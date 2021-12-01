"""
An archive of RSS/Atom syndication feeds.
"""

import os
import pathlib
import mimetypes
import urllib.parse
import csv
import email
import cgi
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
        url_relative = split_url.path.lstrip("/")
        # Add explicit index page basename if the URL points to a directory
        if url_relative.endswith("/"):
            url_relative += self.INDEX_BASENAME
        # Use `pathlib.PurePosixPath` to split on forward slashes in the URL regardless
        # of what the path separator is for this platform.
        url_path = pathlib.PurePosixPath(url_relative)
        archive_path = pathlib.PurePosixPath(
            urllib.parse.quote(split_url.scheme),
            urllib.parse.quote(split_url.netloc),
            # Place the query and fragment from the URL before the extension/suffix in
            # the path
            url_path.with_stem(
                urllib.parse.quote(
                    split_url._replace(
                        scheme="",
                        netloc="",
                        path=url_path.stem,
                    ).geturl(),
                )
            ),
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

    def update_download_metadata(self, download_response, download_path):
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

        # Create a symlink with the most appropriate basename from the redirect chain
        redirect_chain = [download_response]
        redirect_chain.extend(reversed(download_response.history))
        for history_response in redirect_chain:
            history_response_path = self.url_to_path(history_response.request.url)

            # Always use an explicit filename from the headers if available
            if "Content-Disposition" in history_response.headers:
                _, disposition_params = cgi.parse_header(
                    history_response.headers["Content-Disposition"],
                )
                if "filename" in disposition_params:
                    basename = disposition_params["filename"]
                    break

            # If there's no explicit filename, then see if the basename of he request
            # path matches the MIME type from the response headers if present.
            if "Content-Type" in history_response.headers:
                mime_type, _ = cgi.parse_header(
                    history_response.headers["Content-Type"],
                )
                suffixs = mimetypes.guess_all_extensions(mime_type, strict=False)
                history_response_path = self.url_to_path(history_response.request.url)
                if history_response_path.suffix in suffixs:
                    basename = history_response_path.name
                    break

        else:
            # Fallback to the basename of the most recent request, adding an extension
            # if a MIME type is provided.  Note that this is easily confused if the
            # basename of the URL contains a dot.
            history_response = download_response
            history_response_path = self.url_to_path(history_response.request.url)
            basename = history_response_path.name
            if (
                not history_response_path.suffix
                and "Content-Type" in history_response.headers
            ):
                mime_type, _ = cgi.parse_header(
                    history_response.headers["Content-Type"],
                )
                suffix = mimetypes.guess_extension(mime_type, strict=False)
                if suffix:
                    basename += suffix

        symlink_path = history_response_path.with_name(basename)
        if not symlink_path.exists() and symlink_path != download_path:
            logger.info(
                "Symlinking download to basename: %r -> %r",
                str(download_path),
                str(symlink_path),
            )
            symlink_path.parent.mkdir(parents=True, exist_ok=True)
            symlink_path.symlink_to(download_path)
