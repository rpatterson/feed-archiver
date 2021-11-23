"""
An archive of RSS/Atom syndication feeds.
"""

import pathlib
import urllib.parse
import csv
import logging

import requests

from . import feed

logger = logging.getLogger(__name__)


class Archive:
    """
    An archive of RSS/Atom syndication feeds.
    """

    INDEX_BASENAME = "index.html"

    FEED_CONFIGS_BASENAME = ".feed-archiver.csv"
    FEED_URL_FIELD = "Feed URL"

    def __init__(self, root_dir):
        """
        Instantiate a representation of an archive from a file-system path.
        """
        self.root_path = pathlib.Path(root_dir)
        self.config_path = self.root_path / self.FEED_CONFIGS_BASENAME
        assert (
            self.config_path.is_file()
        ), f"Feeds definition path is not a file: {self.config_path}"
        self.archive_feeds = {}
        self.requests = requests.Session()

    def url_to_path(self, url):
        """
        Escape the URL to a safe file-system path within the archive.
        """
        split_url = urllib.parse.urlsplit(url)
        # Want a relative path, strip the leading, root slash
        relative_url_path = split_url.path.lstrip("/")
        if relative_url_path.endswith("/"):
            relative_url_path += self.INDEX_BASENAME
        split_path = split_url._replace(
            # Only want the path, empty scheme and host
            scheme="",
            netloc="",
            path=relative_url_path,
        )
        # Use `pathlib.PurePosixPath` to split on forward slashes in the URL regardless
        # of what the path separator is for this platform
        archive_path = pathlib.PurePosixPath(
            urllib.parse.quote(split_url.scheme),
            urllib.parse.quote(split_url.netloc),
            urllib.parse.quote(split_path.geturl()),
        )
        return self.root_path / archive_path

    def path_to_url(self, path):
        """
        Un-escape the safe file-system path within the archive to a URL.
        """
        # Also accept strings
        path = pathlib.Path(path)
        basename = path.name
        if basename == self.INDEX_BASENAME:
            path = path.parent
        archive_path = path.relative_to(self.root_path)
        url_path = str(
            pathlib.PurePosixPath(
                *[urllib.parse.unquote(part) for part in archive_path.parts[2:]]
            )
        )
        if basename == self.INDEX_BASENAME:
            url_path += "/"
        split_url = urllib.parse.SplitResult(
            scheme=urllib.parse.unquote(archive_path.parts[0]),
            netloc=urllib.parse.unquote(archive_path.parts[1]),
            path=url_path,
            query="",
            fragment="",
        )
        return split_url.geturl()

    def update(self):
        """
        Request the URL of each feed in the archive and update contents accordingly.
        """
        updated_feeds = {}
        logger.info(
            "Retrieving feed configurations: %r",
            str(self.config_path),
        )
        with self.config_path.open() as feeds_opened:
            # We use CSV for the definition of archive feeds because many podcast
            # addicts may have hundreds of feed "subscriptions" so there may be real
            # value to using a format that users can open in very common tools such as
            # spreadsheet applications.  That said, in real world usage there may come
            # to be use cases that are more important to support that require a
            # different format, so open an issue and make your case if you have one.
            feed_reader = csv.DictReader(feeds_opened)
            # Use the column with the same label as the docs if present, otherwise use
            # the first field.
            feed_url_field = self.FEED_URL_FIELD
            if feed_url_field not in feed_reader.fieldnames:  # pragma: no cover
                feed_url_field = feed_reader.fieldnames[0]
            for feed_config in feed_reader:
                # Try to encapsulate all CSV implementation details here, avoid putting
                # anywhere else such as the `feed.ArchiveFeed` class.
                feed_url = feed_config[feed_url_field]
                archive_feed = self.archive_feeds[feed_url] = feed.ArchiveFeed(
                    archive=self,
                    config=feed_config,
                    url=feed_url,
                )
                try:
                    updated_items = archive_feed.update()
                except Exception:  # pragma: no cover, pylint: disable=broad-except
                    logger.exception(
                        "Unhandled exception updating feed: %r",
                        feed_url,
                    )
                    continue
                if updated_items:
                    updated_feeds[feed_url] = updated_items
        return updated_feeds
