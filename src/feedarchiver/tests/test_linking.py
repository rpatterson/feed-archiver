"""
Test the feed-archiver linking of enclosures into media libraries.
"""

import os
import pathlib

from .. import tests


class FeedarchiverDownloadTests(tests.FeedarchiverDownloadsTestCase):
    """
    Test the feed-archiver linking of enclosures into media libraries.
    """

    FEED_BASENAME = "Foo Podcast Title"
    ITEM_BASENAME = "El Ni%C3%B1o Episode Title (Qux Series Title 106 & 07)"
    DOWNLOAD_BASENAME = "download.mp3"

    def test_basic_feed_item_linking(self):
        """
        By default, enclosures are symlinked to `.../Feed Title/Item Title.ext`.
        """
        feeds_content_path = self.archive_feed.archive.root_path / "Music" / "Podcasts"
        self.assertFalse(
            feeds_content_path.is_dir(),
            "Feed item enclosure symlinks hierarchy exists before updating",
        )

        self.update_feed(self.archive_feed)

        self.assertTrue(
            feeds_content_path.is_dir(),
            "Feed item enclosure symlinks hierarchy does not exist after updating",
        )
        feed_content_path = feeds_content_path / self.FEED_BASENAME
        self.assertTrue(
            feed_content_path.is_dir(),
            "Feed missing from symlinks hierarchy",
        )
        item_content_path = feed_content_path / self.ITEM_BASENAME
        self.assertTrue(
            item_content_path.is_dir(),
            "Item missing from symlinks hierarchy",
        )
        download_content_path = item_content_path / self.DOWNLOAD_BASENAME
        self.assertTrue(
            download_content_path.is_symlink(),
            "Item enclosure missing from symlinks hierarchy",
        )
        enclosure_archive_path = (
            self.archive.root_path / self.ENCLOSURE_RELATIVE
        ).with_suffix(".mp3")
        item_content_target = pathlib.Path(
            os.path.relpath(enclosure_archive_path, download_content_path.parent),
        )
        self.assertEqual(
            download_content_path.readlink(),
            item_content_target,
            "Item enclosure symlink to wrong target",
        )
