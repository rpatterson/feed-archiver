########################################################################################
feed-archiver
########################################################################################
Archive the full contents of RSS/Atom syndication feeds including enclosures and assets.
****************************************************************************************

.. image:: https://github.com/rpatterson/feed-archiver/workflows/Run%20linter,%20tests%20and,%20and%20release/badge.svg

The ``$ feed-archiver`` command aims to archive RSS/Atom feeds as fully as possible in
such a way that the archive can serve (at least) 2 use cases:

#. `Mirror of Feed Enclosures and Assets`_

    A mirror of the archived feeds that can be in turn served onto onto feed
    clients/subscribers (such as podcatchers).  For example, you can subscribe to the
    archived feed from your podcatcher app on your phone with auto-download and
    auto-delete of podcast episodes while archiving those same episodes on your HTPC
    server with large enough storage to keep all episodes.  The archived version of the
    feed will also reflect the earliest form of feed XML, item XML, enclosures, and
    assets that the archive downloaded and as such can be used to reflect the original
    version to clients even as the remote feed changes over time.

#. `Ingest Feed Enclosures Into Media Libraries`_

    An alternate hierarchy of feed item enclosures better suited for ingestion into
    other media software, such as media library servers.  For example, your podcast
    episodes can also be made available in your `Jellyfin`_/Emby/Plex library.

********************
Detailed Description
********************

Mirror of Feed Enclosures and Assets
====================================

To serve use case #1, ``feed-archiver`` downloads enclosures and external assets
(e.g. feed and item logos specified as URLs in the feed XMLs) to the archive's local
filesystem, adjusts the URLs of the downloaded items in the feed XML, and saves the feed
XML into the archive as well.  This makes the local archive filesystem suitable for
serving to feed clients/subscribers using a simple static site server such as `nginx`_.

All URLs are transformed into file-system paths that are as readable as possible while
avoiding special characters that may cause issues with common file-systems.
Specifically, special characters are ``%xx`` escaped using `Python's
urllib.parse.quote`_ function.  Note that this will double-escape any
``%xx`` escapes in the remote URL:

  ``.../foo?bar=qux%2Fbaz#corge`` -> ``.../foo%3Fbar=qux%252Fbaz#corge``

Then the URL is converted to a corresponding filesystem path:

  ``https://foo-username:secret@grault.example.com/feeds/garply.rss`` ->
  ``./https/foo-username%3Asecret@grault.example.com/feeds/garply.rss``

Assuming the archived feeds are all hosted via HTTPS/TLS from an `nginx server_name`_ of
``feeds.example.com``, then subscribing to the archived feed in a syndication client,
such as a pod-catcher app can be done by transforming the URL like so:

  ``https://foo-username:secret@grault.example.com/feeds/garply.rss`` ->
  ``https://feeds.example.com/https/foo-username%3Asecret@grault.example.com/feeds/garply.rss``

IOW, it's as close as possible to simply prepending your archives host name to the feed
URL.

As feeds change over time, ``feed-archiver`` preserves the earliest form of feed content
as much as possible.  If a feed item is changed in a subsequent retrieval of the feed,
the remote item XML is preserved instead of updating to the newer XML.  More
specifically, items will be ignored on subsequent retrievals of the same feed if they
have the same ``guid``/``id`` as items that have previously been archived for that feed.

Ingest Feed Enclosures Into Media Libraries
===========================================

To serve use case #2, ``feed-archiver`` links the downloaded feed item enclosures into
an alternate hierarchy based on feed item metadata that better reflects the
show-with-episodes nature of most feeds, such as podcasts, with media enclosures.  What
feed item metadata is used and how it's used to assemble the media library path
enclosures are linked into is configurable on a per-feed basis.  This can be used, for
example, simply to make your podcasts accessible from your media library software.  In a
more complex example, it can be used to link episodes from a podcast about a TV series
as `external alternative audio tracks`_ next to the corresponding TV episode video file.
Multiple linking paths can be configured such that feed item enclosures can be ingested
in multiple locations in media libraries.

Because syndication feeds may have a number of different ways to correspond to library
media, this functionality needs to be highly configurable and in order to be highly
configurable it is more complex to customize to a specific goal.  As such, using this
feature requires using `a link path plugin`_, or the skill level of a junior developer,
or someone who is comfortable reading and interpreting technical documentation, or
re-using example configurations known to work by others.


************
Installation
************

Install using any tool for installing standard Python 3 distributions such as `pip`_::

  $ sudo pip3 install feed-archiver


*****
Usage
*****

Create a ``./.feed-archiver.yml`` YAML file in a directory to serve as the root
directory for all feeds to be archived.  The YAML file must have a top-level
``defaults`` key whose value is an object defining default or global options.  In
particular, the ``base-url`` key in that section whose value must be a string which
defines the external base URL at which the archive is served to clients and is used to
assemble absolute URLs where relative URLs can't be used.  The file must also have a
top-level ``feeds`` key whose value is an array or list of objects defining the remote
feeds to archive in this directory.  Each feed object must contain a ``remote-url`` key
whose value is a string that contains the URL of an individual feed to archive.  In the
simplest form, this can just be a file like so::

  defaults:
    base-url: "https://feeds.example.com"
  feeds:
    - remote-url:
	"https://foo-username:secret@grault.example.com/feeds/garply.rss?bar=qux%2Fbaz#corge"
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

To link feed items into an `alternate hierarchy`_, such as in a media library, add a
``link-paths`` key to the feed configuration whose value is an list/array of objects
each defining one alternative path to link to the feed item enclosure.  Any
``link-paths`` defined in the top-level ``defaults`` key will be used for all feeds.
Configuration to be shared across multiple ``link-paths`` configurations may be placed
in the corresponding ``defaults`` / ``plugins`` / ``link-paths`` / ``{plugin_name}``
object.  The actual linking of enclosures is delegated to `plugins`_.


*******
Plugins
*******

How feed item enclosures are linked into a media library is delegated to plugins or
add-ons.  Specifically, the ``plugin`` key in a ``link-paths`` configuration must be a
string which is the name of `a Python entry point`_ registered in the
``feedarchiver.linkpaths`` group.  The entry point object reference must point to a
``feedarchiver.linkpaths.LinkPathPlugin`` subclass which accepts the following arguments
when instantiated:

#. ``parent=dict``

   The ``feedarchiver.archive.Archive`` if the plugin is configured in ``defaults`` for
   all feeds or the ``feedarchiver.feed.ArchiveFeed`` if defined for a specific feed.

#. ``config=dict``

   The Python dictionary object from the de-serialized archive configuration YAML for
   this specific link path configuration.

and whose instances must be callable and accept the following arguments when called:

#. ``archive_feed=feedarchiver.feed.ArchiveFeed``

   The object ``feedarchiver`` uses internally to represent an individual feed in the
   archive.

#. ``feed_elem=xml.etree.ElementTree.Element``

   The `Python XML element object`_ representing the whole feed.  For RSS this is the
   ``<channel>`` child element while for Atom this is the root ``<feed>`` element.

#. ``item_elem=xml.etree.ElementTree.Element``

   The `Python XML element object`_ representing the specific feed item.

#. ``url_result=lxml.TODO``

   The `lmxl special string object`_ that contains the URL of the specific enclosure.
   Can be used to access the specific enclosure element.

#. ``basename=str``

  The best guess at the most correct file basename, including the suffix or extension,
  for the given enclosure.  This suffix takes into account the suffix from the enclosure
  URL, the ``Content-Type`` header of the response to the enclosure URL request, and
  finally the value of any ``type`` attribute of the enclosure element XML.

#. ``match=re.Match``

   The `Python regular expression match object`_ if the ``match-pattern`` matched the
   string expanded from the `Python format string`_ in the ``match-string`` key.
   Particularly useful to designate `regular expression groups`_ in the
   ``match-pattern`` and then use the parts of ``match-string`` that matched those
   groups in the format ``template``.  If the ``match-pattern`` doesn't match then the
   enclosure will not be linked.  If no ``match-string`` is provided a default is used
   combining the feed title, item title, and enclosure basename with extension::

     {feed_elem.find('title').text.strip()}/{item_elem.find('title').text.strip()}/{basename}

If the plugin returns a value, it must be a list of strings and will be used as the
target paths at which to link the enclosure.  Relative paths are resolved against the
archive root.  These paths are not escaped, so if escaping is needed it must be a part
of the plugin configuration.  Here's an example ``link-paths`` definition::

  defaults:
    base-url: "https://feeds.example.com"
    plugins:
      link-paths:
        sonarr:
          url: "http://localhost:8989"
          api-key: "????????????????????????????????"
    link-paths:
      # Link all feed item enclosures into the media library under the podcasts directory
      - template: "/media/Library/Music/Podcasts/{feed_elem.find('title').text.strip()}/{item_elem.find('title').text.strip()})/{basename}"
  feeds:
    - remote-url:
	"https://foo-username:secret@grault.example.com/feeds/garply.rss?bar=qux%2Fbaz#corge"
      link-paths:
	# This particular feed is a podcast about a TV series/show.  Link enclosures
	# from feed items about an individual episode next to the episode video file as
	# an external audio track using a non-default plugin.
	- plugin: "sonarr"
	  match-string: "{item_elem.find('title').text.strip()}"
	  match-pattern: "(?P<item_title>.+) \\((?P<series_title>.+) (?P<season_number>[0-9])(?P<episode_numbers>[0-9]+[0-9Ee& -]*)\\)"
	  stem-append: "-garply"
  ...

Default Template Plugin
=======================

If no ``plugin`` key is specified, the ``template`` plugin is used.  The link
path config may include the ``template`` key containing a `Python format string`_ which
will be expanded to determine where the feed item enclosure should be linked to.  The
default ``template`` is::

  ./Feeds/{feed_elem.find('title').text.strip()}/{item_elem.find('title').text.strip()}/{basename}

The format strings may reference any of `the arguments passed into link path plugins`_.

Sonarr TV Series Plugin
=======================

The ``sonarr`` plugin uses values from the link path configuration and/or the ``match``
groups to lookup a TV series/show managed by `Sonarr`_, then lookup an episode video
file that corresponds to the feed item enclosure/content, and link the enclosure/content
next to that video file.  The ``link-paths`` configuration or ``match`` groups must
contain:

- ``url`` and ``api-key`` used to `connect to the Sonarr API`_
- ``series_id`` or ``series_title`` used to `look up the TV show/series`_, note that
  using ``series_id`` saves on Sonarr API request per update
- ``season_number`` used to `lookup the episode file`_
- ``episode_numbers`` used to `lookup the episode file`_, plural to support
  multi-episode files

They may also include:

- ``stem-append`` containing a string to append to the episode file stem before the
  enclosure/content suffix/extension


.. _alternate hierarchy: `Ingest Feed Enclosures Into Media Libraries`_
.. _a link path plugin: `Plugins`_
.. _the arguments passed into link path plugins: `Plugins`_

.. _pip: https://pip.pypa.io/en/stable/installing/
.. _a Python entry point:
   https://packaging.python.org/en/latest/specifications/entry-points/#data-model
.. _Python format string: https://docs.python.org/3/library/string.html#formatstrings
.. _Python regular expression match object:
   https://docs.python.org/3/library/re.html#match-objects
.. _regular expression groups: https://docs.python.org/3/library/re.html#index-17
.. _Python's urllib.parse.quote:
   https://docs.python.org/3/library/urllib.parse.html#urllib.parse.quote
.. _Python XML element object:
    https://docs.python.org/3/library/xml.etree.elementtree.html#element-objects
.. _lmxl special string object: https://lxml.de/xpathxslt.html#xpath-return-values

.. _nginx: https://nginx.org/en/docs/
.. _nginx server_name: https://www.nginx.com/resources/wiki/start/topics/examples/server_blocks/

.. _Jellyfin: https://jellyfin.org/
.. _external alternative audio tracks:
   https://jellyfin.org/docs/general/server/media/external-audio-files.html
.. _Sonarr: https://sonarr.tv
.. _connect to the Sonarr API: https://github.com/Sonarr/Sonarr/wiki/API#url
.. _look up the TV show/series: https://github.com/Sonarr/Sonarr/wiki/Series#getid
.. _lookup the episode file: https://github.com/Sonarr/Sonarr/wiki/Episode#get
