"""
Tests for this feed archiver foundation or template.
"""

import os
import datetime
import pathlib
import mimetypes
import urllib.parse
import csv
import tempfile
import shutil
import email.utils
import unittest

from lxml import etree

import requests_mock

from .. import archive
from .. import feed


class FeedarchiverTestCase(
    unittest.TestCase,
):  # pylint: disable=too-many-instance-attributes
    """
    Constants and set-up used in all feed-archiver tests.
    """

    maxDiff = None

    # A date and time in the past all but guaranteed not to exist naturally in the
    # checkout.
    OLD_DATETIME = datetime.datetime(year=1980, month=11, day=25, hour=8, minute=31)
    # The relative path to the example/sample test data this test will use.
    # Default examples are copied from the Wikipedia page of each RSS/Atom syndication
    # XML format to represent the cleanest, simplest form of feeds.
    EXAMPLE_RELATIVE = pathlib.Path("simple")
    # Relative path to the feed XML content in the checkout test data to be used to mock
    # responses to requests for the remote feed URL.
    REMOTE_MOCK = pathlib.Path("orig")
    # Relative path that corresponds to the remote feed URL within the archive.
    FEED_ARCHIVE_STEM = "garply"
    FEED_ARCHIVE_SUFFIX = ".rss"
    FEED_ARCHIVE_QUERY = "?bar=qux%2Fbaz#corge"
    FEED_ARCHIVE_RELATIVE = pathlib.Path(
        "https",
        "foo-username%3Asecret%40grault.example.com",
        "feeds",
        f"{FEED_ARCHIVE_STEM}{urllib.parse.quote(FEED_ARCHIVE_QUERY)}"
        f"{FEED_ARCHIVE_SUFFIX}",
    )

    # Test data in the checkout that represents remote feed data
    REMOTES_PATH = pathlib.Path(__file__).parent / "remotes"
    # Test data in the checkout that represents local archived feed data.
    ARCHIVES_PATH = REMOTES_PATH.parent / "archives"

    def setUp(self):
        """
        Set up used in all feed-archiver tests.
        """
        super().setUp()

        # Mock HTTP/S requests:
        # https://requests-mock.readthedocs.io/en/latest/fixture.html#fixtures
        self.requests_mock = requests_mock.Mocker()
        self.addCleanup(self.requests_mock.stop)
        self.requests_mock.start()

        # Create a temporary directory for mutable test data
        self.tmp_dir = (
            tempfile.TemporaryDirectory(  # pylint: disable=consider-using-with
                suffix=self.EXAMPLE_RELATIVE.suffix,
                prefix=f"{self.EXAMPLE_RELATIVE.stem}-",
            )
        )
        self.addCleanup(self.tmp_dir.cleanup)

        # Use the example/sample test data basename to assemble the rest of the
        # filesystem paths used by the tests.
        self.remotes_path = self.REMOTES_PATH / self.EXAMPLE_RELATIVE
        self.archive_path = self.ARCHIVES_PATH / self.EXAMPLE_RELATIVE

        # Extract the feed URL from the CSV
        self.feed_configs_path = (
            self.archive_path / archive.Archive.FEED_CONFIGS_BASENAME
        )
        with open(self.feed_configs_path, encoding="utf-8") as feed_configs_opened:
            self.feed_configs_rows = list(csv.DictReader(feed_configs_opened))
        self.feed_url = self.feed_configs_rows[1]["Feed Remote URL"]

        # Copy the testing example feeds archive
        shutil.copytree(
            src=self.archive_path,
            dst=self.tmp_dir.name,
            dirs_exist_ok=True,
        )
        self.archive = archive.Archive(self.tmp_dir.name)
        self.archive.load_feed_configs()
        self.archive_feed = feed.ArchiveFeed(
            archive=self.archive,
            config=self.feed_configs_rows[1],
            url=self.feed_url,
        )
        self.feed_path = self.archive.root_path / self.FEED_ARCHIVE_RELATIVE

    def mock_remote(self, archive_feed, remote_mock=None):
        """
        Mock the request responses with the mock dir.

        The relative paths in the mock dir are un-escaped to URLs and used to create the
        request mocks for those URLs.
        """
        if remote_mock is None:
            remote_mock = self.REMOTE_MOCK

        request_mocks = {}
        remote_mock_path = self.REMOTES_PATH / self.EXAMPLE_RELATIVE / remote_mock
        for root, _, files in os.walk(remote_mock_path, followlinks=True):
            if {
                mock_root_part
                for mock_root_part in pathlib.Path(root).parts
                if mock_root_part.endswith("~")
            }:  # pragma: no cover
                continue
            for mock_basename in files:
                if mock_basename.endswith("~"):  # pragma: no cover
                    continue
                mock_path = pathlib.Path(root) / mock_basename
                mock_stat = mock_path.stat()
                mock_bytes = mock_path.read_bytes()
                mock_headers = {
                    "Last-Modified": email.utils.formatdate(
                        timeval=mock_stat.st_mtime,
                        usegmt=True,
                    ),
                    "Content-Length": str(len(mock_bytes)),
                }
                mock_type, _ = mimetypes.guess_type(mock_path.name)
                if mock_type:
                    mock_headers["Content-Type"] = mock_type
                mock_url = archive_feed.archive.path_to_url(
                    archive_feed.archive.root_path
                    / mock_path.relative_to(remote_mock_path)
                )
                request_mocks[mock_url] = (
                    mock_path,
                    self.requests_mock.get(
                        mock_url,
                        # Ensure the download response includes `Last-Modified`
                        headers=mock_headers,
                        content=mock_bytes,
                    ),
                )
        return request_mocks

    def update_feed(self, archive_feed, remote_mock=None):
        """
        Mock the request responses with the mock dir and update the archive.
        """
        request_mocks = self.mock_remote(archive_feed, remote_mock)
        updated_feeds = archive_feed.update()
        return request_mocks, updated_feeds

    def assert_no_header_download_mtime(self, no_header_request_mock, download_path):
        """
        Assert that download responses without headers are handled gracefully.
        """
        self.archive_feed.update()
        self.assertEqual(
            no_header_request_mock.call_count,
            1,
            "Wrong number of feed URL requests without metadata headers",
        )
        self.assertNotEqual(
            datetime.datetime.fromtimestamp(download_path.stat().st_mtime),
            self.OLD_DATETIME,
            "Archive feed modification date not current",
        )


def get_feed_items(feed_path):
    """
    Map item ID to item element for all the items in the given feed XML.
    """
    with feed_path.open() as feed_opened:
        tree = etree.parse(feed_opened)
    channel = tree.getroot().find("channel")
    return {
        item_elem.find("guid").text: item_elem for item_elem in channel.iter("item")
    }
