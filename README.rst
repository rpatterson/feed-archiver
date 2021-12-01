========================================================================================
feed-archiver
========================================================================================
Archive the full contents of RSS/Atom syndication feeds including enclosures and assets.
----------------------------------------------------------------------------------------

.. image:: https://github.com/rpatterson/feed-archiver/workflows/Run%20linter,%20tests%20and,%20and%20release/badge.svg

The ``$ feed-archiver`` command aims to archive RSS/Atom feeds as fully as possible in
such a way that it can be served simply by a static site server such as `nginx`_.  It
downloads feed XML, feed item enclosures, such as podcast audio files, and assets, such
as images or icons.  Downloaded enclosures and assets are stored in a static filesystem
tree, and their URLs in the feed XML are adjusted to point to the relative archived
location.  The adjusted feed XML is then written to the same filesystem tree.

All URLs are transformed into file-system paths that are as readable as possible while
avoiding special characters that may cause issues with common file-systems.
Specifically, special characters are ``%xx`` escaped using `Python's
urllib.parse.quote`_ function.  Note that this will double-escape any
``%xx`` escapes in the existing URL:

  ``.../foo?bar=qux%2Fbaz#corge`` -> ``.../foo%3Fbar%3Dqux%252Fbaz%23corge``

Then the URL is converted to a corresponding filesystem path:

  ``https://foo-username:secret@grault.example.com/feeds/garply.rss`` ->
  ``./https/foo-username%3Asecret%40grault.example.com/feeds/garply.rss``

Assuming the archived feeds are all hosted via HTTPS/TLS from an `nginx server_name`_ of
``feeds.example.com``, then subscribing to the archived feed in a syndication client,
such as a pod-catcher app can be done by transforming the URL like so:

  ``https://foo-username:secret@grault.example.com/feeds/garply.rss`` ->
  ``https://feeds.example.com/https/foo-username%3Asecret%40grault.example.com/feeds/garply.rss``

IOW, it's as close as possible to simply prepending your archives host name to the feed
URL.

As feeds change over time, ``feed-archiver`` preserves the earliest form of feed content
as much as possible.  If a feed item is changed in a subsequent retrieval of the feed,
the remote item XML is preserved instead of updating to the newer XML.  More
specifically, items will be ignored on subsequent retrievals of the same feed if they
have the same ``guid``/``id`` as items that have previously been archived for that feed.


Installation
============

Install using any tool for installing standard Python 3 distributions such as `pip`_::

  $ sudo pip3 install feed-archiver


Usage
=====

Create a ``./.feed-archiver.csv`` CSV file in a directory to serve as the root directory
for all feeds to be archived.  The CSV file should have a header row, a row defining
default or global options.  The second column of the defaults row should define the
external base URL for the archive and is used to assemble absolute URLs where relative
aURLs can't be used.  The first cell of each row after that should contain the URL of a
feed to archive in this directory.  In the simplest form, this can just be a file with
one header line and one feed URL per line from there::

  Feed Remote URL,Feed Archive URL
  ,https://feeds.example.com
  https://foo-username:secret@grault.example.com/feeds/garply.rss,
  ...

Then simple run the ``$ feed-archiver`` command in that directory to update the archive
from the current version of the feeds::

  $ cd "/var/www/html/feeds/"
  $ feed-archiver
  INFO:Retrieving feed URL: https://foo-username:secret@grault.example.com/feeds/garply.rss
  ...

See also the command-line help for details on options and arguments::

  $ usage: feed-archiver [-h] [archive-dir...]

  Archive the full contents of RSS/Atom syndication feeds including enclosures and
  assets.

  positional arguments:
    archive-dir  filesystem path to the root of an archive of feeds (default: ./)

  optional arguments:
    -h, --help  show this help message and exit

  ...


.. _pip: https://pip.pypa.io/en/stable/installing/
.. _Python's urllib.parse.quote:
   https://docs.python.org/3/library/urllib.parse.html#urllib.parse.quote

.. _nginx: https://nginx.org/en/docs/
.. _nginx server_name: https://www.nginx.com/resources/wiki/start/topics/examples/server_blocks/
