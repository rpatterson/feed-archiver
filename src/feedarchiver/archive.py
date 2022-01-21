"""
An archive of RSS/Atom syndication feeds.
"""

import pathlib
import mimetypes
import urllib.parse
import cgi
import logging

import yaml
import requests

import feedarchiver
from . import feed
from . import linkpaths

logger = logging.getLogger(__name__)


class Archive:
    """
    An archive of RSS/Atom syndication feeds.
    """

    INDEX_BASENAME = "index.html"

    FEED_CONFIGS_BASENAME = ".feed-archiver.yml"

    # Initialized when the configuration is loaded prior to update
    global_config = None
    link_path_plugins = None
    # The default base URL for assembling absolute URLs
    url = None
    archive_feeds = None

    def __init__(self, root_dir):
        """
        Instantiate a representation of an archive from a file-system path.
        """
        self.root_path = pathlib.Path(root_dir)
        self.config_path = self.root_path / self.FEED_CONFIGS_BASENAME
        assert (
            self.config_path.is_file()
        ), f"Feeds definition path is not a file: {self.config_path}"
        self.requests = requests.Session()

    def load_config(self):
        """
        Read and deserialize the archive feed configs and do necessary pre-processing.
        """
        logger.debug(
            "Retrieving feed configurations: %r",
            str(self.config_path),
        )
        with self.config_path.open() as feeds_opened:
            archive_config = yaml.safe_load(feeds_opened)

        # The first row after the header defines defaults and/or global options
        self.global_config = archive_config["defaults"]
        self.url = self.global_config["base-url"]
        self.link_path_plugins = list(linkpaths.load_plugins(self, self.global_config))

        feed_configs = archive_config["feeds"]
        if not feed_configs:  # pragma: no cover
            raise ValueError(f"No feeds defined: {str(self.config_path)!r}")

        self.archive_feeds = []
        for feed_config in feed_configs:
            archive_feed = feed.ArchiveFeed(
                archive=self,
                config=feed_config,
            )
            archive_feed.load_config()
            self.archive_feeds.append(archive_feed)

    def response_to_path(self, url_response, url_result=None):
        """
        Derive the best archive path to represent the given remote URL request response.

        The goals in order of importance are:
        1. Ensure a unique filesystem path for each URL in order to avoid clashes such
           that one download doesn't overwrite another.
        2. Ensure that responses for the archived path from a static site server are as
           correct and well formed as possible, primarily that the extension matches the
           `Content-Type`.
        3. Ensure that derived paths are compatible with most common filesystems.
        4. Try to derive paths that are as human readable as possible given the above.

        Currently this just involves adding or correcting the suffix/extension if it
        doesn't match a `Content-Type` header.
        """
        url_path = self.url_to_path(url_response.request.url)
        mime_type = None

        # First try to get the MIME type from the response headers
        if url_response.headers.get("Content-Type"):
            mime_type, _ = cgi.parse_header(url_response.headers["Content-Type"])

        # If there's no MIME type in the the response headers, fallback to the element's
        # attribute if available
        if (
            not mime_type
            and hasattr(url_result, "getparent")
            and url_result.getparent().attrib.get("type")
        ):
            mime_type, _ = cgi.parse_header(url_result.getparent().attrib["type"])

        # Fix the suffix/extension if the MIME type doesn't match
        guessed_type, _ = mimetypes.guess_type(url_path.suffix)
        if mime_type and (
            not url_path.suffix
            or (guessed_type is not None and guessed_type != mime_type)
        ):
            # Header doesn't match the extension, guess the most correct extension
            suffix = mimetypes.guess_extension(mime_type, strict=False)
            if suffix:
                url_path = url_path.with_suffix(suffix)

        return url_path

    def url_to_path(self, url):
        """
        Escape the URL to a safe file-system path within the archive.
        """
        split_url = urllib.parse.urlsplit(url)
        # Want a relative path, strip the leading, root slash
        url_relative = split_url.path.lstrip("/")
        # Add explicit index page basename if the URL points to a directory
        if split_url.path.endswith("/"):
            url_relative += self.INDEX_BASENAME
        # Use `pathlib.PurePosixPath` to split on forward slashes in the URL regardless
        # of what the path separator is for this platform.
        url_path = pathlib.PurePosixPath(url_relative)
        archive_path = (
            pathlib.Path(
                urllib.parse.quote(split_url.scheme),
                urllib.parse.quote(split_url.netloc),
            )
            / pathlib.Path(
                *(urllib.parse.quote(part) for part in url_path.parent.parts)
            )
            / url_path.with_stem(
                # Place the query and fragment from the URL before the extension/suffix
                # in the path
                urllib.parse.quote(
                    split_url._replace(
                        scheme="", netloc="", path=url_path.stem
                    ).geturl(),
                )
            ).name
        )
        # Translate back to platform-native filesystem path separators/slashes
        return self.root_path / archive_path

    def path_to_url(self, path):
        """
        Un-escape the safe file-system path within the archive to a URL.
        """
        # Also accept strings
        path = pathlib.Path(path)
        # Strip explicit index page basename if the URL should point to a directory
        basename = path.name
        if basename == self.INDEX_BASENAME:
            path = path.parent
        # Strip the archive's path
        archive_path = path.relative_to(self.root_path)
        # Extract any URL query and/or fragment from before the suffix/extension
        stem_split = urllib.parse.urlsplit(urllib.parse.unquote(archive_path.stem))
        # Use `pathlib.PurePosixPath` to split on forward slashes in the URL regardless
        # of what the path separator is for this platform.
        url_parent_path = pathlib.PurePosixPath(
            *[urllib.parse.unquote(part) for part in archive_path.parts[2:-1]]
        )
        # Re-assemble the URL path without the query or fragment from the stem
        url_path = url_parent_path / f"{stem_split.path}{archive_path.suffix}"
        # Make explicit that the URL points to a directory if the path is index HTML
        url_relative = str(url_path)
        if basename == self.INDEX_BASENAME:
            url_relative += "/"
        # Re-assemble the rest of the archive path elements, preserving the query and
        # fragment extracted from the stem.
        split_url = stem_split._replace(
            scheme=urllib.parse.unquote(archive_path.parts[0]),
            netloc=urllib.parse.unquote(archive_path.parts[1]),
            path=url_relative,
        )
        return split_url.geturl()

    def update(self):
        """
        Request the URL of each feed in the archive and update contents accordingly.
        """
        self.load_config()
        updated_feeds = {}
        for archive_feed in self.archive_feeds:
            try:
                updated_items = archive_feed.update()
            except Exception:  # pragma: no cover, pylint: disable=broad-except
                logger.exception(
                    "Unhandled exception updating feed: %r",
                    archive_feed.url,
                )
                if feedarchiver.DEBUG:
                    raise
                continue
            if updated_items:
                updated_feeds[archive_feed.url] = updated_items
        return updated_feeds
