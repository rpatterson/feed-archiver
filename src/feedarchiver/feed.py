"""
An RSS/Atom syndication feed in an archive.
"""

import os
import email
import logging

from lxml import etree

from . import formats

logger = logging.getLogger(__name__)


class ArchiveFeed:
    """
    An RSS/Atom syndication feed in an archive.
    """

    FEED_FORMATS = {
        feed_format.ROOT_TAG: feed_format
        for feed_format in vars(formats).values()
        if isinstance(feed_format, type) and issubclass(feed_format, formats.FeedFormat)
    }

    def __init__(self, archive, config, url):
        """
        Instantiate a representation of an archive from a file-system path.
        """
        self.archive = archive
        self.config = config
        self.url = url
        self.path = archive.url_to_path(url)

    def update(self):
        """
        Request the URL of one feed in the archive and update contents accordingly.
        """
        updated_items = {}
        logger.info("Requesting feed: %r", self.url)
        feed_response = self.archive.requests.get(self.url)
        logger.debug("Parsing feed XML: %r", self.url)
        remote_root = etree.fromstring(feed_response.content)

        # Be as permissive as possible in identifying the feed format to tolerate poorly
        # behaved feeds (e.g. wrong `Content-Type` header, XML namespace, etc.).
        # Identify feeds by the top-level XML tag name (e.g. `<rss>` or `<feed>`).
        remote_root_tag = etree.QName(remote_root.tag).localname.lower()
        if remote_root_tag not in self.FEED_FORMATS:  # pragma: no cover
            raise NotImplementedError(
                f"No feed format handler for {remote_root.tag!r} root element"
            )
        feed_format = self.FEED_FORMATS[remote_root_tag]()

        is_feed_initialized = self.path.exists()
        if not is_feed_initialized:
            # First time requesting this feed, simply copy the remote feed to the
            # archive
            logger.info(
                "Initializing feed in archive: %r -> %r",
                self.url,
                str(self.path),
            )
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("w") as feed_archive_opened:
                feed_archive_opened.write(feed_response.text)

        logger.debug("Parsing archive XML: %r", self.url)
        with self.path.open() as feed_archive_opened:
            archive_tree = etree.parse(feed_archive_opened)
        archive_root = archive_tree.getroot()
        archived_items_parent = feed_format.get_items_parent(archive_root)
        if not is_feed_initialized:
            # Re-use remote item processing logic below, clear archived children when
            # initializing the feed.
            for archive_item_elem in feed_format.iter_items(archive_root):
                archived_items_parent.remove(archive_item_elem)
            archived_items = []
        else:
            archived_items = list(feed_format.iter_items(archive_root))
        archived_item_ids = set()

        # Iterate through the remote feed to make updates to the archived feed as
        # appropriate.
        logger.info(
            "Updating feed in archive: %r -> %r",
            self.url,
            str(self.path),
        )
        # What is the lowest child index for the first item, used to insert new items at
        # the top
        first_item_idx = 0
        for first_item_idx, item_sibling in enumerate(
            archived_items_parent.iterchildren(),
        ):
            if etree.QName(item_sibling.tag).localname.lower() == feed_format.ITEM_TAG:
                break
        else:
            first_item_idx += 1
        remote_items = list(feed_format.iter_items(remote_root))
        # Ensure that the order of new feed items is preserved
        remote_items.reverse()
        for remote_item_elem in remote_items:
            remote_item_id = feed_format.get_item_id(remote_item_elem)
            if remote_item_id in archived_item_ids:
                # This item was already seen in the archived feed, we don't need to
                # update the archive or search further in the archived feed.
                continue
            for archived_item_elem in archived_items:
                archived_item_ids.add(feed_format.get_item_id(archived_item_elem))
                if remote_item_id in archived_item_ids:
                    # Found this item in the archived feed, we don't need to
                    # update the archive and we can stop searching the archived feed for
                    # now.
                    break
            else:
                # The remote item ID was not found in the archived feed, update the feed
                # by adding this remote item.
                logger.info(
                    "Adding feed item to archive: %r -> %r",
                    remote_item_id,
                    str(self.path),
                )
                updated_items[remote_item_id] = remote_item_elem
                archived_items_parent.insert(first_item_idx, remote_item_elem)

        # Download enclosures and assets as appropriate
        download_paths = []
        if not is_feed_initialized:
            # Consistent with initial download of the feed, only download assets for the
            # initial version of the feed.
            download_paths.extend(
                self.download_urls(
                    feed_format.iter_feed_download_urls(archive_root),
                ),
            )
        # Download enclosures and assets only for the items that are new to this version
        # of the feed.
        for item_id, item_elem in updated_items.items():
            download_paths.extend(
                self.download_urls(
                    feed_format.iter_item_download_urls(item_elem),
                ),
            )

        if updated_items or not is_feed_initialized:
            # Pretty format the feed for readability
            etree.indent(archive_tree)
            # Update the archived feed file
            archive_tree.write(str(self.path))
        if "Last-Modified" in feed_response.headers:
            last_modified = email.utils.parsedate_to_datetime(
                feed_response.headers["Last-Modified"],
            )
            feed_stat = self.path.stat()
            os.utime(
                self.path,
                (feed_stat.st_atime, last_modified.timestamp()),
            )

        return list(updated_items.keys()), download_paths

    def download_urls(self, url_results):
        """
        Escape URLs to archive paths, download if new, and update URLs.
        """
        downloaded_paths = []
        for url_result in url_results:
            download_path = self.archive.url_to_path(url_result)
            if download_path.name == self.archive.INDEX_BASENAME:
                download_relative = download_path.parent
            else:
                download_relative = download_path
            download_relative = os.path.relpath(download_relative, self.path.parent)

            # Download the URL to the escaped local path in the archive
            if not download_path.exists():
                download_path.parent.mkdir(parents=True, exist_ok=True)
                logger.info(
                    "Downloading URL into archive: %r -> %r",
                    url_result,
                    str(download_relative),
                )
                with self.archive.requests.get(
                    url_result,
                    stream=True,
                ) as download_response:
                    with download_path.open("wb") as download_opened:
                        for chunk in download_response.iter_content(chunk_size=None):
                            download_opened.write(chunk)
                    if "Last-Modified" in download_response.headers:
                        last_modified = email.utils.parsedate_to_datetime(
                            download_response.headers["Last-Modified"],
                        )
                        download_stat = download_path.stat()
                        os.utime(
                            download_path,
                            (download_stat.st_atime, last_modified.timestamp()),
                        )
                downloaded_paths.append(
                    download_path.relative_to(self.archive.root_path),
                )

            # Update the URL in the feed XML to the relative archive path.
            # Update only after successful download to minimize inconsistent state on
            # errors.
            if hasattr(url_result, "getparent") and hasattr(url_result, "attrname"):
                if url_result.attrname:
                    logger.info(
                        'Updating feed URL: <%s %s="%s"...>',
                        url_result.getparent().tag,
                        url_result.attrname,
                        str(download_relative),
                    )
                    url_result.getparent().attrib[url_result.attrname] = str(
                        download_relative
                    )
                else:
                    logger.info(
                        "Updating feed URL: <%s>%s</%s>",
                        url_result.getparent().tag,
                        str(download_relative),
                        url_result.getparent().tag,
                    )
                    url_result.getparent().text = str(download_relative)
            else:  # pragma: no coverx
                raise NotImplementedError(
                    f"Escaping URLs in {type(url_result)!r} text nodes"
                    " not implemented yet",
                )

        return downloaded_paths
