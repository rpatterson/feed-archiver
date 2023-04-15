########################################################################################
Seeking Contributions
########################################################################################

Known bugs and desirable features for which contributions are most welcome.


****************************************************************************************
Required
****************************************************************************************


****************************************************************************************
High Priority
****************************************************************************************

#. Add an enclosure plugin to create playlists.

#. Any documentation improvements!

   Documentation benefits perhaps most from the attention of fresh eyes.  If you find
   anything confusing, please ask for clarification and once you understand what you
   didn't before, please do contribute changes to the documentation to spare future
   users the same confusion.

#. Initialize Python's ``mimetypes`` module with same ``mime.types`` file as is used by
   the static site server::

       $ docker run -it --entrypoint find nginx -name "mime.types"
       ./etc/nginx/mime.types

#. Rename to match the Servarr convention: ``feederr``.

#. Option to use an alternate element as each item's unique identifier within a feed.
   Also requires generalized element value handling (e.g. ``value`` attribute vs an
   element's child text nodes).

#. Parallelize both the processing of whole feeds and the downloading of enclosures and
   assets within each feed using a shared pool.  Maybe using:

   - https://github.com/requests/requests-threads
   - https://toolbelt.readthedocs.io/en/latest/threading.html
   - https://www.python-httpx.org/async/

#. Determine if HTTP/2 is a significant performance improvement for serving large media
   files and integrate into the Traefik -> Nginx stack if yes.


****************************************************************************************
Nice to Have
****************************************************************************************

#. Feed config option to override downloads XPath expression.

#. Option to re-download enclosures/assets if
   Last-Modified/If-Modified-Since/If-Unmodified-Since

#. Option to re-download enclosures/assets if Content-Length is different

#. A 404 handler or somesuch to add feeds to ``./.feed-archiver.yml`` and run ``$
   feed-archiver`` automatically?  IOW, transform feed URL and add to pod-catcher app
   and "it just works".

#. Add ``prune`` sub-command to remove all downloads not referenced in any archive feed
   file.

#. Order new items based on which siblings they're next to in the previous feed version.

#. Extension point (setuptools entry points?) for selecting specialized download
   handlers based on MIME type (e.g. HTML page assets/resources below).

#. Also download all assets/resources for HTML downloads, possibly with `pywebcopy
   <https://stackoverflow.com/a/51544575/624787>`_.

#. Cleanup embedded enclosure metadata (e.g. ID3 tags in MP3) based on item data.  For
   example, add missing ID3 tag with title from the item XML.

#. Improve XML namespace map/prefix for custom attributes.

#. Archive config option to specify the list of safe characters for quoting.

#. Maybe allow Unicode in filesystem path escaping?  Do most filesystems support
   Unicode, for instance?  How do static file servers handle Unicode in filesystem
   paths?

#. Option to use hard links instead of symlinks.

#. More examples of template configurations to match feed metadata: e.g. prepending
   ``<itunes:episode>`` to link basename, extracting album directory from feed item
   title.
