"""
Test the feed-archiver CSV listing of feed URLs.
"""

from feedarchiver import feed
from feedarchiver import tests


class FeedarchiverTests(tests.FeedarchiverTestCase):
    """
    Test the feed-archiver CSV listing of feed URLs.
    """

    def setUp(self):
        """
        Set up an example archive feed from test data.
        """
        super().setUp()

        self.wikipedia_example_rss_feed_archive = feed.ArchiveFeed(
            archive=self.wikipedia_examples_archive,
            config=self.wikipedia_example_feeds_rows[0],
            url=self.wikipedia_example_rss_url,
        )

        # All tests start with an initial request and update
        self.orig_feed_text = self.WIKIPEDIA_EXAMPLE_RSS_SRC_PATH.read_text()
        self.orig_get_mock = self.requests_mock.get(
            self.wikipedia_example_rss_url,
            text=self.orig_feed_text,
        )

    def test_feeds_requested(self):
        """
        Requests are sent for each feed URL in the archive CSV file.
        """
        self.assertFalse(
            self.wikipedia_example_rss_path.exists(),
            "Archive of feed XML exists before updating",
        )
        self.wikipedia_example_rss_feed_archive.update()
        self.assertEqual(
            self.orig_get_mock.call_count,
            1,
            "Wrong number of original feed URL requests",
        )
        self.assertTrue(
            self.wikipedia_example_rss_path.is_file(),
            "Archive of feed XML does not exist after updating",
        )
        self.assertEqual(
            self.wikipedia_example_rss_path.read_text(),
            self.orig_feed_text,
            "Archive of feed XML is different from remote",
        )
