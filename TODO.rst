===========================================================================
Seeking Contributions
===========================================================================
Known bugs and desirable features for which contributions are most welcome.

#. Docker image published to a registry automatically in CI/CD

#. Example ``./docker-compose.yml`` file with Traefik for HTTPS/TLS and nginx for static
   file hosting.

#. Option to use an alternate element as each item's unique identifier within a feed.

#. Parallelize both the processing of whole feeds and the downloading of enclosures and
   assets within each feed using a shared pool.  Maybe using httpx/async:

   https://www.python-httpx.org/async/

   https://docs.python.org/3/library/asyncio-queue.html#examples

#. Option to re-download enclosures/assets if
   Last-Modified/If-Modified-Since/If-Unmodified-Since

#. Option to re-download enclosures/assets if Content-Length is different

#. A 404 handler or somesuch to add feeds to ``./.feed-archiver.csv`` and run ``$
   feed-archiver`` automatically?  IOW, transform feed URL and add to pod-catcher app
   and "it just works".