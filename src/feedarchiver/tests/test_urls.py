"""
Test the feed-archiver URL escaping for file-system paths.
"""

import pathlib

import unittest

from feedarchiver import archive


class FeedarchiverTests(unittest.TestCase):
    """
    Test the feed-archiver URL escaping for file-system paths.
    """

    ARCHIVES_PATH = pathlib.Path(__file__).parent / "archives"

    WIKIPEDIA_EXAMPLE_RSS_URL = (
        "https://foo-username:secret@grault.example.com/feeds/garply.rss"
        "?bar=qux%2Fbaz#corge"
    )
    WIKIPEDIA_EXAMPLES_PATH = ARCHIVES_PATH / "wikipedia-examples"
    WIKIPEDIA_EXAMPLE_RSS_PATH = (
        WIKIPEDIA_EXAMPLES_PATH
        / "https"
        / "foo-username%3Asecret%40grault.example.com"
        / "feeds"
        / "garply.rss%3Fbar%3Dqux%252Fbaz%23corge"
    )

    def setUp(self):
        """
        Set up an example feeds archive from test data.
        """
        super().setUp()
        self.wikipedia_examples_archive = archive.Archive(
            self.WIKIPEDIA_EXAMPLES_PATH,
        )

    def test_url_to_archive_path(self):
        """
        A URL is escaped to a safe file-system path.
        """
        wikipedia_example_rss_path = self.wikipedia_examples_archive.url_to_path(
            self.WIKIPEDIA_EXAMPLE_RSS_URL,
        )
        self.assertEqual(
            wikipedia_example_rss_path,
            self.WIKIPEDIA_EXAMPLE_RSS_PATH,
            "Wrong safe file-system path for escaped URL",
        )

    def test_archive_path_to_url(self):
        """
        A safe file-system path is un-escaped to a URL.
        """
        wikipedia_example_rss_url = self.wikipedia_examples_archive.path_to_url(
            self.WIKIPEDIA_EXAMPLE_RSS_PATH,
        )
        self.assertEqual(
            wikipedia_example_rss_url,
            self.WIKIPEDIA_EXAMPLE_RSS_URL,
            "Wrong un-escaped URL for safe file-system path",
        )

    def test_url_roundtrip(self):
        """
        URL escaping to safe filesystem paths is stable and reproducible.
        """
        self.assertEqual(
            self.wikipedia_examples_archive.path_to_url(
                self.wikipedia_examples_archive.url_to_path(
                    self.WIKIPEDIA_EXAMPLE_RSS_URL,
                ),
            ),
            self.WIKIPEDIA_EXAMPLE_RSS_URL,
            "Different URL after escaping and un-escaping",
        )
        self.assertEqual(
            self.wikipedia_examples_archive.url_to_path(
                self.wikipedia_examples_archive.path_to_url(
                    self.WIKIPEDIA_EXAMPLE_RSS_PATH,
                ),
            ),
            self.WIKIPEDIA_EXAMPLE_RSS_PATH,
            "Different path after un-escaping and re-escaping",
        )
