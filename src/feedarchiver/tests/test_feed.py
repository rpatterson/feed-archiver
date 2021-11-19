"""
Test the feed-archiver CSV listing of feed URLs.
"""

import requests_mock

from feedarchiver import feed
from feedarchiver import tests


@requests_mock.Mocker()
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

    def test_feeds_requested(self, requests_mocker):
        """
        Requests are sent for each feed URL in the archive CSV file.
        """
        feed_text = self.WIKIPEDIA_EXAMPLE_RSS_SRC_PATH.read_text()
        get_mock = requests_mocker.get(
            self.wikipedia_example_rss_url,
            text=feed_text,
        )
        self.assertFalse(
            self.wikipedia_example_rss_path.exists(),
            "Archive of feed XML exists before updating",
        )
        self.wikipedia_example_rss_feed_archive.update()
        self.assertEqual(
            get_mock.call_count,
            1,
            "Wrong number of original feed URL requests",
        )
        self.assertTrue(
            self.wikipedia_example_rss_path.is_file(),
            "Archive of feed XML does not exist after updating",
        )
        self.assertEqual(
            self.wikipedia_example_rss_path.read_text(),
            feed_text,
            "Archive of feed XML is different from original",
        )
