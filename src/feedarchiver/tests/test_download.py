"""
Test the feed-archiver downloading of enclosures, assets, etc..
"""

import os
import datetime
import pathlib
import urllib

from lxml import etree  # nosec: B410
import respx.models

from .. import utils
from .. import tests


class FeedarchiverDownloadTests(tests.FeedarchiverDownloadsTestCase):
    """
    Test the feed-archiver downloading of enclosures, assets, etc..
    """

    def test_real_requests_disabled(self):
        """
        Confirm that tests will fail if real/external requests are attempted.
        """
        # Put the mocks in place
        self.update_feed(self.archive_feed)
        with self.assertRaises(respx.models.AllMockedAssertionError):
            self.archive.client.get("http://example.com")

    def test_download_file_metadata(self):
        """
        Download file metadata in the archive reflects remote response headers.

        All metadata that can be extracted from the remote response is reflected in the
        file metadata in the archive.
        """
        # Constants specific to this test
        enclosure_archive_path = (
            self.archive.root_path / self.ENCLOSURE_RELATIVE.with_suffix(".mp3")
        )

        # Set the mock file path modification date which is used by the test fixture to
        # set the header on the request mock.
        enclosure_mock_stat = self.ENCLOSURE_MOCK_PATH.stat()
        os.utime(
            self.ENCLOSURE_MOCK_PATH,
            (enclosure_mock_stat.st_atime, self.OLD_DATETIME.timestamp()),
        )

        # Download the enclosure into the archive
        orig_request_mocks = self.mock_remote(self.archive_feed)
        redirect_request_mock = self.client_mock.get(
            self.ENCLOSURE_URL,
        ).respond(
            status_code=302,
            headers={"Location": self.ENCLOSURE_REDIRECT_URL},
        )
        self.archive_feed.update()
        # The archive file's modification time matches.
        self.assertEqual(
            datetime.datetime.fromtimestamp(enclosure_archive_path.stat().st_mtime),
            self.OLD_DATETIME,
            "Archive download modification date doesn't match `Last-Modified` header",
        )

        # The most appropriate file basename is symlinked to the download file
        self.assertEqual(
            redirect_request_mock.call_count,
            1,
            "Wrong number of redirect requests",
        )
        _, target_request_mock = orig_request_mocks[self.ENCLOSURE_REDIRECT_URL]
        self.assertEqual(
            target_request_mock.call_count,
            1,
            "Wrong number of redirect redirect target mock request calls",
        )

        # Test in the absence of the response headers
        self.archive_feed.path.unlink()
        enclosure_archive_path.unlink()
        no_header_request_mock = self.client_mock.get(
            self.ENCLOSURE_URL,
        ).respond(
            content=self.ENCLOSURE_MOCK_PATH.read_bytes(),
        )
        no_header_request_mock.reset()
        self.assert_no_header_download_mtime(
            no_header_request_mock,
            self.archive.root_path / self.ENCLOSURE_RELATIVE.with_suffix(".mp3"),
        )

    def test_downloads(self):  # pylint: disable=too-many-locals
        """
        All files in the archive after update correspond to the fixture.

        This tests for completeness, that nothing in the archive doesn't correspond to a
        request mock in the test fixture and that none of the request mocks in the
        fixture weren't called.
        """
        # Download all feed enclosures and assets
        orig_request_mocks, updated_feeds = self.update_feed(self.archive_feed)
        self.assertGreater(
            len(orig_request_mocks),
            # At least 2 downloads in addition to the feeds themselves
            len(self.archive.archive_feeds) + 1,
            "Too few request mocks registered by test fixture",
        )
        _, download_paths = updated_feeds
        self.assertIsInstance(
            list(download_paths.values())[0],
            str,
            "Wrong download path return type",
        )

        remote_mock_path = self.REMOTES_PATH / self.EXAMPLE_RELATIVE / "orig"
        uncalled_request_mocks = orig_request_mocks.copy()
        # This test is written from the perspective of the archive for completeness.
        # Walk the whole archive so we can make assertions on everything within,
        # including things that shouldn't be there.
        for archive_path, archive_relative in tests.walk_archive(
            self.archive.root_path,
        ):
            with self.subTest(
                msg="Test one feed download",
                archive_relative=str(archive_relative),
            ):
                # Assert that the request mock was called correctly
                download_url, mock_path = self.archive_relative_to_remote_url(
                    archive_relative,
                    remote_mock_path,
                )
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
                self.assertTrue(
                    archive_path.is_file(), "Download is not a file in the archive"
                )
                if archive_path != self.archive_feed.path:
                    self.assertEqual(
                        archive_path.read_bytes(),
                        mock_path.read_bytes(),
                        "Different archived download content from remote",
                    )

        del uncalled_request_mocks[self.ENCLOSURE_REDIRECT_URL]
        for mock_url in list(uncalled_request_mocks.keys()):
            if mock_url.startswith(self.SONARR_URL):  # pragma: no cover
                del uncalled_request_mocks[mock_url]
        self.assertEqual(
            uncalled_request_mocks,
            {},
            # Some request mocks didn't correspond to archive files
            "Archive download missing for request mocks",
        )

        # Assert archive URLs updated
        archive_tree = etree.parse(  # nosec: B320
            self.archive_feed.path.open(),
            parser=utils.XML_PARSER,
        )
        feed_link_split = urllib.parse.urlsplit(
            archive_tree.find("channel").find("link").text,
        )
        feed_link_path = (
            pathlib.PurePosixPath(feed_link_split.path.lstrip("/")) / "index.html"
        )
        self.assertTrue(
            (self.archive.root_path / feed_link_path).is_file(),
            "Wrong feed link index HTML absolute URL in feed",
        )
        feed_href_split = urllib.parse.urlsplit(
            archive_tree.find("channel")
            .find("{http://www.w3.org/2005/Atom}link")
            .attrib["href"]
        )
        feed_href_path = pathlib.PurePosixPath(feed_href_split.path.lstrip("/"))
        self.assertTrue(
            (self.archive_feed.archive.root_path / feed_href_path).is_file(),
            "Wrong feed XML href absolute URL in feed",
        )
        feed_image_split = urllib.parse.urlsplit(
            archive_tree.find("channel")
            .find("{http://www.itunes.com/dtds/podcast-1.0.dtd}image")
            .attrib["href"]
        )
        feed_image_path = pathlib.PurePosixPath(feed_image_split.path.lstrip("/"))
        self.assertTrue(
            (self.archive.root_path / feed_image_path).is_file(),
            "Wrong feed image absolute URL in feed",
        )
        archive_items = archive_tree.find("channel").findall("item")
        archive_item = archive_items[1]
        item_link_split = urllib.parse.urlsplit(archive_item.find("link").text)
        item_link_path = (
            pathlib.PurePosixPath(
                urllib.parse.unquote(item_link_split.path).lstrip("/")
            )
            / "index.html"
        )
        self.assertTrue(
            (self.archive.root_path / item_link_path).is_file(),
            "Wrong item link index HTML absolute URL in feed",
        )
        item_enclosure_split = urllib.parse.urlsplit(
            archive_item.find("enclosure").attrib["url"],
        )
        item_enclosure_path = pathlib.PurePosixPath(
            urllib.parse.unquote(item_enclosure_split.path).lstrip("/"),
        )
        self.assertTrue(
            (self.archive.root_path / item_enclosure_path).is_file(),
            "Wrong item enclosure absolute URL in feed",
        )
        item_media_content_split = urllib.parse.urlsplit(
            archive_item.find("{*}content").attrib["url"],
        )
        item_media_content_path = pathlib.PurePosixPath(
            urllib.parse.unquote(item_media_content_split.path).lstrip("/"),
        )
        self.assertEqual(
            item_media_content_path,
            item_enclosure_path,
            "Wrong item media content absolute URL in feed",
        )
        item_image_split = urllib.parse.urlsplit(
            archive_item.find("{*}image").attrib["href"],
        )
        item_image_path = pathlib.PurePosixPath(
            urllib.parse.unquote(item_image_split.path).lstrip("/"),
        )
        self.assertTrue(
            (self.archive.root_path / item_image_path).is_file(),
            "Wrong item image absolute URL in feed",
        )

        # Assert existing downloads not re-downloaded
        self.archive_feed.update()
        for archive_path, archive_relative in tests.walk_archive(
            self.archive.root_path,
        ):
            with self.subTest(
                msg="Test one feed download",
                archive_relative=str(archive_relative),
            ):
                # Assert that the request mock was called correctly
                download_url, mock_path = self.archive_relative_to_remote_url(
                    archive_relative,
                    remote_mock_path,
                )
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
