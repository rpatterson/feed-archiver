"""
An RSS/Atom syndication feed in an archive.
"""

import os
import copy
import logging

from lxml import etree

import feedarchiver.archive
from . import formats

logger = logging.getLogger(__name__)


class ArchiveFeed:
    """
    An RSS/Atom syndication feed in an archive.
    """

    def __init__(self, archive, config, url):
        """
        Instantiate a representation of an archive from a file-system path.
        """
        self.archive = archive
        self.config = config
        self.url = url
        self.path = archive.url_to_path(url)

    def update(self):  # pylint: disable=too-many-locals
        """
        Request the URL of one feed in the archive and update contents accordingly.
        """
        logger.info("Requesting feed: %r", self.url)
        remote_response = self.archive.requests.get(self.url)
        remote_tree = self.load_remote_tree(remote_response)
        remote_root = remote_tree.getroot()
        remote_format = formats.FeedFormat.from_tree(self, remote_tree)

        download_paths = []
        archive_tree = self.load_archive_tree(
            remote_format,
            remote_tree,
            download_paths,
        )
        archive_root = archive_tree.getroot()
        archived_items_parent = remote_format.get_items_parent(archive_root)
        archived_items = list(remote_format.iter_items(archive_root))

        # Iterate through the remote feed to make updates to the archived feed as
        # appropriate.
        logger.info(
            "Updating feed in archive: %r -> %r",
            self.url,
            str(self.path),
        )
        archived_item_ids = set()
        updated_items = {}
        # What is the lowest child index for the first item, used to insert new items at
        # the top
        first_item_idx = 0
        for first_item_idx, item_sibling in enumerate(
            archived_items_parent.iterchildren(),
        ):
            item_sibling_tag = etree.QName(item_sibling.tag).localname
            if item_sibling_tag.lower() == remote_format.ITEM_TAG:
                break
        else:
            first_item_idx += 1
        remote_items = list(remote_format.iter_items(remote_root))
        # Ensure that the order of new feed items is preserved
        remote_items.reverse()
        for remote_item_elem in remote_items:
            remote_item_id = remote_format.get_item_id(remote_item_elem)
            if remote_item_id in archived_item_ids:
                # This item was already seen in the archived feed, we don't need to
                # update the archive or search further in the archived feed.
                continue
            for archived_item_elem in archived_items:
                archived_item_ids.add(remote_format.get_item_id(archived_item_elem))
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
                item_download_urls = remote_format.iter_item_download_urls(
                    remote_item_elem,
                )
                try:
                    # Download enclosures and assets only for this item.
                    item_download_paths = self.download_urls(item_download_urls)
                except Exception:  # pragma: no cover, pylint: disable=broad-except
                    logger.exception(
                        "Problem item downloading URLs, continuing to next: %r",
                        remote_item_id,
                    )
                    continue
                download_paths.extend(item_download_paths)
                updated_items[remote_item_id] = remote_item_elem
                archived_items_parent.insert(first_item_idx, remote_item_elem)

        if updated_items or download_paths:
            # Pretty format the feed for readability
            etree.indent(archive_tree)
            # Update the archived feed file
            archive_tree.write(str(self.path))
        feedarchiver.archive.update_download_metadata(remote_response, self.path)

        return list(updated_items.keys()), download_paths

    def load_remote_tree(self, remote_response):
        """
        Request the feed from the remote URL, parse the XML, and return the tree.

        Also do any pre-processing needed to start updating the archive.
        """
        logger.debug("Parsing remote XML: %r", self.url)
        remote_root = etree.fromstring(
            remote_response.content,
            base_url=remote_response.url,
        )
        return etree.ElementTree(remote_root)

    def load_archive_tree(self, remote_format, remote_tree, download_paths):
        """
        Parse the local feed XML in the archive and return the tree.

        If there is no local feed XML in the archive, such as the first time the feed is
        updated, then initialize the archive tree from the remote tree.

        Also do any pre-processing needed to start updating the archive.
        """
        if self.path.exists():
            logger.info("Parsing archive XML: %r", self.url)
            with self.path.open() as feed_archive_opened:
                archive_tree = etree.parse(feed_archive_opened)
            archive_format = formats.FeedFormat.from_tree(self, remote_tree)
            if not isinstance(archive_format, type(remote_format)):  # pragma: no cover
                raise NotImplementedError(
                    f"Remote feed format, {type(remote_format).__name__!r}, is "
                    f"different from archive format, {type(archive_format).__name__!r}."
                )
        else:
            # First time requesting this feed, copy the remote feed, minus the items to
            # the archive and download the feed-level assets.
            logger.info(
                "Initializing feed in archive: %r -> %r",
                self.url,
                str(self.path),
            )
            # Duplicate the remote tree entirely so we can modify the archive's version
            # separately without changing the remote tree and affecting the rest of the
            # update logic.
            archive_tree = copy.deepcopy(remote_tree)
            archive_root = archive_tree.getroot()
            archived_items_parent = remote_format.get_items_parent(archive_root)
            # Remove all feed items from the copied tree.  As items are updated, the
            # modified versions of he items will be added back in during the rest of the
            # update logic.
            for archive_item_elem in remote_format.iter_items(archive_root):
                archived_items_parent.remove(archive_item_elem)

            # Consistent with initial download of the feed, only download assets for the
            # initial version of the feed.
            download_paths.extend(
                self.download_urls(
                    remote_format.iter_feed_download_urls(archive_root),
                ),
            )

            self.path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(
                "Writing initialized feed: %r",
                str(self.path),
            )
            etree.indent(archive_tree)
            archive_tree.write(str(self.path))

        return archive_tree

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
            if not download_path.exists() and url_result != self.url:
                download_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    download_response = self.download_url(
                        url_result,
                        download_relative,
                        download_path,
                    )
                except Exception:  # pragma: no cover, pylint: disable=broad-except
                    logger.exception(
                        "Problem downloading URL, removing from archive: %r -> %r",
                        url_result,
                        str(download_path),
                    )
                    download_path.unlink()
                    continue
                feedarchiver.archive.update_download_metadata(
                    download_response,
                    download_path,
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

    def download_url(self, url, download_relative, download_path):
        """
        Request a URL and stream the response to the file.
        """
        logger.info(
            "Downloading URL into archive: %r -> %r",
            url,
            str(download_relative),
        )

        content_length = 0
        with self.archive.requests.get(
            url,
            stream=True,
        ) as download_response:
            with download_path.open("wb") as download_opened:
                for chunk in download_response.iter_content(chunk_size=None):
                    download_opened.write(chunk)
                    content_length += len(chunk)

        if "Content-Length" in download_response.headers:
            try:
                remote_content_length = int(
                    download_response.headers["Content-Length"].strip(),
                )
            except ValueError:  # pragma: no cover
                pass
            else:
                if content_length != remote_content_length:  # pragma: no cover
                    logger.error(
                        "Downloaded content size different from remote: %r -> %r",
                        content_length,
                        remote_content_length,
                    )

        return download_response
