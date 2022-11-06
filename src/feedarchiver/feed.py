# pylint: disable=too-many-lines
"""
An RSS/Atom syndication feed in an archive.
"""

import os
import copy
import re
import urllib
import email.utils
import pathlib
import logging

from lxml import etree
from requests_toolbelt.downloadutils import stream

from . import utils
from . import formats
from . import linkpaths

logger = logging.getLogger(__name__)


class ArchiveFeed:
    """
    An RSS/Atom syndication feed in an archive.
    """

    URL_SCHEME_RE = re.compile(r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*):$")
    NAMESPACE = "https://github.com/rpatterson/feed-archiver"

    # Initialized when the configuration is loaded prior to update
    url = None
    link_path_plugins = None
    # Initialized on update from the response to the request for the URL from the feed
    # config in order to use response headers to derrive the best path.
    path = None

    def __init__(self, archive, config):
        """
        Instantiate a representation of an archive from a file-system path.
        """
        if utils.PYTHONTRACEMALLOC:  # pragma: no cover
            # Optionally initialize memory profiling
            self.tracemalloc_snapshot = utils.compare_memory_snapshots(archive)

        self.archive = archive
        self.config = config

    def load_config(self):
        """
        Pre-process and validate the feed config prior to running the actual update.
        """
        self.url = self.config["remote-url"]
        self.link_path_plugins = self.archive.link_path_plugins + list(
            linkpaths.load_plugins(self, self.config),
        )

    def update(
        self,
    ):  # pylint: disable=too-many-locals,too-many-statements,too-many-branches
        """
        Request the URL of one feed in the archive and update contents accordingly.
        """
        logger.info("Requesting feed: %r", self.url)
        remote_response = self.archive.requests.get(self.url)
        # Maybe update the extension based on the headers
        self.path = self.archive.root_path / self.archive.response_to_path(
            remote_response,
        )
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

        remote_item_elems = list(remote_format.iter_items(remote_root))
        archive_item_elems = list(remote_format.iter_items(archive_root))
        if (len(remote_item_elems) - len(archive_item_elems)) > 4:  # pragma: no cover
            logger.warning(
                "Many more items in remote than archive: %s > %s",
                len(remote_item_elems),
                len(archive_item_elems),
            )

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
            if not isinstance(item_sibling.tag, str):
                # Ignore comments or other unusual XML detritus/artifacts
                # `ValueError: Invalid tag name '<cyfunction Comment at 0x...>'`
                continue
            item_sibling_tag = etree.QName(item_sibling.tag).localname
            if item_sibling_tag.lower() == remote_format.ITEM_TAG:
                break
        else:
            first_item_idx += 1
        # Ensure that the order of new feed items is preserved
        remote_item_elems.reverse()
        for remote_item_elem in remote_item_elems:
            logger.debug(
                "Processing remote feed item:\n%s",
                etree.tostring(remote_item_elem).decode(),
            )
            if utils.PYTHONTRACEMALLOC:  # pragma: no cover
                # Optionally compare memory consumption
                self.tracemalloc_snapshot = utils.compare_memory_snapshots(self)

            remote_item_id = remote_format.get_item_id(remote_item_elem)
            if remote_item_id in archived_item_ids:
                # This item was already seen in the archived feed, we don't need to
                # update the archive or search further in the archived feed.
                logger.debug(
                    "Skipping remote feed item already in archived feed: %r",
                    remote_item_id,
                )
                continue
            for archived_item_elem in archive_item_elems:
                archived_item_ids.add(remote_format.get_item_id(archived_item_elem))
                if remote_item_id in archived_item_ids:
                    # Found this item in the archived feed, we don't need to update the
                    # archive and we can stop searching the archived feed for now.
                    # Optimization for the common case where a feed only contains the
                    # most recent items ATM but accrues a lot of items in the archive
                    # over time.
                    logger.debug(
                        "Skipping remote feed item already in archived feed: %r",
                        remote_item_id,
                    )
                    break
            else:
                # The remote item ID was not found in the archived feed, update the feed
                # by adding this remote item.
                logger.info(
                    "Adding feed item to archive: %r -> %r",
                    remote_item_id,
                    str(self.path),
                )

                item_download_paths = self.download_item_content(
                    remote_format,
                    remote_item_elem,
                    remote_item_id,
                )
                if item_download_paths is None:  # pragma: no cover
                    continue
                (
                    item_download_asset_paths,
                    item_download_content_paths,
                ) = item_download_paths
                download_paths.update(item_download_asset_paths)
                download_paths.update(item_download_content_paths)
                updated_items[remote_item_id] = remote_item_elem

                self.link_item_content(
                    feed_elem=archived_items_parent,
                    item_elem=remote_item_elem,
                    item_content_paths=item_download_content_paths,
                )

                archived_items_parent.insert(first_item_idx, remote_item_elem)
                if updated_items or download_paths:  # pragma: no cover
                    # Pretty format the feed for readability
                    etree.indent(archive_tree)
                    # Update the archived feed file
                    archive_tree.write(str(self.path))

        update_download_metadata(remote_response, self.path)

        return list(updated_items.keys()), download_paths

    def download_item_content(self, remote_format, remote_item_elem, remote_item_id):
        """
        Download all the enclosures/content from a feed item.
        """
        item_download_asset_urls = formats.all_xpaths_results(
            remote_item_elem,
            remote_format.DOWNLOAD_ITEM_ASSET_URLS_XPATHS,
        )
        item_download_content_urls = formats.all_xpaths_results(
            remote_item_elem,
            remote_format.DOWNLOAD_ITEM_CONTENT_URLS_XPATHS,
        )
        try:
            # Download enclosures and assets only for this item.
            item_download_asset_paths = self.download_urls(
                item_download_asset_urls,
            )
            item_download_content_paths = self.download_urls(
                item_download_content_urls,
            )
        except Exception:  # pragma: no cover, pylint: disable=broad-except
            logger.exception(
                "Problem downloading item URLs, continuing to next: %r",
                remote_item_id,
            )
            if utils.POST_MORTEM:
                raise
            return None
        return item_download_asset_paths, item_download_content_paths

    def update_self(self, feed_format, archive_root):
        """
        Update the `<link rel="self" href="..." ...` URL in the archived feed.

        Use the absolute URL so that it can be used as a base URL for other URLs in the
        feed XML.
        """
        archive_base_url_split = urllib.parse.urlsplit(
            self.config.get("base-url") or self.archive.global_config["base-url"]
        )
        base_url_path = pathlib.PurePosixPath(
            archive_base_url_split.path
        ) / urllib.parse.quote(os.path.relpath(self.path, self.archive.root_path))
        base_url_split = archive_base_url_split._replace(path=str(base_url_path))
        for self_link_elem in feed_format.get_items_parent(archive_root).xpath(
            feed_format.SELF_LINK_XPATH
        ):
            self_link_elem.attrib["href"] = base_url_split.geturl()

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
        if not self.archive.recreate and self.path.exists():
            logger.debug("Parsing archive XML: %r", self.url)
            with self.path.open() as feed_archive_opened:
                archive_tree = etree.parse(feed_archive_opened)
            archive_format = formats.FeedFormat.from_tree(self, remote_tree)
            if not isinstance(archive_format, type(remote_format)):  # pragma: no cover
                raise NotImplementedError(
                    f"Remote feed format, {type(remote_format).__name__!r}, is "
                    f"different from archive format, {type(archive_format).__name__!r}."
                )
            archive_root = archive_tree.getroot()
            archived_items_parent = remote_format.get_items_parent(archive_root)
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
            try:
                archive_download_paths = self.download_urls(
                    formats.all_xpaths_results(
                        archive_root,
                        remote_format.DOWNLOAD_FEED_URLS_XPATHS,
                    ),
                )
            except Exception:  # pragma: no cover, pylint: disable=broad-except
                logger.exception(
                    "Problem downloading feed assets, continuing with items: %s",
                    self.url,
                )
            else:
                download_paths.update(archive_download_paths)

            self.path.parent.mkdir(parents=True, exist_ok=True)
            logger.debug(
                "Writing initialized feed: %r",
                str(self.path),
            )
            etree.indent(archive_tree)
            archive_tree.write(str(self.path))

        return archive_tree

    def download_urls(self, url_results):  # pylint: disable=too-many-branches
        """
        Escape URLs to archive paths, download if new, and update URLs.
        """
        downloaded_paths = {}
        excs = {}
        for url_result in url_results:
            if url_result == self.url:
                # The feed itself is handled in `self.update()`
                continue
            download_path = None
            if utils.PYTHONTRACEMALLOC:  # pragma: no cover
                # Optionally compare memory consumption
                self.tracemalloc_snapshot = utils.compare_memory_snapshots(self)
            if url_result in downloaded_paths:
                logger.debug("Duplicate URL, skipping download: %r", url_result)
                # Proceed below to update the URLs in the duplicate XML element
                download_path = self.archive.root_path / downloaded_paths[url_result]
            else:
                # Download the URL to the escaped local path in the archive
                try:
                    download_path = self.download_url(url_result)
                except (
                    Exception  # pylint: disable=broad-except
                ) as exc:  # pragma: no cover
                    excs[url_result] = exc
                    logger.exception(
                        "Problem downloading URL, removing from archive: %r",
                        url_result,
                    )
                    if download_path is not None:
                        download_path.unlink()
                    if utils.POST_MORTEM:  # pragma: no cover
                        raise
                    continue
                downloaded_paths[url_result] = download_path.relative_to(
                    self.archive.root_path,
                )

            # Update the URL in the feed XML to the relative archive path.
            # Update only after successful download to minimize inconsistent state on
            # errors.
            if hasattr(url_result, "getparent") and hasattr(url_result, "attrname"):
                url_parent = url_result.getparent()
                download_relative = downloaded_paths[url_result]
                if download_relative.name == self.archive.INDEX_BASENAME:
                    download_relative = download_relative.parent
                download_url_split = self.archive.url_split._replace(
                    # Let pathlib normalize the relative path
                    path=str(
                        pathlib.PurePosixPath(self.archive.url_split.path)
                        / urllib.parse.quote(str(download_relative))
                    ),
                )
                if url_result.attrname:
                    logger.debug(
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
                    logger.debug(
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

        if excs:  # pragma: no cover
            # Ensure the feed item is processed again if any problem occurred with with
            # it's downloads
            raise list(excs.values())[0]
        return downloaded_paths

    def resolve_url(self, url):
        """
        Resolve protocol-relative URLs and workaround other common malformations.
        """
        url_split = urllib.parse.urlsplit(url)
        netloc_scheme_match = self.URL_SCHEME_RE.match(url_split.netloc)
        if url_split.scheme and netloc_scheme_match:
            # Mal-formed repeated scheme URL, e.g.: `href="https://https://example.com"`
            url_split = urllib.parse.urlsplit(
                url_split._replace(scheme="", netloc="")
                ._replace(
                    scheme=netloc_scheme_match.group("scheme"),
                )
                .geturl()
            )
            logger.error(
                "Correcting invalid URL: %r -> %r",
                url,
                url_split.geturl(),
            )
        elif not url_split.scheme and not url_split.netloc:
            # Mal-formed host/netloc-only URL, e.g.: `href="example.com"`
            url_split = urllib.parse.urlsplit("//" + url_split.geturl())
            logger.error(
                "Correcting invalid URL: %r -> %r",
                url,
                url_split.geturl(),
            )
        if url_split.netloc and not url_split.scheme:
            # Protocol/scheme-relative URL, e.g.: `href="//example.com/path"`
            url_split = url_split._replace(
                scheme=urllib.parse.urlsplit(self.url).scheme,
            )
            logger.debug(
                "Resolving protocol-relative URL: %r -> %r",
                url,
                url_split.geturl(),
            )
        return url_split

    def download_url(self, url_result):
        """
        Request a URL and stream the response to the file.
        """
        logger.info("Downloading URL into archive: %r", url_result)
        url_split = self.resolve_url(url_result)
        with self.archive.requests.get(
            url_split.geturl(),
            stream=True,
        ) as download_response:
            download_path = self.archive.root_path / self.archive.response_to_path(
                download_response,
                url_result,
            )
            download_relative = download_path.relative_to(self.archive.root_path)
            if download_path.exists():
                logger.debug(
                    "Skipping download already in archive: %r",
                    str(download_relative),
                )
                return download_path
            logger.debug("Writing download into archive: %r", str(download_relative))
            download_path.parent.mkdir(parents=True, exist_ok=True)
            stream.stream_response_to_file(download_response, path=download_path)
        download_stat = download_path.stat()

        update_download_metadata(download_response, download_path)

        if (
            download_response.headers.get(
                "Content-Encoding",
                "binary",
            )
            .strip()
            .lower()
            == "binary"
            and "Content-Length" in download_response.headers
        ):
            try:
                remote_content_length = int(
                    download_response.headers["Content-Length"].strip(),
                )
            except ValueError:  # pragma: no cover
                pass
            else:
                if download_stat.st_size != remote_content_length:  # pragma: no cover
                    logger.error(
                        "Downloaded content size different from remote: %r -> %r",
                        download_stat.st_size,
                        remote_content_length,
                    )

        return download_path

    def link_item_content(
        self,
        feed_elem,
        item_elem,
        item_content_paths,
    ):  # pylint: disable=too-many-branches
        """
        Link item content/enclosures into media library hierarchies using plugins.
        """
        content_link_paths = {}
        for (
            url_result,
            content_archive_relative,
        ) in item_content_paths.items():
            basename = content_archive_relative.name
            link_idx = 0
            for link_path_plugin in self.link_path_plugins:
                for content_link_path in self.list_item_content_link_plugin_paths(
                    feed_elem,
                    item_elem,
                    url_result,
                    basename,
                    content_archive_relative,
                    link_path_plugin,
                ):
                    content_link_paths.setdefault(url_result, []).append(
                        self.link_plugin_file(
                            url_result,
                            content_archive_relative,
                            content_link_path,
                            link_idx,
                        )
                    )
                    link_idx += 1
        return content_link_paths

    def list_item_content_link_plugin_paths(
        self,
        feed_elem,
        item_elem,
        url_result,
        basename,
        content_archive_relative,
        link_path_plugin,
    ):  # pylint: disable=too-many-arguments
        """
        Return the content link paths for an individual download and plugin.
        """
        match = None
        if "match-re" in link_path_plugin.config:
            match_kwargs = locals().copy()
            del match_kwargs["self"]
            match = self.link_item_plugin_match(**match_kwargs)
            if match is None:
                return []

        # Delegate to the plugin
        logger.debug(
            "Linking item content with %r plugin: %s",
            type(link_path_plugin),
            str(content_archive_relative),
        )
        try:
            content_link_strs = link_path_plugin(
                archive_feed=self,
                feed_elem=feed_elem,
                item_elem=item_elem,
                url_result=url_result,
                basename=basename,
                match=match,
            )
        except Exception:  # pragma: no cover, pylint: disable=broad-except
            logger.exception(
                "Problem linking item content with %r, continuing to next: %s",
                type(link_path_plugin),
                str(content_archive_relative),
            )
            if utils.POST_MORTEM:  # pragma: no cover
                raise
            content_link_strs = []
        if content_link_strs is None:  # pragma: no cover
            # Plugin handled any linking itself
            content_link_strs = []
        if isinstance(content_link_strs, str):  # pragma: no cover
            content_link_strs = [content_link_strs]
        return [
            self.archive.root_path
            / pathlib.Path(
                utils.quote_path(content_link_str),
            )
            for content_link_str in content_link_strs
        ]

    def link_item_plugin_match(self, **kwargs):
        """
        If configured, check for a regular expression match for a feed item enclosure.
        """
        link_path_plugin = kwargs["link_path_plugin"]
        kwargs["self"] = self
        try:
            match_string = eval(  # pylint: disable=eval-used
                f"f{link_path_plugin.config['match-string']!r}",
                globals(),
                kwargs,
            )
        except Exception:  # pragma: no cover, pylint: disable=broad-except
            logger.exception(
                "Problem expanding `match-string` template for %r: %r",
                type(link_path_plugin),
                link_path_plugin.config["match-string"],
            )
            if utils.POST_MORTEM:  # pragma: no cover
                raise
            return None
        try:
            match = link_path_plugin.config["match-re"].match(match_string)
        except Exception:  # pragma: no cover, pylint: disable=broad-except
            logger.exception(
                "Problem matching `match-pattern` for %r: %r",
                type(link_path_plugin),
                link_path_plugin.config["match-string"],
            )
            if utils.POST_MORTEM:  # pragma: no cover
                raise
            return None
        if match is None:  # pragma: no cover
            logger.info(
                "The %r plugin `match-pattern` did not match: %r",
                type(link_path_plugin),
                match_string,
            )
            return None
        return match

    def link_plugin_file(
        self,
        url_result,
        content_archive_relative,
        content_link_path,
        link_idx,
    ):
        """
        Link an item content/enclosure to a filesystem path returned by a plugin.
        """
        # Make the link relative
        content_link_target = pathlib.Path(
            os.path.relpath(
                self.archive.root_path / content_archive_relative,
                content_link_path.parent,
            ),
        )

        # Append numerical index if there are multiple content downloads for this
        # item.
        content_link_stem = content_link_path.stem
        content_index = 0
        while os.path.lexists(content_link_path):
            if (
                content_link_path.is_symlink()
                and content_link_path.readlink() == content_link_target
            ):
                logger.debug(
                    "Duplicate item URL, skip content link: %r -> %r",
                    str(content_link_path),
                    str(content_link_target),
                )
                break
            content_index += 1
            content_link_path = content_link_path.with_stem(
                content_link_stem[
                    : self.archive.root_stat.f_namemax
                    - (len(content_link_path.suffix) + len(str(content_index)))
                ]
                + str(content_index),
            )
        else:
            logger.info(
                "Linking item content: %r -> %r",
                str(content_link_path),
                str(content_link_target),
            )
            content_link_path.parent.mkdir(parents=True, exist_ok=True)
            content_link_path.symlink_to(content_link_target)

        url_result.getparent().attrib[
            f"{{{self.NAMESPACE}}}content-link-{link_idx}"
        ] = str(content_link_path)
        return content_link_path

    def migrate(
        self, target_path
    ):  # pylint: disable=too-many-locals,too-many-branches,too-many-statements
        """
        Use archived feed XML to migrate items as they would be handled now.
        """
        # Request and parse the remote feed XML for the most current representation of
        # items that are still available in the remote.
        remote_response = self.archive.requests.get(self.url)
        remote_tree = self.load_remote_tree(remote_response)
        remote_root = remote_tree.getroot()
        remote_format = formats.FeedFormat.from_tree(self, remote_tree)

        # Find the old feed XML file in the original archive, starting with the oldest
        # possible version first
        for redirect_response in [remote_response] + list(
            reversed(remote_response.history),
        ):
            remote_response_relative = self.archive.response_to_path(
                remote_response,
                request=redirect_response.request,
            )
            # Try without extension as before working around MIME types issues
            orig_feed_relative = remote_response_relative.with_suffix("")
            self.path = self.archive.root_path / orig_feed_relative
            if self.path.is_file():  # pragma: no cover
                break
            # Fallback to the currenct/correct extension
            orig_feed_relative = remote_response_relative
            self.path = self.archive.root_path / orig_feed_relative
            if self.path.is_file():  # pragma: no cover
                break
        else:  # pragma: no cover
            raise ValueError(
                "Could not find original archive feed file from URL: "
                f"{self.url!r} -> {str(orig_feed_relative)!r}"
            )

        # Copy the feed XML to the location the current version of the code would
        # generate
        migrated_feed_relative = self.archive.response_to_path(remote_response)
        migrated_paths = {}
        migrated_feed_path = self.archive.migrate_path(
            target_path,
            orig_feed_relative,
            migrated_feed_relative,
            copy=True,
        )
        migrated_paths[self.url] = (str(self.path), str(migrated_feed_path))

        # Parse the feed XML in the target archive
        logger.debug("Parsing archive XML: %r", self.url)
        with migrated_feed_path.open() as migrated_feed_opened:
            archive_tree = etree.parse(migrated_feed_opened)
        archive_format = formats.FeedFormat.from_tree(self, archive_tree)
        archive_root = archive_tree.getroot()
        self_link_elems = archive_format.get_items_parent(archive_root).xpath(
            archive_format.SELF_LINK_XPATH,
        )

        remote_item_elems_list = list(remote_format.iter_items(remote_root))
        archive_item_elems = list(archive_format.iter_items(archive_root))
        if (
            len(remote_item_elems_list) - len(archive_item_elems)
        ) > 4:  # pragma: no cover
            logger.warning(
                "Many more items in remote than archive: %s > %s",
                len(remote_item_elems_list),
                len(archive_item_elems),
            )

        # Link feed-level downloads into the target archive
        migrated_paths.update(
            self.migrate_url_results(
                target_path,
                xpath_queries=archive_format.DOWNLOAD_FEED_URLS_XPATHS,
                archive_elem=archive_root,
                remote_elem=remote_root,
                exclude_url_elems=self_link_elems,
            ),
        )

        # Map remote items to their IDs for pairing with archive items
        remote_item_elems = {}
        for remote_item_elem in remote_item_elems_list:
            remote_item_elems[
                remote_format.get_item_id(remote_item_elem)
            ] = remote_item_elem

        # Link item-level downloads into the target archive
        archived_items_parent = archive_format.get_items_parent(archive_root)
        for archive_item_elem in archive_item_elems:
            archive_item_id = archive_format.get_item_id(archive_item_elem)
            remote_item_elem = remote_item_elems.get(archive_item_id)

            # Migrate item assets in the archive only
            migrated_paths.update(
                self.migrate_url_results(
                    target_path,
                    xpath_queries=archive_format.DOWNLOAD_ITEM_ASSET_URLS_XPATHS,
                    archive_elem=archive_item_elem,
                    remote_elem=remote_item_elem,
                ).items()
            )

            # Migrate item content in the archive and re-link
            migrated_content_paths = self.migrate_url_results(
                target_path,
                xpath_queries=archive_format.DOWNLOAD_ITEM_CONTENT_URLS_XPATHS,
                archive_elem=archive_item_elem,
                remote_elem=remote_item_elem,
            )
            migrated_paths.update(migrated_content_paths)
            # Remove content links prior to re-creating
            for item_content_url_result in formats.all_xpaths_results(
                archive_item_elem,
                archive_format.DOWNLOAD_ITEM_CONTENT_URLS_XPATHS,
            ):
                # Remove content links listed in the download's item XML namespace
                # attributes.
                content_elem = item_content_url_result.getparent()
                content_link_strs = []
                for attr_name, content_link_str in content_elem.attrib.items():
                    if not attr_name.startswith(f"{{{self.NAMESPACE}}}content-link-"):
                        continue
                    content_link_strs.append(content_link_str)
                    del content_elem.attrib[attr_name]
                # Remove content links that may be stale/old from previous versions of
                # the code
                content_archive_relative = pathlib.PurePosixPath(
                    urllib.parse.unquote(
                        urllib.parse.urlsplit(item_content_url_result).path.lstrip("/"),
                    ),
                )
                for link_path_plugin in self.link_path_plugins:
                    for content_link_path in self.list_item_content_link_plugin_paths(
                        archive_format.get_items_parent(archive_root),
                        archive_item_elem,
                        item_content_url_result,
                        content_archive_relative.name,
                        content_archive_relative,
                        link_path_plugin,
                    ):
                        content_link_str = str(content_link_path)
                        content_link_strs.extend(
                            [
                                # Fully unquoted
                                content_link_str,
                                # Double quoted path characters, single quoted others
                                urllib.parse.quote(
                                    utils.quote_path(content_link_str),
                                    safe="/ ",
                                ),
                                # Single quoted all characters
                                urllib.parse.quote(content_link_str, safe="/ "),
                                # Double quoted all characters
                                urllib.parse.quote(
                                    urllib.parse.quote(content_link_str, safe="/ "),
                                    safe="/ ",
                                ),
                                # Double quoted path characters
                                utils.quote_path(utils.quote_path(content_link_str)),
                            ]
                        )
                # Perform the actual deletion
                logger.debug(
                    "Cleaning up content link viriations:\n%s",
                    "\n".join(content_link_strs),
                )
                for content_link_str in content_link_strs:
                    content_link_path = pathlib.Path(content_link_str)
                    content_link_stem = content_link_path.stem
                    content_index = 0
                    while content_link_path.is_symlink():
                        logger.info(
                            "Removing content link: %r -> %r",
                            content_link_str,
                            str(content_link_path.readlink()),
                        )
                        content_link_path.unlink()
                        content_index += 1
                        # Missing the dash before the index
                        content_link_path = content_link_path.with_stem(
                            f"{content_link_stem}{str(content_index)}",
                        )
                        if content_link_path.is_symlink():
                            logger.info(
                                "Removing content link: %r -> %r",
                                content_link_str,
                                str(content_link_path.readlink()),
                            )
                            content_link_path.unlink()
                        content_link_path = content_link_path.with_stem(
                            f"{content_link_stem}-{str(content_index)}",
                        )
            # Re-apply current `link-path` plugins
            self.link_item_content(
                feed_elem=archived_items_parent,
                item_elem=archive_item_elem,
                item_content_paths={
                    archive_url_result: pathlib.Path(
                        target_file_path,
                    ).relative_to(target_path)
                    for archive_url_result, (
                        archive_file_path,
                        target_file_path,
                    ) in migrated_content_paths.items()
                },
            )

        # Pretty format the feed for readability
        etree.indent(archive_tree)
        # Update the archived feed file
        archive_tree.write(str(migrated_feed_path))

        return len(migrated_paths)

    def migrate_url_results(
        self,
        target_path,
        xpath_queries,
        archive_elem,
        remote_elem=None,
        exclude_url_elems=None,
    ):  # pylint: disable=too-many-arguments,too-many-locals
        """
        Reconcile the same XPath query URLs from both the remote and the archive.
        """
        archive_url_results = formats.all_xpaths_results(archive_elem, xpath_queries)
        remote_url_results = None
        if remote_elem is not None:  # pragma: no cover
            remote_url_results = formats.all_xpaths_results(remote_elem, xpath_queries)

        # Compare the 2 sets of XPath URL results
        if remote_url_results and len(remote_url_results) != len(
            archive_url_results
        ):  # pragma: no cover
            logger.warning(
                "Remote has different XPath results than the archive: %s != %s",
                len(archive_url_results),
                len(remote_url_results),
            )
            remote_url_results = None
        if remote_url_results:
            for archive_url_result_idx, archive_url_result in enumerate(
                archive_url_results,
            ):
                archive_url_elem = archive_url_result.getparent()
                remote_url_result = remote_url_results[archive_url_result_idx]
                remote_url_elem = remote_url_result.getparent()
                if archive_url_elem.tag != remote_url_elem.tag:  # pragma: no cover
                    logger.warning(
                        "Remote has different XPath results than the archive: %r",
                        archive_url_result,
                    )
                    remote_url_results = None
                    break

        # Perform the actual migrations
        if exclude_url_elems is None:
            exclude_url_elems = []
        file_paths = {}
        for archive_url_result_idx, archive_url_result in enumerate(
            archive_url_results,
        ):
            archive_url_elem = archive_url_result.getparent()
            for exclude_url_elem in exclude_url_elems:
                # Check if the parent element of the URL result is excluded
                if exclude_url_elem is archive_url_elem:
                    break
            else:
                remote_url_result = None
                if remote_url_results:  # pragma: no cover
                    remote_url_result = remote_url_results[archive_url_result_idx]
                migrated_file_paths = self.migrate_url_result(
                    target_path,
                    archive_url_result,
                    remote_url_result,
                )
                if migrated_file_paths is None:  # pragma: no cover
                    break
                archive_file_path, target_file_path = migrated_file_paths
                file_paths[archive_url_result] = (
                    str(archive_file_path),
                    str(target_file_path),
                )
        return file_paths

    def migrate_url_result(
        self,
        target_path,
        archive_url_result,
        remote_url_result=None,
    ):
        """
        Use `feed-archiver` XML attributes to migrate an individual URL.
        """
        # Lookup the original URL from the XML namespace attribute
        url_parent = archive_url_result.getparent()
        if remote_url_result is not None:
            remote_url = remote_url_result
        elif archive_url_result.attrname:  # pragma: no cover
            remote_url = url_parent.attrib[
                f"{{{self.NAMESPACE}}}attribute-{archive_url_result.attrname}"
            ]
        else:  # pragma: no cover
            remote_url = url_parent.attrib[f"{{{self.NAMESPACE}}}text"]
        remote_url_split = self.resolve_url(remote_url)
        target_relative_path = self.archive.url_to_path(
            remote_url_split.geturl(),
        )

        # Determine the path to the file in the archive
        archive_base_url_split = urllib.parse.urlsplit(
            self.config.get("base-url") or self.archive.global_config["base-url"],
        )
        archive_url_split = urllib.parse.urlsplit(archive_url_result)
        archive_relative_path = pathlib.PurePosixPath(
            urllib.parse.unquote(archive_url_split.path.lstrip("/")),
        )
        # Start with the oldest form, relative to the feed
        if (
            not archive_url_split.scheme and not archive_url_split.netloc
        ):  # pragma: no cover
            archive_file_path = self.path.parent / archive_relative_path
            archive_relative_path = archive_file_path.relative_to(
                self.archive.root_path,
            )
        # Newer, absolute URLs using `base-url` from the config
        elif (archive_url_split.scheme, archive_url_split.netloc) == (
            archive_base_url_split.scheme,
            archive_base_url_split.netloc,
        ):
            archive_relative_path = pathlib.PurePosixPath(
                urllib.parse.unquote(archive_url_split.path.lstrip("/")),
            )
            archive_file_path = self.archive.root_path / archive_relative_path
        else:  # pragma: no cover
            # Probably a download URL added to the remote feed since the original
            # archive was last updated
            logger.debug(
                "URL not downloaded in original archive: %r",
                archive_url_split.geturl(),
            )
            return None
        # Handle directory `index.html` files
        if archive_file_path.is_dir():
            archive_relative_path = archive_relative_path / self.archive.INDEX_BASENAME
            archive_file_path = archive_file_path / self.archive.INDEX_BASENAME
        else:
            target_relative_path = target_relative_path.with_suffix(
                archive_relative_path.suffix,
            )

        # Update the archived URL in the XML a
        target_relative_url_path = target_relative_path
        if target_relative_path.name == self.archive.INDEX_BASENAME:
            target_relative_url_path = target_relative_path.parent
        migrated_url_split = self.archive.url_split._replace(
            path=str(
                pathlib.PurePosixPath(self.archive.url_split.path)
                / urllib.parse.quote(str(target_relative_url_path)),
            ),
        )
        logger.info(
            "Updating download path: %r -> %r",
            str(archive_relative_path),
            str(target_relative_path),
        )
        if archive_url_result.attrname:
            url_parent.attrib[archive_url_result.attrname] = migrated_url_split.geturl()
        else:
            url_parent.text = migrated_url_split.geturl()

        # Link into the migrated archive unless it's already been linked by a redundant
        # item enclosure/content element.
        target_file_path = target_path / target_relative_path
        if not target_file_path.exists():
            target_file_path = self.archive.migrate_path(
                target_path,
                archive_relative_path,
                target_relative_path,
            )

        return archive_file_path, target_file_path


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
