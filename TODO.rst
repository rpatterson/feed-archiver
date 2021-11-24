===========================================================================
Seeking Contributions
===========================================================================
Known bugs and desirable features for which contributions are most welcome.

Required
========

#. File modification dates match response ``Last-Modified`` header.

#. Add CLI options and subcommand.

High Priority
=============

#. Docker image published to a registry automatically in CI/CD

#. Example ``./docker-compose.yml`` file with Traefik for HTTPS/TLS and nginx for static
   file hosting.

#. Option to use an alternate element as each item's unique identifier within a feed.
   Also requires generalized element value handling (e.g. ``value`` attribute vs an
   element's child text nodes).

#. Parallelize both the processing of whole feeds and the downloading of enclosures and
   assets within each feed using a shared pool.  Maybe using httpx/async:

   https://www.python-httpx.org/async/

   https://docs.python.org/3/library/asyncio-queue.html#examples

Nice to Have
============

#. Feed config option to override downloads XPath expression.

#. `lxml.etree <https://lxml.de/3.2/parsing.html#iterparse-and-iterwalk>`_

#. Option to re-download enclosures/assets if
   Last-Modified/If-Modified-Since/If-Unmodified-Since

#. Option to re-download enclosures/assets if Content-Length is different

#. A 404 handler or somesuch to add feeds to ``./.feed-archiver.csv`` and run ``$
   feed-archiver`` automatically?  IOW, transform feed URL and add to pod-catcher app
   and "it just works".

#. Add ``prune`` sub-command to remove all downloads not referenced in any archive feed
   file.

#. Order new items based on which siblings they're next to in the previous feed version.

#. Extension point (setuptools entry points?) for selecting specialized download
   handlers based on MIME type (e.g. HTML page assets/resources below).

#. Playlist creation for media enclosures.

#. Also download all assets/resources for HTML downloads, possibly with `pywebcopy
   <https://stackoverflow.com/a/51544575/624787>`_.
