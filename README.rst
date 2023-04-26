########################################################################################
feed-archiver
########################################################################################
Archive the full contents of RSS/Atom syndication feeds including enclosures and assets.
****************************************************************************************

.. list-table::
   :class: borderless align-right

   * - .. figure:: https://img.shields.io/pypi/v/feed-archiver.svg?logo=pypi&label=PyPI&logoColor=gold
	  :alt: PyPI latest release version
	  :target: https://pypi.org/project/feed-archiver/
       .. figure:: https://img.shields.io/pypi/dm/feed-archiver.svg?color=blue&label=Downloads&logo=pypi&logoColor=gold
	  :alt: PyPI downloads per month
	  :target: https://pypi.org/project/feed-archiver/
       .. figure:: https://img.shields.io/pypi/pyversions/feed-archiver.svg?logo=python&label=Python&logoColor=gold
	  :alt: PyPI Python versions
	  :target: https://pypi.org/project/feed-archiver/
       .. figure:: https://img.shields.io/badge/code%20style-black-000000.svg
	  :alt: Python code style
	  :target: https://github.com/psf/black

     - .. figure:: https://gitlab.com/rpatterson/feed-archiver/-/badges/release.svg
	  :alt: GitLab latest release
	  :target: https://gitlab.com/rpatterson/feed-archiver/-/releases
       .. figure:: https://gitlab.com/rpatterson/feed-archiver/badges/main/pipeline.svg
          :alt: GitLab CI/CD pipeline status
          :target: https://gitlab.com/rpatterson/feed-archiver/-/commits/main
       .. figure:: https://gitlab.com/rpatterson/feed-archiver/badges/main/coverage.svg
          :alt: GitLab coverage report
	  :target: https://gitlab.com/rpatterson/feed-archiver/-/commits/main
       .. figure:: https://img.shields.io/gitlab/stars/rpatterson/feed-archiver?gitlab_url=https%3A%2F%2Fgitlab.com&logo=gitlab
	  :alt: GitLab repo stars
	  :target: https://gitlab.com/rpatterson/feed-archiver

     - .. figure:: https://img.shields.io/github/v/release/rpatterson/feed-archiver?logo=github
	  :alt: GitHub release (latest SemVer)
	  :target: https://github.com/rpatterson/feed-archiver/releases
       .. figure:: https://github.com/rpatterson/feed-archiver/actions/workflows/build-test.yml/badge.svg
          :alt: GitHub Actions status
          :target: https://github.com/rpatterson/feed-archiver/actions/workflows/build-test.yml
       .. figure:: https://app.codecov.io/github/rpatterson/feed-archiver/branch/main/graph/badge.svg?token=GNKVQ8VYOU
          :alt: Codecov test coverage
	  :target: https://app.codecov.io/github/rpatterson/feed-archiver
       .. figure:: https://img.shields.io/github/stars/rpatterson/feed-archiver?logo=github
	  :alt: GitHub repo stars
	  :target: https://github.com/rpatterson/feed-archiver/

     - .. figure:: https://img.shields.io/docker/v/merpatterson/feed-archiver/main?sort=semver&logo=docker
          :alt: Docker Hub image version (latest semver)
          :target: https://hub.docker.com/r/merpatterson/feed-archiver
       .. figure:: https://img.shields.io/docker/pulls/merpatterson/feed-archiver?logo=docker
          :alt: Docker Hub image pulls count
          :target: https://hub.docker.com/r/merpatterson/feed-archiver
       .. figure:: https://img.shields.io/docker/stars/merpatterson/feed-archiver?logo=docker
	  :alt: Docker Hub stars
	  :target: https://hub.docker.com/r/merpatterson/feed-archiver
       .. figure:: https://img.shields.io/docker/image-size/merpatterson/feed-archiver?logo=docker
	  :alt: Docker Hub image size (latest semver)
	  :target: https://hub.docker.com/r/merpatterson/feed-archiver

     - .. figure:: https://img.shields.io/keybase/pgp/rpatterson?logo=keybase
          :alt: KeyBase PGP key ID
          :target: https://keybase.io/rpatterson
       .. figure:: https://img.shields.io/github/followers/rpatterson?style=social
          :alt: GitHub followers count
          :target: https://github.com/rpatterson
       .. figure:: https://img.shields.io/liberapay/receives/rpatterson.svg?logo=liberapay
          :alt: LiberaPay donated per week
          :target: https://liberapay.com/rpatterson/donate
       .. figure:: https://img.shields.io/liberapay/patrons/rpatterson.svg?logo=liberapay
          :alt: LiberaPay patrons count
          :target: https://liberapay.com/rpatterson/donate

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

.. contents:: Table of Contents

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
feature requires using `an enclosure plugin`_, or the skill level of a junior developer,
or someone who is comfortable reading and interpreting technical documentation, or
re-using example configurations known to work by others.


****************************************************************************************
Installation
****************************************************************************************

Install and use either via a local, native installation or a Docker container image:

Local/Native Installation
========================================================================================

Install using any tool for installing standard Python 3 distributions such as `pip`_::

  $ pip3 install --user feed-archiver

Optional shell tab completion is available via `argcomplete`_.

Docker Container Image Installation
========================================================================================

The recommended way to use the Docker container image is via `Docker Compose`_.  See
`the example ./docker-compose.yml file`_ for an example configuration.  Once you have
your configuration, you can create and run the container::

  $ docker compose up

Alternatively, you make use the image directly.  Pull `the Docker image`_::

  $ docker pull "registry.gitlab.org/rpatterson/feed-archiver"

And then use the image to create and run a container::

  $ docker run --rm -it "registry.gitlab.org/rpatterson/feed-archiver" ...

Images variant tags are published for the Python version, branch, and major/minor
versions so that users can control when they get new images over time,
e.g. ``registry.gitlab.org/merpatterson/feed-archiver:py310-main``.  The canonical
Python version is 3.10 which is the version used in tags without ``py###``,
e.g. ``registry.gitlab.org/merpatterson/feed-archiver:main``.  Pre-releases are from
``develop`` and final releases are from ``main`` which is also the default for tags
without a branch, e.g. ``registry.gitlab.org/merpatterson/feed-archiver:py310``. The
major/minor version tags are only applied to the final release images and without the
corresponding ``main`` branch tag,
e.g. ``registry.gitlab.org/merpatterson/feed-archiver:py310-v0.8``.

Multi-platform Docker images are published containing images for the following
platforms or architectures in the Python 3.10 ``py310`` variant:

- ``linux/amd64``
- ``linux/arm64``
- ``linux/arm/v7``


****************************************************************************************
Usage
****************************************************************************************

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
    - title: "Garply Podcast Title"
      remote-url: "\
      https://foo-username:secret@grault.example.com\
      /feeds/garply.rss?bar=qux%2Fbaz#corge"
  ...

Then run the ``$ feed-archiver`` command in that directory to update the archive from
the current version of the feeds and write an HTML index with links to the archived
feeds::

  $ cd "/var/www/html/feeds/"
  $ feed-archiver
  INFO:Retrieving feed URL: https://foo-username:secret@grault.example.com/feeds/garply.rss
  ...
  INFO:Writing HTML index: /var/www/html/feeds/index.html

See also the command-line help for details on options and arguments::

  $ feed-archiver --help
  usage: feed-archiver [-h] [--log-level {CRITICAL,FATAL,ERROR,WARN,WARNING,INFO,DEBUG,NOTSET}]
		       [--archive-dir [ARCHIVE_DIR]]
		       {update,relink} ...

  Archive RSS/Atom syndication feeds and their enclosures and assets.

  positional arguments:
    {update,relink}       sub-command
      update              Request the URL of each feed in the archive and update contents accordingly.
      relink              Re-link enclosures to the correct locations for the current configuration.

  options:
    -h, --help            show this help message and exit
    --log-level {CRITICAL,FATAL,ERROR,WARN,WARNING,INFO,DEBUG,NOTSET}
			  Select logging verbosity. (default: INFO)
    --archive-dir [ARCHIVE_DIR], -a [ARCHIVE_DIR]
			  the archive root directory into which all feeds, their enclosures and assets
			  will be downloaded (default: .)

If using the Docker container image, the container can be run from the command-line as
well::

  $ docker compose run "feed-archiver" feed-archiver --help
  usage: feed-archiver [-h]

To link feed item enclosures into an `alternate hierarchy`_, such as in a media library,
add a ``enclosures`` key to the feed configuration whose value is an list/array of
objects each defining one alternative path to link to the feed item enclosure.  Any
``enclosures`` defined in the top-level ``defaults`` key will be used for all feeds.
Configuration to be shared across multiple ``enclosures`` configurations may be placed
in the corresponding ``defaults`` / ``plugins`` / ``enclosures`` / ``{plugin_name}``
object.  The actual linking of enclosures is delegated to `plugins`_.

When updating the archive from the remote feed URLs using the ``$ feed-archiver
update`` sub-command, the enclosures of new items are linked as configured.  If the
``enclosures`` configuration changes or any of the used plugins refer to external
resources that may change, such as the with the ``sonarr`` plugin when `Sonarr`_ has
upgraded or renamed the corresponding video files, use the  ``$ feed-archiver relink``
command to update all existing links.


*******
Plugins
*******

How feed item enclosures are linked into a media library is delegated to plugins or
add-ons.  Specifically, the ``plugin`` key in a ``enclosures`` configuration must be a
string which is the name of `a Python entry point`_ registered in the
``feedarchiver.enclosures`` group.  The entry point object reference must point to a
``feedarchiver.enclosures.EnclosurePlugin`` subclass which accepts the following arguments
when instantiated:

#. ``parent=dict``

   The ``feedarchiver.archive.Archive`` if the plugin is configured in ``defaults`` for
   all feeds or the ``feedarchiver.feed.ArchiveFeed`` if defined for a specific feed.

#. ``config=dict``

   The Python dictionary object from the de-serialized archive configuration YAML for
   this specific enclosure configuration.

and whose instances must be callable and accept the following arguments when called:

#. ``archive_feed=feedarchiver.feed.ArchiveFeed``

   The object ``feedarchiver`` uses internally to represent an individual feed in the
   archive.

#. ``feed_elem=xml.etree.ElementTree.Element``,
   ``item_elem=xml.etree.ElementTree.Element``

   The `Python XML element object`_ representing the whole feed, for RSS this is the
   ``<channel>`` child element while for Atom this is the root ``<feed>`` element, and
   the a similar object representing the specific feed item.

#. ``feed_parsed=feedparser.util.FeedParserDict``,
   ``item_parsed=feedparser.util.FeedParserDict``

   The `feedparser`_ object representing the whole feed and the specific feed item.

#. ``url_result=lxml.etree._ElementUnicodeResult``

   The `lmxl special string object`_ that contains the URL of the specific enclosure.
   Can be used to access the specific enclosure element.

#. ``enclosure_path=pathlib.Path``

   The path to the enclosure in the archive as a `Python pathlib.Path`_ object with the
   best guess at the most correct file basename, including the suffix or extension, for
   the given enclosure.  This suffix takes into account the suffix from the enclosure
   URL, the ``Content-Type`` header of the response to the enclosure URL request, and
   finally the value of any ``type`` attribute of the enclosure element XML.

#. ``match=re.Match``

   The `Python regular expression match object`_ if the ``match-pattern`` matched the
   string expanded from the `Python format string`_ in the ``match-string`` key.
   Particularly useful to designate `regular expression groups`_ in the
   ``match-pattern`` and then use the parts of ``match-string`` that matched those
   groups in the format ``template``.  If the ``match-pattern`` doesn't match then the
   enclosure will not be linked. If there are `symbolic group names`_,
   e.g. ``(?P<foo_group_name>.*)`` in the pattern, then they are also available by name
   in the format string, e.g ``{foo_group_name.lower()}``.  If no ``match-string`` is
   provided a default is used combining the feed title, item title, and enclosure
   basename with extension::

     {utils.quote_sep(feed_parsed.feed.title).strip()}/{utils.quote_sep(item_parsed.title).strip()}{enclosure_path.suffix}

If the plugin returns a value, it must be a list of strings and will be used as the
target paths at which to link the enclosure.  Relative paths are resolved against the
archive root.  These paths are not escaped, so if escaping is needed it must be a part
of the plugin configuration. If no plugins link a given enclosure, then any plugins
whose ``fallback`` key is ``true`` will be applied. Here's an example ``enclosures``
definition::

  defaults:
    base-url: "https://feeds.example.com"
    plugins:
      enclosures:
	sonarr:
	  url: "http://localhost:8989"
	  api-key: "????????????????????????????????"
    enclosures:
      # Link all feed item enclosures into the media library under the podcasts
      # directory.  Link items into an album directory named by series title if
      # matching.
      - template: "\
	/media/Library/Music/Podcasts\
	/{utils.quote_sep(feed_parsed.feed.title).strip()}\
	/{series_title}\
	/{utils.quote_sep(item_parsed.title).strip()}{enclosure_path.suffix}"
	match-string: "{utils.quote_sep(item_parsed.title).strip()}"
	match-pattern: "\
	(?P<item_title>.+) \\((?P<series_title>.+) \
	(?P<season_number>[0-9])(?P<episode_numbers>[0-9]+[0-9Ee& -]*)\\)"
      # Otherwise link into "self-titled" album directories of the same name as the
      # feed.
      - template: "\
        /media/Library/Music/Podcasts\
        /{utils.quote_sep(feed_parsed.feed.title).strip()}\
        /{utils.quote_sep(feed_parsed.feed.title).strip()}\
        /{utils.quote_sep(item_parsed.title).strip()}{enclosure_path.suffix}"
	fallback: true
  feeds:
    - remote-url: "\
      https://foo-username:secret@grault.example.com\
      /feeds/garply.rss?bar=qux%2Fbaz#corge"
      enclosures:
	# This particular feed is a podcast about a TV series/show.  Link enclosures
	# from feed items about an individual episode next to the episode video file as
	# an external audio track using a non-default plugin.
	- plugin: "sonarr"
	  match-string: "{utils.quote_sep(item_parsed.title).strip()}"
	  match-pattern: "\
	  (?P<item_title>.+) \\((?P<series_title>.+) \
	  (?P<season_number>[0-9])(?P<episode_numbers>[0-9]+[0-9Ee& -]*)\\)"
	  stem-append: "-garply"
  ...

Default Template Plugin
=======================

If no ``plugin`` key is specified, the ``template`` plugin is used.  The link
path config may include the ``template`` key containing a `Python format string`_ which
will be expanded to determine where the feed item enclosure should be linked to.  The
default ``template`` is::

  ./Feeds/{utils.quote_sep(feed_parsed.feed.title).strip()}/{utils.quote_sep(item_parsed.title).strip()}{enclosure_path.suffix}

The format strings may reference any of `the arguments passed into enclosure plugins`_.

Sonarr TV Series Plugin
=======================

The ``sonarr`` plugin uses values from the enclosure configuration and/or the ``match``
groups to lookup a TV series/show managed by `Sonarr`_, then lookup an episode video
file that corresponds to the feed item enclosure, and link the enclosure next to that
video file.  The ``enclosures`` configuration or ``match`` groups must contain:

- ``url`` and ``api-key`` used to `connect to the Sonarr API`_
- ``series_id`` or ``series_title`` used to `look up the TV show/series`_, note that
  using ``series_id`` saves on Sonarr API request per update
- ``season_number`` used to `lookup the episode file`_
- ``episode_numbers`` used to `lookup the episode file`_, plural to support
  multi-episode files

They may also include:

- ``stem-append`` containing a string to append to the episode file stem before the
  enclosure suffix/extension


****************************************************************************************
Contributing
****************************************************************************************

NOTE: `This project is hosted on GitLab`_.  There's `a mirror on GitHub`_ but please use
GitLab for reporting issues, submitting PRs/MRs and any other development or maintenance
activity.

See `the ./CONTRIBUTING.rst file`_ for more details on how to get started with
development.


.. _alternate hierarchy: `Ingest Feed Enclosures Into Media Libraries`_
.. _an enclosure plugin: `Plugins`_
.. _the arguments passed into enclosure plugins: `Plugins`_

.. _pip: https://pip.pypa.io/en/stable/installation/
.. _argcomplete: https://kislyuk.github.io/argcomplete/#installation
.. _a Python entry point:
   https://packaging.python.org/en/latest/specifications/entry-points/#data-model
.. _Python format string: https://docs.python.org/3/library/string.html#formatstrings
.. _Python regular expression match object:
   https://docs.python.org/3/library/re.html#match-objects
.. _regular expression groups: https://docs.python.org/3/library/re.html#index-17
.. _symbolic group names: https://docs.python.org/3/library/re.html#index-18
.. _Python's urllib.parse.quote:
   https://docs.python.org/3/library/urllib.parse.html#urllib.parse.quote
.. _Python pathlib.path:
   https://docs.python.org/3/library/pathlib.html#accessing-individual-parts
.. _Python XML element object:
    https://docs.python.org/3/library/xml.etree.elementtree.html#element-objects
.. _lmxl special string object: https://lxml.de/xpathxslt.html#xpath-return-values
.. _feedparser: https://pythonhosted.org/feedparser/index.html

.. _nginx: https://nginx.org/en/docs/
.. _nginx server_name: https://www.nginx.com/resources/wiki/start/topics/examples/server_blocks/

.. _Jellyfin: https://jellyfin.org/
.. _external alternative audio tracks:
   https://jellyfin.org/docs/general/server/media/external-audio-files.html
.. _Sonarr: https://sonarr.tv
.. _connect to the Sonarr API: https://github.com/Sonarr/Sonarr/wiki/API#url
.. _look up the TV show/series: https://github.com/Sonarr/Sonarr/wiki/Series#getid
.. _lookup the episode file: https://github.com/Sonarr/Sonarr/wiki/Episode#get

.. _the Docker image: https://hub.docker.com/r/merpatterson/feed-archiver
.. _`Docker Compose`: https://docs.docker.com/compose/
.. _`the example ./docker-compose.yml file`:
   https://gitlab.com/rpatterson/feed-archiver/blob/main/docker-compose.yml

.. _`This project is hosted on GitLab`:
   https://gitlab.com/rpatterson/feed-archiver
.. _`a mirror on GitHub`:
   https://github.com/rpatterson/feed-archiver
.. _`the ./CONTRIBUTING.rst file`:
   https://gitlab.com/rpatterson/feed-archiver/blob/main/CONTRIBUTING.rst
