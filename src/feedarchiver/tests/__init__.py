"""
Tests for this feed archiver foundation or template.
"""

import pathlib
import csv
import tempfile
import shutil
import unittest
from xml import etree

import requests_mock

from .. import archive


class FeedarchiverTestCase(unittest.TestCase):
    """
    Common feed-archiver test constants and set-up.
    """

    # Paths for test data in the checkout that represents remote feed data
    FEEDS_PATH = pathlib.Path(__file__).parent / "feeds"
    WIKIPEDIA_EXAMPLE_FEEDS_RELATIVE = pathlib.Path(
        "wikipedia-examples",
        "feeds",
    )
    WIKIPEDIA_EXAMPLE_RSS_SRC_RELATIVE = (
        WIKIPEDIA_EXAMPLE_FEEDS_RELATIVE / "garply-orig.rss"
    )
    WIKIPEDIA_EXAMPLE_RSS_SRC_PATH = FEEDS_PATH / WIKIPEDIA_EXAMPLE_RSS_SRC_RELATIVE

    # Paths for test data in the checkout that represents local archived feed data
    ARCHIVES_PATH = pathlib.Path(__file__).parent / "archives"
    WIKIPEDIA_EXAMPLES_PATH = ARCHIVES_PATH / "wikipedia-examples"
    WIKIPEDIA_EXAMPLES_FEED_CONFIGS_PATH = (
        WIKIPEDIA_EXAMPLES_PATH / archive.Archive.FEED_CONFIGS_BASENAME
    )
    WIKIPEDIA_EXAMPLE_RSS_RELATIVE = pathlib.Path(
        "https",
        "foo-username%3Asecret%40grault.example.com",
        "feeds",
        "garply.rss%3Fbar%3Dqux%252Fbaz%23corge",
    )
    WIKIPEDIA_EXAMPLE_RSS_PATH = (
        WIKIPEDIA_EXAMPLES_PATH / WIKIPEDIA_EXAMPLE_RSS_RELATIVE
    )

    def setUp(self):
        """
        Set up an example feeds archive from test data.
        """
        super().setUp()

        # https://requests-mock.readthedocs.io/en/latest/fixture.html#fixtures
        self.requests_mock = requests_mock.Mocker()
        self.addCleanup(self.requests_mock.stop)
        self.requests_mock.start()

        # Extract the feed URL from the CSV
        with open(
            self.WIKIPEDIA_EXAMPLES_FEED_CONFIGS_PATH,
            encoding="utf-8",
        ) as feeds_opened:
            self.wikipedia_example_feeds_rows = list(csv.DictReader(feeds_opened))
        self.wikipedia_example_rss_url = self.wikipedia_example_feeds_rows[0][
            "Feed URL"
        ]

        # Copy the testing example feeds archive
        self.wikipedia_examples_tmp = (
            tempfile.TemporaryDirectory(  # pylint: disable=consider-using-with
                suffix=self.WIKIPEDIA_EXAMPLES_PATH.suffix,
                prefix=f"{self.WIKIPEDIA_EXAMPLES_PATH.stem}-",
            )
        )
        self.addCleanup(self.wikipedia_examples_tmp.cleanup)
        shutil.copytree(
            src=self.WIKIPEDIA_EXAMPLES_PATH,
            dst=self.wikipedia_examples_tmp.name,
            dirs_exist_ok=True,
        )
        self.wikipedia_examples_archive = archive.Archive(
            self.wikipedia_examples_tmp.name,
        )
        self.wikipedia_example_rss_path = (
            self.wikipedia_examples_archive.root_path
            / self.WIKIPEDIA_EXAMPLE_RSS_RELATIVE
        )

    def update_feed(
        self,
        archive_feed,
        relative_path=WIKIPEDIA_EXAMPLE_RSS_SRC_RELATIVE,
    ):
        """
        Mock the request response with the feed file contents and update the archive.
        """
        feed_path = self.FEEDS_PATH / relative_path
        get_mock = self.requests_mock.get(
            self.wikipedia_example_rss_url,
            text=feed_path.read_text(),
        )
        updated_feeds = archive_feed.update()
        return feed_path, get_mock, updated_feeds


def get_feed_items(feed_path):
    """
    Map item ID to item element for all the items in the given feed XML.
    """
    tree = etree.ElementTree.parse(feed_path)
    channel = tree.getroot().find("channel")
    return {
        item_elem.find("guid").text: item_elem for item_elem in channel.iter("item")
    }
