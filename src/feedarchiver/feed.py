"""
An archive of RSS/Atom syndication feeds.
"""


class ArchiveFeed:
    """
    An archive of one RSS/Atom syndication feed.
    """

    def __init__(self, archive, config, url):
        """
        Instantiate a representation of an archive from a file-system path.
        """
        self.archive = archive
        self.config = config
        self.url = url

    def update(self):
        """
        Request the URL of one feed in the archive and update contents accordingly.
        """
        updated_items = {}
        feed_response = self.archive.requests.get(self.url)
        feed_archive_path = self.archive.url_to_path(self.url)
        feed_archive_path.parent.mkdir(parents=True, exist_ok=True)
        with feed_archive_path.open("w") as feed_archive_opened:
            feed_archive_opened.write(feed_response.text)
        return updated_items
