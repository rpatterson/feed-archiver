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
import pdb

from lxml import etree  # nosec B410

from . import utils
from .utils import mimetypes
from . import formats
from . import enclosures

logger = logging.getLogger(__name__)


class ArchiveFeed:
    """
    An RSS/Atom syndication feed in an archive.
    """

    URL_SCHEME_RE = re.compile(r"^(?P<scheme>[a-zA-Z][a-zA-Z0-9+.-]*):$")
    NAMESPACE = "https://github.com/rpatterson/feed-archiver"

    # Initialized when the configuration is loaded prior to update
    url = None
    enclosure_plugins = None
    enclosure_fallack_plugins = None
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
        self.enclosure_plugins = self.archive.enclosure_plugins[:]
        self.enclosure_fallack_plugins = self.archive.enclosure_fallack_plugins[:]
        enclosure_plugins, enclosure_fallack_plugins = enclosures.load_plugins(
            self,
            self.config,
        )
        self.enclosure_plugins.extend(enclosure_plugins)
        self.enclosure_fallack_plugins.extend(enclosure_fallack_plugins)

    # Sub-commands

    # TODO: Refactor to reduce complexity and improve readability and testibility
    def update(  # noqa: MC0001
        self,
    ):  # pylint: disable=too-many-locals,too-many-statements,too-many-branches
        """
        Request the URL of one feed in the archive and update contents accordingly.
        """
        logger.debug("Requesting feed: %r", self.url)
        remote_response = self.archive.client.get(self.url)
        # Maybe update the extension based on the headers
        self.path = self.archive.root_path / self.archive.response_to_path(
            remote_response,
        )
        remote_tree = self.load_remote_tree(remote_response)
        remote_root = remote_tree.getroot()
        remote_format = formats.FeedFormat.from_tree(self, remote_tree)

        # Assemble the archive version of the feed XML
        download_paths = {}
        archive_tree = self.get_archive_tree(
            remote_tree,
            download_paths,
            remote_format=remote_format,
        )
        archive_root = archive_tree.getroot()
        archived_items_parent = remote_format.get_items_parent(archive_root)

        remote_item_elems = list(remote_format.iter_items(remote_root))
        archive_item_elems = list(remote_format.iter_items(archive_root))
        if (len(remote_item_elems) - len(archive_item_elems)) > 4:
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

                item_download_paths = self.download_item_enclosures(
                    remote_format,
                    remote_item_elem,
                    remote_item_id,
                )
                if item_download_paths is None:
                    continue
                (
                    item_asset_paths,
                    item_enclosure_paths,
                ) = item_download_paths
                download_paths.update(item_asset_paths)
                download_paths.update(item_enclosure_paths)
                updated_items[remote_item_id] = remote_item_elem

                self.link_item_enclosures(
                    remote_format=remote_format,
                    feed_elem=archived_items_parent,
                    item_elem=remote_item_elem,
                    item_enclosure_paths=item_enclosure_paths,
                )

                archived_items_parent.insert(first_item_idx, remote_item_elem)
                # Pretty format the feed for readability
                etree.indent(archive_tree)
                # Update the archived feed file
                archive_tree.write(str(self.path))

        update_download_metadata(remote_response, self.path)

        if updated_items or download_paths:
            return list(updated_items.keys()), {
                # Return values fit for CLI output
                download_url: str(download_path)
                for download_url, download_path in download_paths.items()
            }
        return None

    # TODO: Refactor to reduce complexity and improve readability and testibility
    def relink(self):  # noqa: MC0001
        """
        Re-link enclosures to the correct locations for this feed.
        """
        # Parse this feed's archive XML
        self.path = self.find_archive_path()
        archive_tree = self.load_archive_tree()
        archive_format = formats.FeedFormat.from_tree(self, archive_tree)
        attr_prefixes = [
            f"{{{self.NAMESPACE}}}enclosure-link-",
            # BBB: old format compatibility
            f"{{{self.NAMESPACE}}}content-link-",
        ]

        # Update the links for each item in this feed
        is_modified = False
        linked_enclosures = {}
        for archive_item_elem in archive_format.iter_items(archive_tree.getroot()):
            item_enclosure_paths = {}
            for url_result in formats.all_xpaths_results(
                archive_item_elem,
                archive_format.DOWNLOAD_ITEM_ENCLOSURE_URLS_XPATHS,
            ):
                for attr, attr_value in list(url_result.getparent().attrib.items()):
                    for attr_prefix in attr_prefixes:
                        if attr.startswith(attr_prefix):
                            break
                    else:
                        continue
                    enclosure_path = pathlib.Path(attr_value)
                    if enclosure_path.is_symlink():
                        logger.info(
                            "Deleting existing enclosure link: %r -> %r",
                            str(enclosure_path),
                            str(os.readlink(enclosure_path)),
                        )
                        enclosure_path.unlink()
                    del url_result.getparent().attrib[attr]
                    is_modified = True
                item_enclosure_paths[url_result] = pathlib.Path(
                    urllib.parse.unquote(
                        urllib.parse.urlsplit(url_result).path.lstrip("/"),
                    ),
                )
            item_enclosures = self.link_item_enclosures(
                remote_format=archive_format,
                feed_elem=archive_format.get_items_parent(archive_tree.getroot()),
                item_elem=archive_item_elem,
                item_enclosure_paths=item_enclosure_paths,
            )
            if item_enclosures:
                is_modified = True
            if is_modified:  # pragma: no cover
                # Pretty format the feed for readability
                etree.indent(archive_tree)
                # Update the archived feed file
                archive_tree.write(str(self.path))
            linked_enclosures.update(
                (
                    url_result,
                    # Make results JSON serializable for CLI stdout
                    [str(enclosure_path) for enclosure_path in enclosure_paths],
                )
                for url_result, enclosure_paths in item_enclosures.items()
            )
        if linked_enclosures:
            return linked_enclosures
        return None

    # Other methods

    def download_item_enclosures(self, remote_format, remote_item_elem, remote_item_id):
        """
        Download all the enclosures from a feed item.
        """
        item_asset_urls = formats.all_xpaths_results(
            remote_item_elem,
            remote_format.DOWNLOAD_ITEM_ASSET_URLS_XPATHS,
        )
        item_enclosure_urls = formats.all_xpaths_results(
            remote_item_elem,
            remote_format.DOWNLOAD_ITEM_ENCLOSURE_URLS_XPATHS,
        )
        try:
            # Download enclosures and assets only for this item.
            item_asset_paths = self.download_urls(
                item_asset_urls,
            )
            item_enclosure_paths = self.download_urls(
                item_enclosure_urls,
            )
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Problem downloading item URLs, continuing to next: %r",
                remote_item_id,
            )
            if utils.POST_MORTEM:  # pragma: no cover
                pdb.post_mortem()
            return None
        return item_asset_paths, item_enclosure_paths

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
        remote_root = etree.fromstring(  # nosec: B320
            remote_response.content,
            base_url=str(remote_response.url),
            parser=utils.XML_PARSER,
        )
        return etree.ElementTree(remote_root)

    def find_archive_path(self):
        """
        Locate this feed's file in the archive.
        """
        path = self.archive.root_path / self.archive.url_to_path(self.url)
        if not path.exists():
            archive_files = []
            for archive_file in path.parent.glob(f"{path.stem}.*"):
                guessed_type, _ = mimetypes.guess_type(archive_file)
                if guessed_type is not None and (
                    guessed_type.endswith("/xml") or guessed_type.endswith("+xml")
                ):
                    archive_files.append(archive_file)
            if not archive_files:
                raise ValueError(f"Could not locate feed in archive: {self.url}")
            if len(archive_files) > 1:
                logger.warning(
                    "Multiple XML files found for feed, using first: %s\n%s",
                    self.url,
                    "\n  ".join([str(archive_file) for archive_file in archive_files]),
                )
            path = archive_files[0]
        return path

    def load_archive_tree(self):
        """
        Parse the local feed XML in the archive and return the tree.
        """
        archive_tree = None
        if (
            not self.archive.recreate
            and self.path.exists()
            and self.path.read_text().strip()
        ):
            logger.debug("Parsing archive XML: %r", self.url)
            with self.path.open() as feed_archive_opened:
                # Try to parse the local archive version of the feed if possible.  If
                # there are errors parsing it, then treat it as if it's the first time
                # archiving this feed.
                try:
                    archive_tree = etree.parse(  # nosec B320
                        feed_archive_opened,
                        parser=utils.XML_PARSER,
                    )
                except SyntaxError:
                    logger.exception(
                        "Unhandled exception parsing archive feed: %r",
                        self.url,
                    )
                    if utils.POST_MORTEM:  # pragma: no cover
                        pdb.post_mortem()
        return archive_tree

    def get_archive_tree(self, remote_tree, download_paths, remote_format=None):
        """
        Parse the archive feed XML if it exists or initialize an empty archive feed.

        If there is no local feed XML in the archive, such as the first time the feed is
        updated, then initialize the archive tree from the remote tree.

        Also do any pre-processing needed to start updating the archive.
        """
        archive_tree = self.load_archive_tree()
        if archive_tree is not None:
            if remote_format is not None:  # pragma: no cover
                archive_format = formats.FeedFormat.from_tree(self, archive_tree)
                if not isinstance(
                    archive_format,
                    type(remote_format),
                ):  # pragma: no cover
                    raise NotImplementedError(
                        f"Remote feed format, {type(remote_format).__name__!r}, is "
                        "different from archive format, "
                        f"{type(archive_format).__name__!r}."
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

    # TODO: Refactor to reduce complexity and improve readability and testibility
    def download_urls(  # noqa: MC0001
        self,
        url_results,
    ):  # pylint: disable=too-many-branches
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
                except Exception as exc:  # pylint: disable=broad-except
                    excs[url_result] = exc
                    logger.exception(
                        "Problem downloading URL, removing from archive: %r",
                        url_result,
                    )
                    if download_path is not None:  # pragma: no cover
                        download_path.unlink()
                    if utils.POST_MORTEM:  # pragma: no cover
                        pdb.post_mortem()
                    continue
                downloaded_paths[url_result] = download_path.relative_to(
                    self.archive.root_path,
                )

            # Update the URL in the feed XML to the relative archive path.
            # Update only after successful download to minimize inconsistent state on
            # errors.
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

        if excs:
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
        with self.archive.client.stream(
            "GET",
            url_split.geturl(),
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
            with download_path.open("wb") as download_opened:
                for data in download_response.iter_bytes():
                    download_opened.write(data)

        update_download_metadata(download_response, download_path)

        return download_path

    def link_item_enclosures(
        self,
        remote_format,
        feed_elem,
        item_elem,
        item_enclosure_paths,
    ):
        """
        Link item enclosures into media library hierarchies using plugins.
        """
        link_paths = {}
        if not self.enclosure_plugins and not self.enclosure_fallack_plugins:
            # Avoid unnecessary work when no link plugins are configured, particularly
            # parsing the item with `feedparser`.
            return link_paths

        feed_parsed = utils.parse_item_feed(remote_format, feed_elem, item_elem)
        (item_parsed,) = feed_parsed.entries
        for (
            url_result,
            enclosure_path,
        ) in item_enclosure_paths.items():
            link_idx = 0
            for enclosure_plugin in self.enclosure_plugins:
                for link_path in self.list_plugin_enclosure_links(
                    feed_elem,
                    feed_parsed,
                    item_elem,
                    item_parsed,
                    url_result,
                    enclosure_path,
                    enclosure_plugin,
                ):
                    link_paths.setdefault(url_result, []).append(
                        self.link_plugin_file(
                            url_result,
                            enclosure_path,
                            link_path,
                            link_idx,
                        )
                    )
                    link_idx += 1
            if link_idx > 0:
                # At least one plugin linked the enclosure, skip the fallbacks
                continue
            # Link and fallback configurations for this enclosure
            for enclosure_plugin in self.enclosure_fallack_plugins:
                for link_path in self.list_plugin_enclosure_links(
                    feed_elem,
                    feed_parsed,
                    item_elem,
                    item_parsed,
                    url_result,
                    enclosure_path,
                    enclosure_plugin,
                ):
                    link_paths.setdefault(url_result, []).append(
                        self.link_plugin_file(
                            url_result,
                            enclosure_path,
                            link_path,
                            link_idx,
                        )
                    )
                    link_idx += 1
        return link_paths

    def list_plugin_enclosure_links(
        self,
        feed_elem,
        feed_parsed,
        item_elem,
        item_parsed,
        url_result,
        enclosure_path,
        enclosure_plugin,
    ):  # pylint: disable=too-many-arguments
        """
        Return the links for an individual enclosure and plugin.
        """
        kwargs = {}
        match = None
        if "match-re" in enclosure_plugin.config:
            match_kwargs = locals().copy()
            del match_kwargs["self"]
            match = self.link_item_plugin_match(**match_kwargs)
            if match is None:
                return []
            kwargs.update(match.groupdict())

        # Delegate to the plugin
        logger.debug(
            "Linking item enclosure with %r plugin: %s",
            type(enclosure_plugin),
            str(enclosure_path),
        )
        try:
            link_strs = enclosure_plugin(
                archive_feed=self,
                feed_elem=feed_elem,
                feed_parsed=feed_parsed,
                item_elem=item_elem,
                item_parsed=item_parsed,
                url_result=url_result,
                enclosure_path=enclosure_path,
                match=match,
                **kwargs,
            )
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Problem linking item enclosure with %r, continuing to next: %s",
                type(enclosure_plugin),
                str(enclosure_path),
            )
            if utils.POST_MORTEM:  # pragma: no cover
                pdb.post_mortem()
            link_strs = []
        if link_strs is None:  # pragma: no cover
            # Plugin handled any linking itself
            link_strs = []
        if isinstance(link_strs, str):  # pragma: no cover
            link_strs = [link_strs]
        # Filter out duplicate paths but preserve order
        uniq_link_strs = []
        for enclosure_link_str in link_strs:
            if enclosure_link_str not in uniq_link_strs:
                uniq_link_strs.append(enclosure_link_str)
        return [
            self.archive.root_path
            / pathlib.Path(
                utils.quote_path(enclosure_link_str),
            )
            for enclosure_link_str in uniq_link_strs
        ]

    def link_item_plugin_match(self, **kwargs):
        """
        If configured, check for a regular expression match for a feed item enclosure.
        """
        enclosure_plugin = kwargs["enclosure_plugin"]
        kwargs["self"] = self
        try:
            match_string = eval(  # nosec B307, pylint: disable=eval-used
                f"f{enclosure_plugin.config['match-string']!r}",
                globals(),
                kwargs,
            )
        except Exception:  # pylint: disable=broad-except
            logger.exception(
                "Problem expanding `match-string` template for %r: %r",
                type(enclosure_plugin),
                enclosure_plugin.config["match-string"],
            )
            if utils.POST_MORTEM:  # pragma: no cover
                pdb.post_mortem()
            return None
        try:
            match = enclosure_plugin.config["match-re"].match(match_string)
        except Exception:  # pragma: no cover, pylint: disable=broad-except
            logger.exception(
                "Problem matching `match-pattern` for %r: %r",
                type(enclosure_plugin),
                enclosure_plugin.config["match-string"],
            )
            if utils.POST_MORTEM:  # pragma: no cover
                pdb.post_mortem()
            return None
        if match is None:
            logger.debug(
                "The %r plugin `match-pattern` did not match: %r",
                type(enclosure_plugin),
                match_string,
            )
            return None
        return match

    def link_plugin_file(
        self,
        url_result,
        enclosure_archive_relative,
        link_path,
        link_idx,
    ):
        """
        Link an item enclosure to a filesystem path returned by a plugin.
        """
        # Make the link relative
        enclosure_link_target = pathlib.Path(
            os.path.relpath(
                self.archive.root_path / enclosure_archive_relative,
                link_path.parent,
            ),
        )

        # Append numerical index if there are multiple enclosure downloads for this
        # item.
        enclosure_link_stem = link_path.stem
        enclosure_index = 0
        while os.path.lexists(link_path):
            if link_path.is_symlink() and os.readlink(link_path) == str(
                enclosure_link_target
            ):
                logger.debug(
                    "Duplicate item URL, skip enclosure link: %r -> %r",
                    str(link_path),
                    str(enclosure_link_target),
                )
                break
            enclosure_index += 1
            link_path = link_path.with_name(
                enclosure_link_stem[
                    : self.archive.root_stat.f_namemax
                    - (len(link_path.suffix) + len(str(enclosure_index)))
                ]
                + str(enclosure_index)
                + link_path.suffix,
            )
        else:
            logger.info(
                "Linking item enclosure: %r -> %r",
                str(link_path),
                str(enclosure_link_target),
            )
            link_path.parent.mkdir(parents=True, exist_ok=True)
            link_path.symlink_to(enclosure_link_target)

        url_result.getparent().attrib[
            f"{{{self.NAMESPACE}}}enclosure-link-{link_idx}"
        ] = str(link_path)
        return link_path


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
