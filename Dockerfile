# From https://hub.docker.com/_/python
FROM python:3.10

# Add a user whose home directory will contain the configuration file
ARG PUID=1000
ARG PGID=100
ARG REQUIREMENTS=./requirements.txt

# Install the application and dependencies
WORKDIR /usr/local/src/feed-archiver/
COPY [ "./", "./" ]
RUN pip install --no-cache-dir -r "${REQUIREMENTS}"
RUN pip install --no-cache-dir -e "./"

# Add a user whose home directory will contain the configuration file
RUN adduser --uid "${PUID}" --gid "${PGID}" --disabled-password \
    --gecos "Feed Archiver,,," "feed-archiver"
USER $PUID:$PGID

WORKDIR /home/feed-archiver/
ENTRYPOINT  [ "feed-archiver" ]
CMD [ "update" ]
