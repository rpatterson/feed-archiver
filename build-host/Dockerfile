# SPDX-FileCopyrightText: 2023 Ross Patterson <me@rpatterson.net>
#
# SPDX-License-Identifier: MIT

## Container image in which to build, test, and release the project

# I *want* something to break to let me know if something changes in the latest version
# of the base image changes something:
# hadolint ignore=DL3007
FROM docker:latest

# Install the minimum OS packages needed to use the `./Makefile`.  Also install any OS
# packages the `./Makefile` might install to optimize build times.
# hadolint ignore=DL3018
RUN \
    apk add --no-cache \
    "make" \
    "bash" \
    "su-exec" \
    "git" \
    "gettext" \
    "py3-pip" \
    "gnupg" \
    "curl" \
    "tar" \
    "github-cli" \
    && rm -rf /var/cache/apk/*

# Project contstants:
ARG PROJECT_NAMESPACE=rpatterson
ARG PROJECT_NAME=feed-archiver

# Find the same home directory even when run as another user, e.g. `root`.
ENV HOME="/home/runner"
# Add user installs to PATH
ENV PATH="${HOME}/.local/bin:${PATH}"

COPY [ "./requirements-py310.txt", "${HOME}/.local/lib/" ]
RUN mkdir -pv "${HOME}/.local/var/log/" && \
    pip3 install --no-cache-dir --user -r "${HOME}/.local/lib/requirements-py310.txt" \
    >"${HOME}/.local/var/log/${PROJECT_NAME}-host-install.log"

COPY [ "./bin/entrypoint", "/usr/local/bin/entrypoint" ]
ENTRYPOINT [ "docker-entrypoint.sh", "entrypoint" ]
CMD [ "make", "-e", "build-docker" ]

# https://github.com/opencontainers/image-spec/blob/main/annotations.md#pre-defined-annotation-keys
LABEL org.opencontainers.image.url="https://gitlab.com/${PROJECT_NAMESPACE}/${PROJECT_NAME}"
LABEL org.opencontainers.image.documentation="https://gitlab.com/${PROJECT_NAMESPACE}/${PROJECT_NAME}"
LABEL org.opencontainers.image.source="https://gitlab.com/${PROJECT_NAMESPACE}/${PROJECT_NAME}"
LABEL org.opencontainers.image.title="Feed Archiver Build Host"
LABEL org.opencontainers.image.description="Feed Archiver build host"
LABEL org.opencontainers.image.licenses="MIT"
LABEL org.opencontainers.image.authors="Ross Patterson <me@rpatterson.net>"
LABEL org.opencontainers.image.vendor="rpatterson.net"
LABEL org.opencontainers.image.base.name="docker.io/library/docker:latest"
# Build-time `LABEL`s
LABEL org.opencontainers.image.version=0.0.1
