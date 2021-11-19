"""
Test the feed-archiver URL escaping for file-system paths.
"""

from .. import tests


class FeedarchiverURLsTests(tests.FeedarchiverTestCase):
    """
    Test the feed-archiver URL escaping for file-system paths.
    """

    def test_url_to_archive_path(self):
        """
        A URL is escaped to a safe file-system path.
        """
        wikipedia_example_rss_path = self.wikipedia_examples_archive.url_to_path(
            self.wikipedia_example_rss_url,
        )
        self.assertEqual(
            wikipedia_example_rss_path,
            self.wikipedia_example_rss_path,
            "Wrong safe file-system path for escaped URL",
        )

    def test_archive_path_to_url(self):
        """
        A safe file-system path is un-escaped to a URL.
        """
        wikipedia_example_rss_url = self.wikipedia_examples_archive.path_to_url(
            self.wikipedia_example_rss_path,
        )
        self.assertEqual(
            wikipedia_example_rss_url,
            self.wikipedia_example_rss_url,
            "Wrong un-escaped URL for safe file-system path",
        )

    def test_url_roundtrip(self):
        """
        URL escaping to safe filesystem paths is stable and reproducible.
        """
        self.assertEqual(
            self.wikipedia_examples_archive.path_to_url(
                self.wikipedia_examples_archive.url_to_path(
                    self.wikipedia_example_rss_url,
                ),
            ),
            self.wikipedia_example_rss_url,
            "Different URL after escaping and un-escaping",
        )
        self.assertEqual(
            self.wikipedia_examples_archive.url_to_path(
                self.wikipedia_examples_archive.path_to_url(
                    self.wikipedia_example_rss_path,
                ),
            ),
            self.wikipedia_example_rss_path,
            "Different path after un-escaping and re-escaping",
        )
