## Development, build and maintenance tasks

### Defensive settings for make:
#     https://tech.davis-hansson.com/p/make/
SHELL:=bash
.ONESHELL:
.SHELLFLAGS:=-xeu -o pipefail -c
.SILENT:
.DELETE_ON_ERROR:
MAKEFLAGS+=--warn-undefined-variables
MAKEFLAGS+=--no-builtin-rules
PS1?=$$

# Options affecting target behavior
DEBUG=
POST_MORTEM=
export PUID=1000
export PGID=100
REQUIREMENTS=./requirements-devel.txt

# Derived values
VENVS = $(shell tox -l)


## Top-level targets

.PHONY: all
### Default target
all: build

.PHONY: build
### Perform any currently necessary local set-up common to most operations
build: \
		./var/log/init-setup.log ./var/log/recreate.log \
		./var/log/docker-build.log ./server/.htpasswd \
		./src/feedarchiver/tests/archives/end-to-end/.feed-archiver.yml
.PHONY: build-dist
### Build installable Python packages, mostly to check build locally
build-dist: build
	./.tox/build/bin/python -m build

.PHONY: start
### Run the local development end-to-end stack services in the background as daemons
start: build
	docker compose down
	docker compose up -d
.PHONY: run
### Run the local development end-to-end stack services in the foreground for debugging
run: build
	docker compose down
	docker compose up
.PHONY: run-debug
### Run the update sub-command in the container via the interactive debugger
run-debug: build
	docker compose run --rm -e DEBUG="$(DEBUG)" -e POST_MORTEM="$(POST_MORTEM)" \
	    --entrypoint="python" "feed-archiver" -m "pdb" \
	    "/usr/local/bin/feed-archiver" "update"

.PHONY: format
### Automatically correct code in this checkout according to linters and style checkers
format: build
	./.tox/lint/bin/autoflake -r -i --remove-all-unused-imports \
		--remove-duplicate-keys --remove-unused-variables \
		--remove-unused-variables ./
	./.tox/lint/bin/autopep8 -v -i -r --exclude "var" ./
	./.tox/lint/bin/black ./

.PHONY: test
### Run the full suite of tests, coverage checks, and linters
test: build format test-docker
.PHONY: test-docker
### Run the full suite of tests inside a docker container
test-docker: ./var/log/docker-build.log
	docker compose run --rm --workdir="/usr/local/src/feed-archiver/" \
	    --entrypoint="tox" feed-archiver
# Ensure the dist/package has been correctly installed in the image
	docker compose run --rm --entrypoint="python" feed-archiver \
	    -m feedarchiver --help
	docker compose run --rm --entrypoint="feed-archiver" feed-archiver --help

.PHONY: test-debug
### Run tests in the main/default environment and invoke the debugger on errors/failures
test-debug: ./var/log/editable.log
	./.tox/py310/bin/pytest --pdb

.PHONY: upgrade
### Update all fixed/pinned dependencies to their latest available versions
upgrade:
	touch "./pyproject.toml"
	$(MAKE) PUID=$(PUID) "test"

.PHONY: clean
### Restore the checkout to a state as close to an initial clone as possible
clean:
	docker compose down --rmi "all" -v || true
	test ! -x "./.tox/lint/bin/pre-commit" || (
	    ./.tox/lint/bin/pre-commit uninstall --hook-type pre-push
	    ./.tox/lint/bin/pre-commit uninstall
	    ./.tox/lint/bin/pre-commit clean
	)
	git clean -dfx -e "var/"
	rm -vf "./var/log/init-setup.log" "./var/log/recreate.log" \
	    "./var/log/editable.log" "./var/log/docker-build.log"


## Utility targets

.PHONY: expand-template
## Create a file from a template replacing environment variables
expand-template: .SHELLFLAGS = -eu -o pipefail -c
expand-template:
	if [ -e "$(target)" ]
	then
	    echo "Template $(template) has been updated"
	    echo "Reconcile changes and touch $(target)"
	    false
	fi
	envsubst <"$(template)" >"$(target)"


## Real targets

./requirements.txt: ./pyproject.toml ./setup.cfg ./tox.ini
	tox -r -e "build"

./var/log/recreate.log: ./requirements.txt ./requirements-devel.txt ./tox.ini
	mkdir -pv "$(dir $(@))"
	tox -r --notest -v | tee "$(@)"
# Workaround tox's `usedevelop = true` not working with `./pyproject.toml`
./var/log/editable.log: ./var/log/recreate.log
	./.tox/py310/bin/pip install -e "./"

# Docker targets
./var/log/docker-build.log: \
		./requirements.txt ./requirements-devel.txt \
		./Dockerfile ./docker-compose.yml ./.env
# Ensure access permissions to the `./.tox/` directory inside docker.  If created by `#
# dockerd`, it ends up owned by `root`.
	mkdir -pv "./.tox-docker/" "./src/feed_archiver-docker.egg-info/" \
	    "./sonarr/config/" "./letsencrypt/"
	docker compose build --pull \
	    --build-arg "PUID=$(PUID)" --build-arg "PGID=$(PGID)" \
	    --build-arg "REQUIREMENTS=$(REQUIREMENTS)" >> "$(@)"
# Use separate Python artifacts inside the image and locally on the host
	docker compose run --rm --workdir="/usr/local/src/feed-archiver/" \
	    --entrypoint="tox" feed-archiver -r --notest -v

# Local environment variables from a template
./.env: ./.env.in
	$(MAKE) "template=$(<)" "target=$(@)" expand-template

# Static site server set up
./server/.htpasswd: .SHELLFLAGS = -eu -o pipefail -c
./server/.htpasswd:
	echo "Enter a HTTP Basic authentication password for the static site server."
	if ! which htpasswd
	then
	    sudo apt-get update
	    sudo apt-get install -y apache2-utils
	fi
	htpasswd -c "$(@)" "feed-archiver"

# Extract the Sonarr API key
./sonarr/config/config.xml: ./var/log/docker-build.log
	docker compose up -d sonarr
	sleep 1
	until [ -e "$(@)" ]
	do
	    sleep 0.1
	done
./src/feedarchiver/tests/archives/end-to-end/.feed-archiver.yml: \
		./src/feedarchiver/tests/archives/end-to-end/.feed-archiver.yml.in \
		./sonarr/config/config.xml
	export SONARR_API_KEY=$$(
	    sed -nE 's|.*<ApiKey>(.+)</ApiKey>.*|\1|p' "./sonarr/config/config.xml"
	)
	$(MAKE) "template=$(<)" "target=$(@)" expand-template

# Perform any one-time local checkout set up
./var/log/init-setup.log: ./.git/hooks/pre-commit ./.git/hooks/pre-push
	mkdir -pv "$(dir $(@))"
	date >> "$(@)"

./.git/hooks/pre-commit: ./var/log/recreate.log
	./.tox/lint/bin/pre-commit install

./.git/hooks/pre-push: ./var/log/recreate.log
	./.tox/lint/bin/pre-commit install --hook-type pre-push


# Emacs editor settings
./.dir-locals.el: ./.dir-locals.el.in
	$(MAKE) "template=$(<)" "target=$(@)" expand-template
