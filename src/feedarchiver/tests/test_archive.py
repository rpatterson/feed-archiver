"""
Test the feed-archiver representation of an archive of syndication feeeds.
"""

from unittest import mock

from .. import tests


class FeedarchiverArchiveTests(tests.FeedarchiverTestCase):
    """
    Test the feed-archiver representation of an archive of syndication feeeds.
    """

    # From `./feeds/wikipedia-examples/feeds/garply-orig.rss`
    UPDATE_RETURN_VALUE = {
        "7bd204c6-1655-4c27-aeee-53f933c5395f": dict(title="Example entry"),
    }

    @mock.patch("feedarchiver.feed.ArchiveFeed")
    def test_feeds_updated(self, mock_feed_class):
        """
        Each feed in the archive CSV file is updated.
        """
        mock_update_method = mock_feed_class.return_value.update
        mock_update_method.return_value = self.UPDATE_RETURN_VALUE

        updated_feeds = self.wikipedia_examples_archive.update()

        mock_feed_class.assert_any_call(
            archive=self.wikipedia_examples_archive,
            url=self.wikipedia_example_rss_url,
            config={"Feed URL": self.wikipedia_example_rss_url},
        )
        self.assertEqual(
            mock_feed_class.call_count,
            2,
            "Wrong number of archive feeds instantiated",
        )
        mock_update_method.assert_called_with()
        self.assertEqual(
            mock_update_method.call_count,
            2,
            "Wrong number of archive feeds updates",
        )
        self.assertIn(
            self.wikipedia_example_rss_url,
            updated_feeds,
            "RSS feed URL missing from archive updates",
        )
        self.assertEqual(
            updated_feeds[self.wikipedia_example_rss_url],
            self.UPDATE_RETURN_VALUE,
            "Wrong archive updates RSS feed item",
        )

    @mock.patch("feedarchiver.feed.ArchiveFeed")
    def test_feeds_no_updated_items(self, mock_feed_class):
        """
        Archive handles updates without any updated feed items.
        """
        mock_update_method = mock_feed_class.return_value.update
        mock_update_method.return_value = {}

        updated_feeds = self.wikipedia_examples_archive.update()

        self.assertEqual(
            updated_feeds,
            {},
            "Archive updated feed items not empty",
        )
