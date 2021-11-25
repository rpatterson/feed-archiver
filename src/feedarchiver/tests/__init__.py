"""
Tests for this feed archiver foundation or template.
"""

import os
import pathlib
import csv
import tempfile
import shutil
import unittest

from lxml import etree

import requests_mock

from .. import archive


class FeedarchiverTestCase(unittest.TestCase):
    """
    Constants and set-up used in all feed-archiver tests.
    """

    maxDiff = None

    # The relative path to the example/sample test data this test will use.
    # Default examples are copied from the Wikipedia page of each RSS/Atom syndication
    # XML format to represent the cleanest, simplest form of feeds.
    EXAMPLE_RELATIVE = pathlib.Path("simple")
    # Relative path to the feed XML content in the checkout test data to be used to mock
    # responses to requests for the remote feed URL.
    REMOTE_MOCK = pathlib.Path("orig")
    # Relative path that corresponds to the remote feed URL within the archive.
    FEED_ARCHIVE_RELATIVE = pathlib.Path(
        "https",
        "foo-username%3Asecret%40grault.example.com",
        "feeds",
        "garply.rss%3Fbar%3Dqux%252Fbaz%23corge",
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
        self.feed_url = self.feed_configs_rows[0]["Feed URL"]

        # Copy the testing example feeds archive
        shutil.copytree(
            src=self.archive_path,
            dst=self.tmp_dir.name,
            dirs_exist_ok=True,
        )
        self.archive = archive.Archive(self.tmp_dir.name)
        self.feed_path = self.archive.root_path / self.FEED_ARCHIVE_RELATIVE

    def update_feed(self, archive_feed, remote_mock=None):
        """
        Mock the request responses with the mock dir and update the archive.

        The relative paths in the mock dir are un-escaped to URLs and used to create the
        request mocks for those URLs.
        """
        if remote_mock is None:
            remote_mock = self.REMOTE_MOCK

        request_mocks = {}
        remote_mock_path = self.REMOTES_PATH / self.EXAMPLE_RELATIVE / remote_mock
        for root, dirs, files in os.walk(remote_mock_path):
            for mock_basename in files:
                if mock_basename.endswith("~"):
                    continue
                mock_path = pathlib.Path(root, mock_basename)
                mock_relative = mock_path.relative_to(remote_mock_path)
                mock_url = archive_feed.archive.path_to_url(
                    archive_feed.archive.root_path / mock_relative
                )
                request_mocks[mock_url] = (
                    mock_path,
                    self.requests_mock.get(
                        mock_url,
                        text=mock_path.read_text(),
                    ),
                )

        updated_feeds = archive_feed.update()
        return request_mocks, updated_feeds


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
