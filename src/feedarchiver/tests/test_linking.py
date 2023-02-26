"""
Test the feed-archiver linking of enclosures into media libraries.
"""

import os
import pathlib

import feedarchiver
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
            os.readlink(download_content_path),
            str(item_content_target),
            "Item enclosure symlink to wrong target",
        )

    def test_feed_relinking_existing(self):
        """
        The `relink` sub-command cleans up old links and makes new links per the config.
        """
        # Verify initial test fixture
        self.update_feed(self.archive_feed)
        feeds_content_path = self.archive_feed.archive.root_path / "Music" / "Podcasts"
        feed_content_path = feeds_content_path / self.FEED_BASENAME
        item_content_path = feed_content_path / self.ITEM_BASENAME
        download_content_path = item_content_path / self.DOWNLOAD_BASENAME
        self.assertTrue(
            download_content_path.is_symlink(),
            "Item enclosure missing from symlinks hierarchy",
        )

        # Change the archive configuration such that downloaded files are symlinked to
        # different locations.
        updated_config_path = (
            self.ARCHIVES_PATH / "relink" / self.archive.config_path.name
        )
        self.archive.config_path.write_text(
            updated_config_path.read_text(),
            encoding="utf-8",
        )

        # Run the `$ feedarchiver relink` sub-command with a configuration that changes
        # the path downloaded files should be linked to.
        feedarchiver.main(
            args=["--archive-dir", str(self.archive_feed.archive.root_path), "relink"],
        )
        self.assertFalse(
            download_content_path.exists(),
            "Original downloaded file symlink still exists",
        )
        updated_link_path = (
            feed_content_path / f"{self.ITEM_BASENAME} - {self.DOWNLOAD_BASENAME}"
        )
        self.assertTrue(
            updated_link_path.is_symlink(),
            "New downloaded file link is not a symlink",
        )

    def test_feed_relinking_deleted(self):
        """
        The `relink` sub-command tolerates already deleted symlinks.
        """
        self.update_feed(self.archive_feed)
        feeds_content_path = self.archive_feed.archive.root_path / "Music" / "Podcasts"
        feed_content_path = feeds_content_path / self.FEED_BASENAME
        item_content_path = feed_content_path / self.ITEM_BASENAME
        download_content_path = item_content_path / self.DOWNLOAD_BASENAME
        download_content_path.unlink()

        # Change the archive configuration such that downloaded files are symlinked to
        # different locations.
        updated_config_path = (
            self.ARCHIVES_PATH / "relink-wo-suffix" / self.archive.config_path.name
        )
        self.archive.config_path.write_text(
            updated_config_path.read_text(),
            encoding="utf-8",
        )
        # Excercise logic to locate feed XML file in archive
        self.feed_path.with_suffix(".txt").write_text("Not actual feed XML")

        # Run the `$ feedarchiver relink` sub-command with a configuration that changes
        # the path downloaded files should be linked to.
        feedarchiver.relink(archive_dir=self.archive_feed.archive.root_path)
        self.assertFalse(
            download_content_path.exists(),
            "Original downloaded file symlink still exists",
        )
        updated_link_path = (
            feed_content_path / f"{self.ITEM_BASENAME} - {self.DOWNLOAD_BASENAME}"
        )
        self.assertTrue(
            updated_link_path.is_symlink(),
            "New downloaded file link is not a symlink",
        )
