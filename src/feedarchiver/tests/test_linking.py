"""
Test the feed-archiver linking of enclosures into media libraries.
"""

import os
import pathlib
import logging

import feedarchiver
from .. import archive
from .. import feed
from .. import tests


class FeedarchiverDownloadTests(tests.FeedarchiverDownloadsTestCase):
    """
    Test the feed-archiver linking of enclosures into media libraries.
    """

    FEED_BASENAME = "Foo Podcast Title"
    ITEM_BASENAME = "El Ni%C3%B1o Episode Title (Qux Series Title 106 & 07)"
    DOWNLOAD_SUFFIX = ".mp3"
    ITEM_DOWNLOAD_BASENAME = f"{ITEM_BASENAME}{DOWNLOAD_SUFFIX}"
    DOWNLOAD_BASENAME = f"download{DOWNLOAD_SUFFIX}"

    def test_basic_feed_item_linking(self):
        """
        By default, enclosures are symlinked to `.../Feed Title/Item Title.ext`.
        """
        feeds_links_path = self.archive_feed.archive.root_path / "Music" / "Podcasts"
        self.assertFalse(
            feeds_links_path.is_dir(),
            "Feed item enclosure symlinks hierarchy exists before updating",
        )

        self.update_feed(self.archive_feed)

        self.assertTrue(
            feeds_links_path.is_dir(),
            "Feed item enclosure symlinks hierarchy does not exist after updating",
        )
        feed_links_path = feeds_links_path / self.FEED_BASENAME
        self.assertTrue(
            feed_links_path.is_dir(),
            "Feed missing from symlinks hierarchy",
        )
        link_path = feed_links_path / self.ITEM_DOWNLOAD_BASENAME
        self.assertTrue(
            link_path.is_symlink(),
            "Item enclosure missing from symlinks hierarchy",
        )
        enclosure_archive_path = (
            self.archive.root_path / self.ENCLOSURE_RELATIVE
        ).with_suffix(".mp3")
        item_enclosures_target = pathlib.Path(
            os.path.relpath(enclosure_archive_path, link_path.parent),
        )
        self.assertEqual(
            os.readlink(link_path),
            str(item_enclosures_target),
            "Item enclosure symlink to wrong target",
        )

    def test_feed_relinking_existing(self):
        """
        The `relink` sub-command cleans up old links and makes new links per the config.
        """
        # Verify initial test fixture
        self.update_feed(self.archive_feed)
        feeds_links_path = self.archive_feed.archive.root_path / "Music" / "Podcasts"
        feed_links_path = feeds_links_path / self.FEED_BASENAME
        link_path = feed_links_path / self.ITEM_DOWNLOAD_BASENAME
        self.assertTrue(
            link_path.is_symlink(),
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
            link_path.exists(),
            "Original downloaded file symlink still exists",
        )
        updated_link_path = (
            feed_links_path / f"{self.ITEM_BASENAME} - {self.DOWNLOAD_BASENAME}"
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
        feeds_links_path = self.archive_feed.archive.root_path / "Music" / "Podcasts"
        feed_links_path = feeds_links_path / self.FEED_BASENAME
        link_path = feed_links_path / self.ITEM_DOWNLOAD_BASENAME
        link_path.unlink()

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
            link_path.exists(),
            "Original downloaded file symlink still exists",
        )
        updated_link_path = (
            feed_links_path / f"{self.ITEM_BASENAME} - {self.DOWNLOAD_BASENAME}"
        )
        self.assertTrue(
            updated_link_path.is_symlink(),
            "New downloaded file link is not a symlink",
        )

    def test_feed_relink_missing_feed(self):
        """
        The `relink` raises a helpful error if the archived feed XML is missing.
        """
        self.update_feed(self.archive_feed)
        self.archive_feed.path.unlink()
        with self.assertLogs(
            archive.logger,
            level=logging.ERROR,
        ) as logged_msgs:
            feedarchiver.relink(archive_dir=self.archive_feed.archive.root_path)
        self.assertEqual(
            len(logged_msgs.records),
            1,
            "Wrong number of download logged archive records",
        )
        self.assertIn(
            "Could not locate feed in archive",
            logged_msgs.records[0].exc_info[1].args[0],
            "Wrong logged record message",
        )

    def test_feed_relink_multiple_feed_files(self):
        """
        The `relink` logs a helpful warning if there are multiple archived feeds.
        """
        self.update_feed(self.archive_feed)
        self.archive_feed.path.with_suffix(".xml").write_text(
            self.archive_feed.path.read_text(),
        )
        self.archive_feed.path.rename(self.archive_feed.path.with_suffix(".xml.rss"))
        with self.assertLogs(
            feed.logger,
            level=logging.WARNING,
        ) as logged_msgs:
            feedarchiver.relink(archive_dir=self.archive_feed.archive.root_path)
        self.assertGreater(
            len(logged_msgs.records),
            0,
            "Missing logged records",
        )
        self.assertIn(
            "Multiple XML files found for feed",
            logged_msgs.records[0].message,
            "Wrong logged record message",
        )


class FeedarchiverRelinkEdgeTests(tests.FeedarchiverTestCase):
    """
    Test `relink` sub-command edge cases.
    """

    EXAMPLE_RELATIVE = pathlib.Path("empty-items")

    def test_feed_relinking_wo_items(self):
        """
        The `relink` sub-command tolerates feeds without items.
        """
        self.update_feed(self.archive_feed)
        relink_results = feedarchiver.relink(
            archive_dir=self.archive_feed.archive.root_path,
        )
        self.assertFalse(
            relink_results,
            "Empty feed returned relink results",
        )
