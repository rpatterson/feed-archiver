"""
Test the feed-archiver migration of whole archives.
"""

import os
import pathlib
import tempfile

from .. import archive
from .. import tests


class FeedarchiverMigrateTests(tests.FeedarchiverDownloadsTestCase):
    """
    Test the feed-archiver migration of whole archives.
    """

    STAT_ATTRS_INCLUDE = {
        st_attr
        for st_attr in dir(os.stat_result)
        if st_attr.startswith("st_") and st_attr != "st_nlink"
        # For some reason Python's `pathlib.Path.link_to()` changes the ctime while
        # `$ ln` in the shell does not.
        and not st_attr.startswith("st_ctime")
        # Access times seem to change intermittently when run under some combination of
        # coverage and docker
        and not st_attr.startswith("st_atime")
    }

    def get_archive_contents(self, root_path=None):
        """
        Collect all necessary identifying information for the archive contents.
        """
        if root_path is None:
            root_path = self.archive.root_path

        archive_contents = {}
        for archive_path, archive_relative in tests.walk_archive(root_path):
            content_stat = archive_path.stat()
            archive_contents[archive_relative] = (
                {
                    st_attr: getattr(content_stat, st_attr)
                    for st_attr in self.STAT_ATTRS_INCLUDE
                    # The actuall feed XML is modified, so ignore those timestamps
                    if not archive_relative == self.FEED_ARCHIVE_RELATIVE
                    or not st_attr.startswith("st_mtime")
                },
                archive_path.read_bytes(),
            )
        return archive_contents

    def test_migration(self):  # pylint: disable=too-many-locals
        """
        The contents of a migrated archive are identical to the original.
        """
        # Populate the original archive
        orig_request_mocks, _ = self.update_feed(self.archive_feed)
        # Collect all necessary identifying information for the archive contents.
        orig_archive_contents = self.get_archive_contents()

        # Migrate the archive to another directory
        with tempfile.TemporaryDirectory(  # pylint: disable=consider-using-with
            suffix=self.EXAMPLE_RELATIVE.suffix,
            prefix=f"{self.EXAMPLE_RELATIVE.stem}-",
        ) as target_dir:
            target_path = pathlib.Path(target_dir)
            self.archive.migrate(target_path)
            orig_after_archive_contents = self.get_archive_contents()
            migrated_archive_contents = self.get_archive_contents(target_path)

            # The migrated archive should be fully up to date
            migrated_archive = archive.Archive(target_path)
            migrated_archive.load_config()
            migrated_archive_feed = migrated_archive.archive_feeds[0]
            (
                migrated_updated_item_ids,
                migrated_downloaded_paths,
            ) = migrated_archive_feed.update()

        # Compare migrated archive contents
        self.assertEqual(
            orig_after_archive_contents.keys(),
            orig_archive_contents.keys(),
            "Original archive contents differ after migration",
        )
        self.assertEqual(
            migrated_archive_contents.keys(),
            orig_archive_contents.keys(),
            "Migrated archive contents differ from the original",
        )
        for archive_relative, (orig_stat, orig_bytes) in orig_archive_contents.items():
            orig_after_stat, orig_after_bytes = orig_after_archive_contents[
                archive_relative
            ]
            migrated_stat, migrated_bytes = migrated_archive_contents[archive_relative]
            with self.subTest(
                msg="Test migration of one archive file",
                archive_relative=str(archive_relative),
            ):
                self.assertEqual(
                    orig_after_stat,
                    orig_stat,
                    "Original metadata differs after migration: "
                    f"{str(archive_relative)}",
                )
                self.assertTrue(
                    orig_after_bytes == orig_bytes,
                    "Original content differs after migration: "
                    f"{str(archive_relative)}",
                )
                if archive_relative != self.FEED_ARCHIVE_RELATIVE:
                    self.assertEqual(
                        migrated_stat,
                        orig_stat,
                        "Migrated metadata differs from the original: "
                        f"{str(archive_relative)}",
                    )
                self.assertTrue(
                    migrated_bytes == orig_bytes,
                    "Migrated content differs from the original: "
                    f"{str(archive_relative)}",
                )

        # Perform assertions concerning updating the migrated archive
        self.assertEqual(
            migrated_updated_item_ids,
            [],
            "Feed items updated in migrated archive",
        )
        self.assertEqual(
            migrated_downloaded_paths,
            {},
            "Feed item content downloaded in migrated archive",
        )

        # No additional requests should have been made to remotes
        remote_mock_path = self.REMOTES_PATH / self.EXAMPLE_RELATIVE / "orig"
        uncalled_request_mocks = orig_request_mocks.copy()
        for _, archive_relative in tests.walk_archive(
            self.archive.root_path,
        ):
            with self.subTest(
                msg="Test one feed download migration",
                archive_relative=str(archive_relative),
            ):
                # Assert that the request mock was called correctly
                download_url, _ = self.archive_relative_to_remote_url(
                    archive_relative,
                    remote_mock_path,
                )
                _, download_request_mock = uncalled_request_mocks.pop(
                    download_url,
                )
                if download_url == self.feed_url:
                    self.assertEqual(
                        download_request_mock.call_count,
                        3,
                        f"Wrong number of feed requests: {download_url!r}",
                    )
                else:
                    self.assertEqual(
                        download_request_mock.call_count,
                        1,
                        f"Wrong number of download requests: {download_url!r}",
                    )
