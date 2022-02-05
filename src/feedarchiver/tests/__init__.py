"""
Tests for this feed archiver foundation or template.
"""

import os
import datetime
import pathlib
import tempfile
import shutil
import email.utils
import unittest

from lxml import etree

import requests_mock

from .. import utils
from .. import archive
from ..utils import mimetypes


class FeedarchiverTestCase(
    unittest.TestCase,
):  # pylint: disable=too-many-instance-attributes
    """
    Constants and set-up used in all feed-archiver tests.
    """

    maxDiff = None

    # A date and time in the past all but guaranteed not to exist naturally in the
    # checkout.
    OLD_DATETIME = datetime.datetime(year=1980, month=11, day=25, hour=8, minute=31)
    # The relative path to the example/sample test data this test will use.
    # Default examples are copied from the Wikipedia page of each RSS/Atom syndication
    # XML format to represent the cleanest, simplest form of feeds.
    EXAMPLE_RELATIVE = pathlib.Path("simple")
    # Relative path to the feed XML content in the checkout test data to be used to mock
    # responses to requests for the remote feed URL.
    REMOTE_MOCK = pathlib.Path("orig")
    # Relative path that corresponds to the remote feed URL within the archive.
    FEED_ARCHIVE_STEM = "garply"
    FEED_ARCHIVE_SUFFIX = ".rss"
    FEED_ARCHIVE_QUERY = "?bar=qux%2Fbaz#corge"
    FEED_ARCHIVE_RELATIVE = pathlib.Path(
        "https",
        "foo-username%3Asecret@grault.example.com",
        "feeds",
        f"{FEED_ARCHIVE_STEM}{utils.quote_basename(FEED_ARCHIVE_QUERY)}"
        f"{FEED_ARCHIVE_SUFFIX}",
    )

    # Test data in the checkout that represents remote feed data
    REMOTES_PATH = pathlib.Path(__file__).parent / "remotes"
    # Test data in the checkout that represents local archived feed data.
    ARCHIVES_PATH = REMOTES_PATH.parent / "archives"

    SONARR_URL = "http://localhost:8989"

    def setUp(self):
        """
        Set up used in all feed-archiver tests.
        """
        super().setUp()

        # Mock HTTP/S requests:
        # https://requests-mock.readthedocs.io/en/latest/fixture.html#fixtures
        self.requests_mock = requests_mock.Mocker()
        self.addCleanup(self.requests_mock.stop)
        self.requests_mock.start()

        # Create a temporary directory for mutable test data
        self.tmp_dir = (
            tempfile.TemporaryDirectory(  # pylint: disable=consider-using-with
                suffix=self.EXAMPLE_RELATIVE.suffix,
                prefix=f"{self.EXAMPLE_RELATIVE.stem}-",
            )
        )
        self.addCleanup(self.tmp_dir.cleanup)

        # Use the example/sample test data basename to assemble the rest of the
        # filesystem paths used by the tests.
        self.remotes_path = self.REMOTES_PATH / self.EXAMPLE_RELATIVE
        self.archive_path = self.ARCHIVES_PATH / self.EXAMPLE_RELATIVE

        # Copy the testing example feeds archive
        shutil.copytree(
            src=self.archive_path,
            dst=self.tmp_dir.name,
            dirs_exist_ok=True,
        )
        self.archive = archive.Archive(self.tmp_dir.name)
        # Mock the Sonarr request that is sent when the config is loaded
        self.requests_mock.get(
            f"{self.SONARR_URL}/api/v3/system/status?apikey=secret",
            json=dict(version="3.0.6.1342"),
        )
        self.archive.load_config()
        self.archive_feed = self.archive.archive_feeds[0]
        self.feed_url = self.archive_feed.url
        self.feed_path = self.archive.root_path / self.FEED_ARCHIVE_RELATIVE

    def mock_remote(self, archive_feed, remote_mock=None):
        """
        Mock the request responses with the mock dir.

        The relative paths in the mock dir are un-escaped to URLs and used to create the
        request mocks for those URLs.
        """
        if remote_mock is None:
            remote_mock = self.REMOTE_MOCK

        request_mocks = {}
        remote_mock_path = self.REMOTES_PATH / self.EXAMPLE_RELATIVE / remote_mock
        for mock_path, _ in walk_archive(remote_mock_path):
            mock_stat = mock_path.stat()
            mock_bytes = mock_path.read_bytes()
            mock_headers = {
                "Last-Modified": email.utils.formatdate(
                    timeval=mock_stat.st_mtime,
                    usegmt=True,
                ),
                "Content-Length": str(len(mock_bytes)),
            }
            mock_type, _ = mimetypes.guess_type(mock_path.name)
            if mock_type:
                mock_headers["Content-Type"] = mock_type
            mock_url = archive_feed.archive.path_to_url(
                archive_feed.archive.root_path / mock_path.relative_to(remote_mock_path)
            )
            request_mocks[mock_url] = (
                mock_path,
                self.requests_mock.get(
                    mock_url,
                    # Ensure the download response includes `Last-Modified`
                    headers=mock_headers,
                    content=mock_bytes,
                ),
            )
        return request_mocks

    def update_feed(self, archive_feed, remote_mock=None):
        """
        Mock the request responses with the mock dir and update the archive.
        """
        request_mocks = self.mock_remote(archive_feed, remote_mock)
        updated_feeds = archive_feed.update()
        return request_mocks, updated_feeds

    def assert_no_header_download_mtime(self, no_header_request_mock, download_path):
        """
        Assert that download responses without headers are handled gracefully.
        """
        self.archive_feed.update()
        self.assertEqual(
            no_header_request_mock.call_count,
            1,
            "Wrong number of feed URL requests without metadata headers",
        )
        self.assertNotEqual(
            datetime.datetime.fromtimestamp(download_path.stat().st_mtime),
            self.OLD_DATETIME,
            "Archive feed modification date not current",
        )


class FeedarchiverDownloadsTestCase(FeedarchiverTestCase):
    """
    Test against a rich, full-featured feed including enclosures.
    """

    EXAMPLE_RELATIVE = pathlib.Path("downloads")

    # Constants specific to this test suite
    FEED_ARCHIVE_RELATIVE = pathlib.Path(
        "https",
        "foo.example.com",
        "podcast",
        "feed.rss",
    )
    ITEM_SLUG_PREFIX = "el-ni%C3%B1o"
    ITEM_SLUG = f"{ITEM_SLUG_PREFIX}-episode-title"
    ENCLOSURE_URL = f"https://foo.example.com/podcast/episodes/{ITEM_SLUG}/download"
    ENCLOSURE_RELATIVE = pathlib.Path(
        "https",
        "foo.example.com",
        "podcast",
        "episodes",
        utils.quote_basename(ITEM_SLUG),
        "download",
    )
    ENCLOSURE_MOCK_PATH = (
        FeedarchiverTestCase.REMOTES_PATH
        / EXAMPLE_RELATIVE
        / FeedarchiverTestCase.REMOTE_MOCK
        / ENCLOSURE_RELATIVE
    )
    ENCLOSURE_REDIRECT_URL = f"https://bar.example.com/media/{ITEM_SLUG_PREFIX}.mp3"

    def archive_relative_to_remote_url(self, archive_relative, remote_mock_path):
        """
        Return the remote URL for the archive path adjusted for the mocks.
        """
        mock_path = remote_mock_path / archive_relative
        remote_url_path = self.archive.root_path / archive_relative
        if archive_relative == self.ENCLOSURE_RELATIVE.with_suffix(".mp3"):
            # Adjust for the case where the remote URL is missing the
            # suffix/extension
            remote_url_path = remote_url_path.with_suffix("")
            mock_path = mock_path.with_suffix("")
        return self.archive.path_to_url(remote_url_path), mock_path


def get_feed_items(feed_path):
    """
    Map item ID to item element for all the items in the given feed XML.
    """
    with feed_path.open() as feed_opened:
        tree = etree.parse(feed_opened)
    channel = tree.getroot().find("channel")
    return {
        item_elem.find("guid").text: item_elem for item_elem in channel.iter("item")
    }


def walk_archive(archive_root_path):
    """
    Walk the given path like `os.path` but excluding what we want to ignore for tests.
    """
    for root, _, files in os.walk(archive_root_path, followlinks=True):
        root_path = pathlib.Path(root)
        root_relative = root_path.relative_to(archive_root_path)
        # Directories we don't want to "descend" into
        if {
            archive_root_part
            for archive_root_part in pathlib.Path(root).parts
            if archive_root_part.endswith("~")
        } or (
            root_relative.parts
            and root_relative.parts[0]
            in {
                "Feeds",
                "Music",
                "Videos",
            }
        ):  # pragma: no cover
            continue
        for archive_basename in files:
            if (
                archive_basename.endswith("~")
                or archive_basename == archive.Archive.FEED_CONFIGS_BASENAME
            ):  # pragma: no cover
                continue
            archive_path = root_path / archive_basename
            archive_relative = archive_path.relative_to(archive_root_path)
            yield archive_path, archive_relative
