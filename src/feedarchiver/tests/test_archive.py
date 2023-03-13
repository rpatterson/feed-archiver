"""
Test the feed-archiver representation of an archive of syndication feeeds.
"""

import typing
import unittest
from unittest import mock

from .. import archive
from .. import tests


class FeedarchiverArchiveTests(tests.FeedarchiverTestCase):
    """
    Test the feed-archiver representation of an archive of syndication feeeds.
    """

    # From `./remotes/simple/orig/.../garply%3Fbar=qux%252Fbaz%23corge.rss`
    UPDATE_RETURN_VALUE: typing.Tuple = (["7bd204c6-1655-4c27-aeee-53f933c5395f"], {})

    @mock.patch("feedarchiver.feed.ArchiveFeed")
    def test_feeds_updated(self, mock_feed_class):
        """
        Each feed in the archive configuration is updated.
        """
        mock_update_method = mock_feed_class.return_value.update
        mock_update_method.return_value = self.UPDATE_RETURN_VALUE

        self.archive.load_config()
        mock_feed_class.return_value.config = mock_feed_class.mock_calls[0][2]["config"]
        mock_feed_class.return_value.path = self.feed_path
        mock_feed_class.assert_any_call(
            archive=self.archive,
            config={"remote-url": self.feed_url},
        )
        self.assertEqual(
            mock_feed_class.call_count,
            2,
            "Wrong number of archive feeds instantiated",
        )
        self.archive.archive_feeds[0].url = self.feed_url

        updated_feeds = self.archive.update()
        mock_update_method.assert_called_with()
        self.assertEqual(
            mock_update_method.call_count,
            2,
            "Wrong number of archive feeds updates",
        )
        self.assertIn(
            self.feed_url,
            updated_feeds,
            "RSS feed URL missing from archive updates",
        )
        self.assertEqual(
            updated_feeds[self.feed_url],
            self.UPDATE_RETURN_VALUE,
            "Wrong archive updates RSS feed item",
        )

    @mock.patch("feedarchiver.feed.ArchiveFeed")
    def test_feeds_no_updated_items(self, mock_feed_class):
        """
        Archive handles updates without any updated feed items.
        """
        mock_update_method = mock_feed_class.return_value.update
        mock_update_method.return_value = None
        self.archive.load_config()
        mock_feed_class.return_value.config = mock_feed_class.mock_calls[0][2]["config"]

        updated_feeds = self.archive.update()

        self.assertEqual(
            updated_feeds,
            None,
            "Archive updated feed items not empty",
        )


class FeedarchiverInvalidArchiveTests(unittest.TestCase):
    """
    Test archives with invalid configuration.
    """

    def test_archive_wo_config(self):
        """
        An archive with no configuration raises a helpful error.
        """
        with self.assertRaises(ValueError, msg="Wrong empty config error"):
            archive.Archive(tests.FeedarchiverTestCase.ARCHIVES_PATH / "empty")

    def test_archive_wo_feeds(self):
        """
        An archive with no feeds configured raises a helpful error.
        """
        feed_archive = archive.Archive(
            tests.FeedarchiverTestCase.ARCHIVES_PATH / "empty-feeds",
        )
        with self.assertRaises(ValueError, msg="Wrong empty feeds error"):
            feed_archive.load_config()
