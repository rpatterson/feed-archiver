"""
An archive of RSS/Atom syndication feeds.
"""

import pathlib
import urllib.parse


class Archive:
    """
    An archive of RSS/Atom syndication feeds.
    """

    def __init__(self, root_dir):
        """
        Instantiate a representation of an archive from a file-system path.
        """
        self.root_path = pathlib.Path(root_dir)

    def url_to_path(self, url):
        """
        Escape the URL to a safe file-system path within the archive.
        """
        split_url = urllib.parse.urlsplit(url)
        split_path = split_url._replace(
            # Only want the path, empty scheme and host
            scheme="",
            netloc="",
            # Want a relative path, strip the leading, root slash
            path=split_url.path.lstrip("/"),
        )
        # Use `pathlib.PurePosixPath` to split on forward slashes in the URL regardless
        # of what the path separator is for this platform
        archive_path = pathlib.PurePosixPath(
            urllib.parse.quote(split_url.scheme),
            urllib.parse.quote(split_url.netloc),
            urllib.parse.quote(split_path.geturl()),
        )
        return self.root_path / archive_path

    def path_to_url(self, path):
        """
        Un-escape the safe file-system path within the archive to a URL.
        """
        # Also accept strings
        path = pathlib.Path(path)
        archive_path = path.relative_to(self.root_path)
        split_url = urllib.parse.SplitResult(
            scheme=urllib.parse.unquote(archive_path.parts[0]),
            netloc=urllib.parse.unquote(archive_path.parts[1]),
            path=str(
                pathlib.PurePosixPath(
                    *[urllib.parse.unquote(part) for part in archive_path.parts[2:]]
                )
            ),
            query="",
            fragment="",
        )
        return split_url.geturl()
