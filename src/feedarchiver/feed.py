"""
An RSS/Atom syndication feed in an archive.
"""

import os
import copy
import urllib
import email.utils
import pathlib
import logging

from lxml import etree

from . import formats

logger = logging.getLogger(__name__)


class ArchiveFeed:
    """
    An RSS/Atom syndication feed in an archive.
    """

    NAMESPACE = "https://github.com/rpatterson/feed-archiver"

    # Initialized on update from the response to the request for the URL from the feed
    # config in order to use response headers to derrive the best path.
    path = None

    def __init__(self, archive, config, url):
        """
        Instantiate a representation of an archive from a file-system path.
        """
        self.archive = archive
        self.config = config
        self.url = url

    def update(self):  # pylint: disable=too-many-locals
        """
        Request the URL of one feed in the archive and update contents accordingly.
        """
        logger.info("Requesting feed: %r", self.url)
        remote_response = self.archive.requests.get(self.url)
        # Maybe update the extension based on the headers
        self.path = self.archive.response_to_path(remote_response)
        remote_tree = self.load_remote_tree(remote_response)
        remote_root = remote_tree.getroot()
        remote_format = formats.FeedFormat.from_tree(self, remote_tree)

        # Assemble the archive version of the feed XML
        download_paths = {}
        archive_tree = self.load_archive_tree(
            remote_format,
            remote_tree,
            download_paths,
        )
        archive_root = archive_tree.getroot()
        archived_items_parent = remote_format.get_items_parent(archive_root)
        archived_items = list(remote_format.iter_items(archive_root))

        logger.info(
            "Updating feed in archive: %r -> %r",
            self.url,
            str(self.path),
        )
        self.update_self(remote_format, archive_root)
        # Iterate through the remote feed to make updates to the archived feed as
        # appropriate.
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
                download_paths.update(item_download_paths)
                updated_items[remote_item_id] = remote_item_elem
                archived_items_parent.insert(first_item_idx, remote_item_elem)

        if updated_items or download_paths:
            # Pretty format the feed for readability
            etree.indent(archive_tree)
            # Update the archived feed file
            archive_tree.write(str(self.path))
        update_download_metadata(remote_response, self.path)

        return list(updated_items.keys()), download_paths

    def update_self(self, feed_format, archive_root):
        """
        Update the `<link rel="self" href="..." ...` URL in the archived feed.

        Use the absolute URL so that it can be used as a base URL for other URLs in the
        feed XML.
        """
        archive_url_field = self.archive.feed_config_fields[
            self.archive.FEED_ARCHIVE_URL_FIELD
        ]
        archive_base_url_split = urllib.parse.urlsplit(
            self.config.get(archive_url_field)
            or self.archive.global_config[archive_url_field]
        )
        archive_url_path = pathlib.PurePosixPath(
            archive_base_url_split.path
        ) / os.path.relpath(self.path, self.archive.root_path)
        archive_url_split = archive_base_url_split._replace(path=str(archive_url_path))
        for self_link_elem in feed_format.get_items_parent(archive_root).xpath(
            feed_format.SELF_LINK_XPATH
        ):
            self_link_elem.attrib["href"] = archive_url_split.geturl()

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
            download_paths.update(
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
        downloaded_paths = {}
        for url_result in url_results:
            if url_result == self.url:
                # The feed itself is handled in `self.update()`
                continue
            if url_result in downloaded_paths:
                logger.debug("Duplicate URL, skipping download: %r", url_result)
                # Proceed below to update the URLs in the duplicate XML element
                download_path = self.archive.root_path / downloaded_paths[url_result]
            else:
                # Download the URL to the escaped local path in the archive
                try:
                    download_path = self.download_url(url_result)
                except Exception:  # pragma: no cover, pylint: disable=broad-except
                    logger.exception(
                        "Problem downloading URL, removing from archive: %r -> %r",
                        url_result,
                        str(download_path),
                    )
                    download_path.unlink()
                    continue
                downloaded_paths[url_result] = download_path.relative_to(
                    self.archive.root_path,
                )

            # Update the URL in the feed XML to the relative archive path.
            # Update only after successful download to minimize inconsistent state on
            # errors.
            if hasattr(url_result, "getparent") and hasattr(url_result, "attrname"):
                url_parent = url_result.getparent()
                if download_path.name == self.archive.INDEX_BASENAME:
                    download_relative = download_path.parent
                else:
                    download_relative = download_path
                download_url_path = pathlib.PurePosixPath(
                    os.path.relpath(download_relative, self.path.parent),
                )
                download_url_split = urllib.parse.SplitResult(
                    # Make fully relative to the feed
                    scheme="",
                    netloc="",
                    # Let pathlib normalize the relative path
                    path=str(download_url_path),
                    # Archive paths should have not query or fragment
                    query="",
                    fragment="",
                )
                if url_result.attrname:
                    logger.info(
                        'Updating feed URL: <%s %s="%s"...>',
                        url_result.getparent().tag,
                        url_result.attrname,
                        download_url_split.geturl(),
                    )
                    # Store the original remote URL in a namespace attribute
                    url_parent.attrib[
                        f"{{{self.NAMESPACE}}}attribute-{url_result.attrname}"
                    ] = url_result
                    # Update the archived URL to the local, relative URL
                    url_parent.attrib[url_result.attrname] = download_url_split.geturl()
                else:
                    logger.info(
                        "Updating feed URL: <%s>%s</%s>",
                        url_result.getparent().tag,
                        download_url_split.geturl(),
                        url_result.getparent().tag,
                    )
                    # Store the original remote URL in a namespace attribute
                    url_parent.attrib[f"{{{self.NAMESPACE}}}text"] = url_result
                    # Update the URL in the archive XML to the local, relative URL
                    url_parent.text = download_url_split.geturl()
            else:  # pragma: no coverx
                raise NotImplementedError(
                    f"Escaping URLs in {type(url_result)!r} text nodes"
                    " not implemented yet",
                )

        return downloaded_paths

    def download_url(self, url_result):
        """
        Request a URL and stream the response to the file.
        """
        content_length = 0
        logger.info("Downloading URL into archive: %r", url_result)
        with self.archive.requests.get(
            url_result,
            stream=True,
        ) as download_response:
            download_path = self.archive.response_to_path(download_response, url_result)
            download_relative = download_path.relative_to(self.archive.root_path)
            if download_path.exists():
                logger.warning(
                    "Skipping download already in archive: %r",
                    str(download_relative),
                )
                return download_path
            logger.info("Writing download into archive: %r", str(download_relative))
            download_path.parent.mkdir(parents=True, exist_ok=True)
            with download_path.open("wb") as download_opened:
                for chunk in download_response.iter_content(chunk_size=None):
                    download_opened.write(chunk)
                    content_length += len(chunk)

        update_download_metadata(download_response, download_path)

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

        return download_path


def update_download_metadata(download_response, download_path):
    """
    Reflect any metdata that can be extracted from the respons in the download file.
    """
    # Set the filesystem modification datetime if the header is provided
    if "Last-Modified" in download_response.headers:
        last_modified = email.utils.parsedate_to_datetime(
            download_response.headers["Last-Modified"],
        )
        feed_stat = download_path.stat()
        os.utime(
            download_path,
            (feed_stat.st_atime, last_modified.timestamp()),
        )
        return last_modified

    return None
