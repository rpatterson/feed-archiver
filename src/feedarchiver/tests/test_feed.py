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

        self.wikipedia_example_rss_archive_feed = feed.ArchiveFeed(
            archive=self.wikipedia_examples_archive,
            config=self.wikipedia_example_feeds_rows[0],
            url=self.wikipedia_example_rss_url,
        )

    def test_feeds_requested(self):
        """
        Requests are sent for each feed URL in the archive CSV file.
        """
        self.assertFalse(
            self.wikipedia_example_rss_path.exists(),
            "Archive of feed XML exists before updating",
        )
        feed_path, get_mock, _ = self.update_feed(
            self.wikipedia_example_rss_archive_feed,
        )
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
            feed_path.read_text(),
            "Archive of feed XML is different from remote",
        )

    def test_feed_unchanged(self):
        """
        Archive feed is untouched if the remote feed XML is unchanged.
        """
        # Confirm initial fixture
        feed_path, get_mock, _ = self.update_feed(
            self.wikipedia_example_rss_archive_feed,
        )
        orig_archive_item_elems = tests.get_feed_items(self.wikipedia_example_rss_path)
        self.assertEqual(
            len(orig_archive_item_elems),
            1,
            "Wrong number of original archived feed items",
        )

        # Feed XML hasn't changed
        self.wikipedia_example_rss_archive_feed.update()
        self.assertEqual(
            get_mock.call_count,
            2,
            "Wrong number of original feed URL requests",
        )
        self.assertEqual(
            self.wikipedia_example_rss_path.read_text(),
            feed_path.read_text(),
            "Archive of feed XML is different from remote",
        )

    def test_feed_added_item(self):
        """
        Items are added to the archive feed XML as the remote feed XML changes.
        """
        # Populate with an archived copy of the original remote feed XML.
        _, get_mock, _ = self.update_feed(
            self.wikipedia_example_rss_archive_feed,
        )

        # Update the archive after the remote feed is updated with a new item added
        _, added_item_get_mock, _ = self.update_feed(
            archive_feed=self.wikipedia_example_rss_archive_feed,
            relative_path=self.WIKIPEDIA_EXAMPLE_RSS_SRC_RELATIVE.with_stem(
                self.WIKIPEDIA_EXAMPLE_RSS_SRC_RELATIVE.stem.replace(
                    "-orig",
                    "-added-item",
                ),
            ),
        )

        # Confirm that the correct request mocks have been used
        self.assertEqual(
            get_mock.call_count,
            1,
            "Wrong number of original feed URL requests",
        )
        self.assertEqual(
            added_item_get_mock.call_count,
            1,
            "Wrong number of added item feed URL requests",
        )

        # The item has been added to the archived feed XML
        added_archive_item_elems = tests.get_feed_items(self.wikipedia_example_rss_path)
        self.assertEqual(
            len(added_archive_item_elems),
            2,
            "Wrong number of items in archived feed after an item was added",
        )

    def test_feed_removed_item(self):
        """
        Items removed from the remote feed XML are kept in the archive.
        """
        # Populate with an archived copy of the original remote feed XML containing more
        # than one item.
        _, added_item_get_mock, _ = self.update_feed(
            archive_feed=self.wikipedia_example_rss_archive_feed,
            relative_path=self.WIKIPEDIA_EXAMPLE_RSS_SRC_RELATIVE.with_stem(
                self.WIKIPEDIA_EXAMPLE_RSS_SRC_RELATIVE.stem.replace(
                    "-orig",
                    "-added-item",
                ),
            ),
        )

        # Update the archive after the remote feed is updated with an item removed
        _, removed_item_get_mock, _ = self.update_feed(
            archive_feed=self.wikipedia_example_rss_archive_feed,
            relative_path=self.WIKIPEDIA_EXAMPLE_RSS_SRC_RELATIVE.with_stem(
                self.WIKIPEDIA_EXAMPLE_RSS_SRC_RELATIVE.stem.replace(
                    "-orig",
                    "-removed-item",
                ),
            ),
        )

        # Confirm that the correct request mocks have been used
        self.assertEqual(
            added_item_get_mock.call_count,
            1,
            "Wrong number of original feed URL requests",
        )
        self.assertEqual(
            removed_item_get_mock.call_count,
            1,
            "Wrong number of removed item feed URL requests",
        )

        # The item has been preserved in the archived feed XML
        removed_archive_item_elems = tests.get_feed_items(
            self.wikipedia_example_rss_path,
        )
        self.assertEqual(
            len(removed_archive_item_elems),
            2,
            "Wrong number of items in archived feed after an item was removed",
        )
