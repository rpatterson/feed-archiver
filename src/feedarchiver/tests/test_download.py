"""
Test the feed-archiver downloading of enclosures, assets, etc..
"""

import os
import datetime
import pathlib

from lxml import etree
import requests_mock

from .. import tests


class FeedarchiverDownloadTests(tests.FeedarchiverTestCase):
    """
    Test the feed-archiver downloading of enclosures, assets, etc..
    """

    EXAMPLE_RELATIVE = pathlib.Path("downloads")

    # Constants specific to this test suite
    ENCLOSURE_HOST_PATH = (
        "foo.example.com/podcast/episodes/waldo-episode-title/waldo.mp3"
    )
    ENCLOSURE_URL = f"https://{ENCLOSURE_HOST_PATH}"
    ENCLOSURE_RELATIVE = pathlib.Path(f"https/{ENCLOSURE_HOST_PATH}")
    ENCLOSURE_MOCK_PATH = (
        tests.FeedarchiverTestCase.REMOTES_PATH
        / EXAMPLE_RELATIVE
        / tests.FeedarchiverTestCase.REMOTE_MOCK
        / ENCLOSURE_RELATIVE
    )

    def test_real_requests_disabled(self):
        """
        Confirm that tests will fail if real/external requests are attempted.
        """
        # Put the mocks in place
        self.update_feed(self.archive_feed)
        with self.assertRaises(requests_mock.exceptions.NoMockAddress):
            self.archive.requests.get("http://example.com")

    def test_download_file_metadata(self):
        """
        Download file metadata in the archive reflects remote response headers.

        All metadata that can be extracted from the remote response is reflected in the
        file metadata in the archive.
        """
        # Constants specific to this test
        enclosure_archive_path = self.archive.root_path / self.ENCLOSURE_RELATIVE

        # Set the mock file path modification date which is used by the test fixture to
        # set the header on the request mock.
        enclosure_mock_stat = self.ENCLOSURE_MOCK_PATH.stat()
        os.utime(
            self.ENCLOSURE_MOCK_PATH,
            (enclosure_mock_stat.st_atime, self.OLD_DATETIME.timestamp()),
        )

        # Download the enclosure into the archive
        self.update_feed(self.archive_feed)

        # The archive file's modification time matches.
        self.assertEqual(
            datetime.datetime.fromtimestamp(enclosure_archive_path.stat().st_mtime),
            self.OLD_DATETIME,
            "Archive download modification date doesn't match `Last-Modified` header",
        )

        # Test in the absence of the response headers
        self.archive_feed.path.unlink()
        enclosure_archive_path.unlink()
        no_header_request_mock = self.requests_mock.get(
            self.ENCLOSURE_URL,
            content=self.ENCLOSURE_MOCK_PATH.read_bytes(),
        )
        self.assert_no_header_download_mtime(
            no_header_request_mock,
            enclosure_archive_path,
        )

    def test_downloads(self):  # pylint: disable=too-many-locals
        """
        All files in the archive after update correspond to the fixture.

        This tests for completeness, that nothing in the archive doesn't correspond to a
        request mock in the test fixture and that none of the request mocks in the
        fixture weren't called.
        """
        # Download all feed enclosures and assets
        orig_request_mocks, _ = self.update_feed(self.archive_feed)
        self.assertGreater(
            len(orig_request_mocks),
            # At least 2 downloads in addition to the feeds themselves
            len(self.feed_configs_rows) + 1,
            "Too few request mocks registered by test fixture",
        )

        remote_mock_path = self.REMOTES_PATH / self.EXAMPLE_RELATIVE / "orig"
        uncalled_request_mocks = orig_request_mocks.copy()
        # This test is written from the perspective of the archive for completeness.
        # Walk the whole archive so we can make assertions on everything within,
        # including things that shouldn't be there.
        for root, _, files in os.walk(self.archive.root_path):
            for archive_basename in files:
                if (
                    archive_basename.endswith("~")
                    or archive_basename == self.archive.FEED_CONFIGS_BASENAME
                ):
                    continue
                archive_path = pathlib.Path(root, archive_basename)
                archive_relative = archive_path.relative_to(self.archive.root_path)
                with self.subTest(
                    msg="Test one feed download",
                    archive_relative=str(archive_relative),
                ):

                    # Assert that the request mock was called correctly
                    download_url = self.archive.path_to_url(archive_path)
                    self.assertIn(
                        download_url,
                        uncalled_request_mocks,
                        "No mock registered for download request",
                    )
                    _, download_request_mock = uncalled_request_mocks.pop(
                        download_url,
                    )
                    self.assertEqual(
                        download_request_mock.call_count,
                        1,
                        f"Wrong number of requests: {download_url!r}",
                    )

                    # Assert that the downloaded file in the archive is correct
                    mock_path = remote_mock_path / archive_relative
                    self.assertTrue(
                        archive_path.is_file(), "Download is not a file in the archive"
                    )
                    if archive_path != self.archive_feed.path:
                        self.assertEqual(
                            archive_path.read_bytes(),
                            mock_path.read_bytes(),
                            "Different archived download content from remote",
                        )

        self.assertEqual(
            uncalled_request_mocks,
            {},
            # Some request mocks didn't correspond to archive files
            "Archive download missing for request mocks",
        )

        # Assert archive URLs updated
        archive_tree = etree.parse(self.archive_feed.path.open())
        feed_link_path = (
            pathlib.Path(archive_tree.find("channel").find("link").text) / "index.html"
        )
        self.assertTrue(
            (self.archive_feed.path.parent / feed_link_path).is_file(),
            "Wrong feed link index HTML relative URL in feed",
        )
        feed_href_path = pathlib.Path(
            archive_tree.find("channel")
            .find("{http://www.w3.org/2005/Atom}link")
            .attrib["href"]
        )
        self.assertTrue(
            (self.archive_feed.path.parent / feed_href_path).is_file(),
            "Wrong feed XML href relative URL in feed",
        )
        feed_image_path = pathlib.Path(
            archive_tree.find("channel")
            .find("{http://www.itunes.com/dtds/podcast-1.0.dtd}image")
            .attrib["href"]
        )
        self.assertTrue(
            (self.archive_feed.path.parent / feed_image_path).is_file(),
            "Wrong feed image relative URL in feed",
        )
        archive_items = archive_tree.find("channel").findall("item")
        item_link_path = pathlib.Path(archive_items[0].find("link").text) / "index.html"
        self.assertTrue(
            (self.archive_feed.path.parent / item_link_path).is_file(),
            "Wrong item link index HTML relative URL in feed",
        )
        item_enclosure_path = pathlib.Path(
            archive_items[0].find("enclosure").attrib["url"],
        )
        self.assertTrue(
            (self.archive_feed.path.parent / item_enclosure_path).is_file(),
            "Wrong item enclosure relative URL in feed",
        )
        item_media_content_path = pathlib.Path(
            archive_items[0].find("{*}content").attrib["url"],
        )
        self.assertEqual(
            item_media_content_path,
            item_enclosure_path,
            "Wrong item media content relative URL in feed",
        )
        item_image_path = pathlib.Path(
            archive_items[0].find("{*}image").attrib["href"],
        )
        self.assertTrue(
            (self.archive_feed.path.parent / item_image_path).is_file(),
            "Wrong item image relative URL in feed",
        )

        # Assert existing downloads not re-downloaded
        self.archive_feed.update()
        for root, _, files in os.walk(self.archive.root_path):
            for archive_basename in files:
                if (
                    archive_basename.endswith("~")
                    or archive_basename == self.archive.FEED_CONFIGS_BASENAME
                ):
                    continue
                archive_path = pathlib.Path(root, archive_basename)
                archive_relative = archive_path.relative_to(self.archive.root_path)
                with self.subTest(
                    msg="Test one feed download",
                    archive_relative=str(archive_relative),
                ):

                    # Assert that the request mock was called correctly
                    download_url = self.archive.path_to_url(archive_path)
                    self.assertIn(
                        download_url,
                        orig_request_mocks,
                        "No mock registered for download request",
                    )
                    _, download_request_mock = orig_request_mocks[download_url]
                    if archive_path != self.archive_feed.path:
                        self.assertEqual(
                            download_request_mock.call_count,
                            1,
                            "Request made for already archived download",
                        )
