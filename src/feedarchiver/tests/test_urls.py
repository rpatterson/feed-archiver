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
        feed_path = self.archive.url_to_path(self.feed_url)
        self.assertEqual(
            feed_path,
            self.feed_path,
            "Wrong safe file-system path for escaped URL",
        )

    def test_archive_path_to_url(self):
        """
        A safe file-system path is un-escaped to a URL.
        """
        feed_url = self.archive.path_to_url(self.feed_path)
        self.assertEqual(
            feed_url,
            self.feed_url,
            "Wrong un-escaped URL for safe file-system path",
        )

    def test_url_roundtrip(self):
        """
        URL escaping to safe filesystem paths is stable and reproducible.
        """
        self.assertEqual(
            self.archive.path_to_url(self.archive.url_to_path(self.feed_url)),
            self.feed_url,
            "Different URL after escaping and un-escaping",
        )
        self.assertEqual(
            self.archive.url_to_path(self.archive.path_to_url(self.feed_path)),
            self.feed_path,
            "Different path after un-escaping and re-escaping",
        )
