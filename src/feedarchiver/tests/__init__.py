"""
Tests for this feed archiver foundation or template.
"""

import pathlib
import csv
import tempfile
import shutil
import unittest

import requests_mock

from .. import archive


class FeedarchiverTestCase(unittest.TestCase):
    """
    Common feed-archiver test constants and set-up.
    """

    ARCHIVES_PATH = pathlib.Path(__file__).parent / "archives"
    FEEDS_PATH = pathlib.Path(__file__).parent / "feeds"

    WIKIPEDIA_EXAMPLE_RSS_SRC_PATH = (
        FEEDS_PATH / "wikipedia-examples" / "feeds" / "garply-orig.rss"
    )
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
