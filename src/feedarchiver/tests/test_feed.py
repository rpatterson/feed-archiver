"""
Test the feed-archiver CSV listing of feed URLs.
"""

from lxml import etree

from .. import feed
from .. import formats
from .. import tests


class FeedarchiverFeedTests(tests.FeedarchiverTestCase):
    """
    Test the feed-archiver CSV listing of feed URLs.
    """

    FEED_FORMAT_PARAMS = [
        dict(
            feed_format_class=formats.RssFeedFormat,
            relative_path=(
                tests.FeedarchiverTestCase.EXAMPLE_RELATIVE
                / tests.FeedarchiverTestCase.REMOTE_MOCK
                / "https"
                / "foo-username%3Asecret%40grault.example.com"
                / "feeds"
                / "garply.rss%3Fbar%3Dqux%252Fbaz%23corge"
            ),
            items_parent_tag="channel",
            item_tag="item",
            item_id="7bd204c6-1655-4c27-aeee-53f933c5395f",
        ),
        dict(
            feed_format_class=formats.AtomFeedFormat,
            relative_path=(
                tests.FeedarchiverTestCase.EXAMPLE_RELATIVE
                / tests.FeedarchiverTestCase.REMOTE_MOCK
                / "https"
                / "waldo.example.com"
                / "feeds"
                / "waldo"
            ),
            items_parent_tag=(
                f"{{http://www.w3.org/2005/Atom}}{formats.AtomFeedFormat.ROOT_TAG}"
            ),
            item_tag="entry",
            item_id="urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a",
        ),
    ]

    def setUp(self):
        """
        Set up an example archive feed from test data.
        """
        super().setUp()

        self.archive_feed = feed.ArchiveFeed(
            archive=self.archive,
            config=self.feed_configs_rows[0],
            url=self.feed_url,
        )

    def test_feed_configs_requested(self):
        """
        Requests are sent for each feed URL in the archive CSV file.
        """
        self.assertFalse(
            self.feed_path.exists(),
            "Archive of feed XML exists before updating",
        )
        orig_request_mocks, _ = self.update_feed(self.archive_feed)
        feed_path, get_mock = orig_request_mocks[self.feed_url]
        self.assertEqual(
            get_mock.call_count,
            1,
            "Wrong number of original feed URL requests",
        )
        self.assertTrue(
            self.feed_path.is_file(),
            "Archive of feed XML does not exist after updating",
        )
        remote_tree = etree.parse(feed_path.open())
        etree.indent(remote_tree)
        self.assertEqual(
            self.feed_path.read_text(),
            etree.tostring(remote_tree).decode(),
            "Archive of feed XML is different from remote",
        )

    def test_feed_unchanged(self):
        """
        Archive feed is untouched if the remote feed XML is unchanged.
        """
        # Confirm initial fixture
        orig_request_mocks, _ = self.update_feed(self.archive_feed)
        feed_path, get_mock = orig_request_mocks[self.feed_url]
        orig_archive_item_elems = tests.get_feed_items(self.feed_path)
        self.assertEqual(
            len(orig_archive_item_elems),
            1,
            "Wrong number of original archived feed items",
        )

        # Feed XML hasn't changed
        self.archive_feed.update()
        self.assertEqual(
            get_mock.call_count,
            2,
            "Wrong number of original feed URL requests",
        )
        remote_tree = etree.parse(feed_path.open())
        etree.indent(remote_tree)
        self.assertEqual(
            self.feed_path.read_text(),
            etree.tostring(remote_tree).decode(),
            "Archive of feed XML is different from remote",
        )

    def test_feed_added_item(self):
        """
        Items are added to the archive feed XML as the remote feed XML changes.
        """
        # Populate with an archived copy of the original remote feed XML.
        orig_request_mocks, _ = self.update_feed(self.archive_feed)
        _, get_mock = orig_request_mocks[self.feed_url]
        orig_archive_item_elems = tests.get_feed_items(self.feed_path)
        self.assertEqual(
            len(orig_archive_item_elems),
            1,
            "Wrong number of original items in archived feed",
        )

        # Update the archive after the remote feed is updated with a new item added
        added_item_request_mocks, _ = self.update_feed(
            archive_feed=self.archive_feed,
            remote_mock="added-item",
        )
        _, added_item_get_mock = added_item_request_mocks[self.feed_url]

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
        added_archive_item_elems = tests.get_feed_items(self.feed_path)
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
        added_item_request_mocks, _ = self.update_feed(
            archive_feed=self.archive_feed,
        )
        _, added_item_get_mock = added_item_request_mocks[self.feed_url]

        # Update the archive after the remote feed is updated with an item removed
        removed_item_request_mocks, _ = self.update_feed(
            archive_feed=self.archive_feed,
            remote_mock="removed-item",
        )
        _, removed_item_get_mock = removed_item_request_mocks[self.feed_url]

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
        removed_archive_item_elems = tests.get_feed_items(self.feed_path)
        self.assertEqual(
            len(removed_archive_item_elems),
            2,
            "Wrong number of items in archived feed after an item was removed",
        )

    def test_feed_reordered_item(self):
        """
        Items are reordered to the archive feed XML as the remote feed XML changes.
        """
        # Populate with a feed containing multiple items
        added_item_request_mocks, _ = self.update_feed(
            archive_feed=self.archive_feed,
            remote_mock="added-item",
        )
        # Update the archive after the remote feed is updated with item order changed
        reordered_item_request_mocks, _ = self.update_feed(
            archive_feed=self.archive_feed,
            remote_mock="reordered-item",
        )
        reordered_item_feed_path, _ = reordered_item_request_mocks[self.feed_url]

        remote_tree = etree.parse(reordered_item_feed_path.open())
        remote_items = remote_tree.find("channel").findall("item")
        archive_tree = etree.parse(self.feed_path.open())
        archive_items = archive_tree.find("channel").findall("item")
        self.assertEqual(
            archive_items[0].find("guid").text,
            remote_items[2].find("guid").text,
            "Item added at end of remote feed not at beginning of archive feed",
        )
        self.assertEqual(
            archive_items[1].find("guid").text,
            remote_items[1].find("guid").text,
            "Item original position in remote feed not preserved",
        )
        self.assertEqual(
            archive_items[2].find("guid").text,
            remote_items[0].find("guid").text,
            "Item original position in remote feed not preserved",
        )

    def test_feed_empty(self):
        """
        Updating an empty feed works without any errors
        """
        # Populate with a feed containing multiple items
        empty_request_mocks, _ = self.update_feed(
            archive_feed=self.archive_feed,
            remote_mock="empty",
        )
        archive_tree = etree.parse(self.feed_path.open())
        archive_items = archive_tree.find("channel").findall("item")
        self.assertEqual(
            archive_items,
            [],
            "Archive contains items for an empty feed",
        )

    def test_feed_formats(self):
        """
        Both RSS and Atom XML feed formats are supported.
        """
        for feed_format_params in self.FEED_FORMAT_PARAMS:
            feed_format_class = feed_format_params["feed_format_class"]
            relative_path = feed_format_params["relative_path"]
            with self.subTest(
                msg="Test one XML feed format",
                feed_format_class=feed_format_class,
            ):
                with (self.REMOTES_PATH / relative_path).open() as feed_opened:
                    feed_tree = etree.parse(feed_opened)
                feed_root = feed_tree.getroot()
                feed_format = feed_format_class()

                items_parent = feed_format.get_items_parent(feed_root)
                self.assertEqual(
                    items_parent.tag,
                    feed_format_params["items_parent_tag"],
                    "Wrong feed XML items container element tag name",
                )

                items = list(feed_format.iter_items(feed_root))
                self.assertEqual(
                    len(items),
                    1,
                    "Wrong number of feed XML items",
                )
                self.assertEqual(
                    etree.QName(items[0].tag).localname,
                    feed_format_params["item_tag"],
                    "Wrong feed XML items container element tag name",
                )

                items_id = feed_format.get_item_id(items[0])
                self.assertEqual(
                    items_id,
                    feed_format_params["item_id"],
                    "Wrong feed item unique identifier",
                )
