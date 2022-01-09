"""
Test updating the archive from the feed URLs.
"""

import os
import datetime

from lxml import etree

from .. import formats
from .. import tests


class FeedarchiverFeedTests(tests.FeedarchiverTestCase):
    """
    Test updating the archive from the feed URLs.
    """

    FEED_MOCK_RELATIVE = (
        tests.FeedarchiverTestCase.EXAMPLE_RELATIVE
        / tests.FeedarchiverTestCase.REMOTE_MOCK
        / tests.FeedarchiverTestCase.FEED_ARCHIVE_RELATIVE
    )
    FEED_FORMAT_PARAMS = [
        dict(
            feed_format_class=formats.RssFeedFormat,
            relative_path=FEED_MOCK_RELATIVE,
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

    def test_feed_configs_requested(self):
        """
        Requests are sent for each feed URL in the archive configuration.
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
        with feed_path.open() as remote_opened:
            remote_tree = etree.parse(remote_opened)
        remote_items = remote_tree.find("channel").iterchildren("item")
        remote_item_ids = [
            remote_item.find("guid").text for remote_item in remote_items
        ]
        with self.feed_path.open() as archive_opened:
            archive_tree = etree.parse(archive_opened)
        archive_items = archive_tree.find("channel").iterchildren("item")
        archive_item_ids = [
            archive_item.find("guid").text for archive_item in archive_items
        ]
        self.assertEqual(
            archive_item_ids,
            remote_item_ids,
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
        with feed_path.open() as remote_opened:
            remote_tree = etree.parse(remote_opened)
        remote_items = remote_tree.find("channel").iterchildren("item")
        remote_item_ids = [
            remote_item.find("guid").text for remote_item in remote_items
        ]
        with self.feed_path.open() as archive_opened:
            archive_tree = etree.parse(archive_opened)
        archive_items = archive_tree.find("channel").iterchildren("item")
        archive_item_ids = [
            archive_item.find("guid").text for archive_item in archive_items
        ]
        self.assertEqual(
            archive_item_ids,
            remote_item_ids,
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
        self.update_feed(
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
        self.update_feed(
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
                feed_format = feed_format_class(self.archive_feed)

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

    def test_feed_file_metadata(self):
        """
        Feed file metadata in the archive reflects remote response headers.

        All metadata that can be extracted from the remote response is reflected in the
        file metadata in the archive.
        """
        feed_mock_path = self.REMOTES_PATH / self.FEED_MOCK_RELATIVE
        # Set the mock file path modification date which is used by the test fixture to
        # set the header on the request mock.
        feed_mock_stat = feed_mock_path.stat()
        os.utime(
            feed_mock_path,
            (feed_mock_stat.st_atime, self.OLD_DATETIME.timestamp()),
        )

        # Feed the feed into the archive
        self.update_feed(self.archive_feed)

        # The archive file's modification time matches.
        self.assertEqual(
            datetime.datetime.fromtimestamp(self.feed_path.stat().st_mtime),
            self.OLD_DATETIME,
            "Archive feed modification date doesn't match `Last-Modified` header",
        )

        # Test in the absence of the response headers
        no_header_feed_mock_path = (
            self.REMOTES_PATH
            / self.EXAMPLE_RELATIVE
            / "added-item"
            / tests.FeedarchiverTestCase.FEED_ARCHIVE_RELATIVE
        )
        no_header_request_mock = self.requests_mock.get(
            self.feed_url,
            content=no_header_feed_mock_path.read_bytes(),
        )
        self.assert_no_header_download_mtime(
            no_header_request_mock,
            self.feed_path,
        )
