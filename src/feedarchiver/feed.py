"""
An RSS/Atom syndication feed in an archive.
"""

from lxml import etree

from . import formats


class ArchiveFeed:
    """
    An RSS/Atom syndication feed in an archive.
    """

    FEED_FORMATS = {
        feed_format.ROOT_TAG: feed_format
        for feed_format in vars(formats).values()
        if isinstance(feed_format, type) and issubclass(feed_format, formats.FeedFormat)
    }

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
        feed_archive_path = self.archive.url_to_path(self.url)
        feed_response = self.archive.requests.get(self.url)
        remote_root = etree.fromstring(feed_response.content)

        # Be as permissive as possible in identifying the feed format to tolerate poorly
        # behaved feeds (e.g. wrong `Content-Type` header, XML namespace, etc.).
        # Identify feeds by the top-level XML tag name (e.g. `<rss>` or `<feed>`).
        remote_root_tag = etree.QName(remote_root.tag).localname.lower()
        if remote_root_tag not in self.FEED_FORMATS:  # pragma: no cover
            raise NotImplementedError(
                f"No feed format handler for {remote_root.tag!r} root element"
            )
        feed_format = self.FEED_FORMATS[remote_root_tag]()

        if not feed_archive_path.exists():
            # First time requesting this feed, simply copy the remote feed to the
            # archive
            feed_archive_path.parent.mkdir(parents=True, exist_ok=True)
            with feed_archive_path.open("w") as feed_archive_opened:
                feed_archive_opened.write(feed_response.text)

            updated_items.update(
                (feed_format.get_item_id(remote_item_elem), remote_item_elem)
                for remote_item_elem in feed_format.iter_items(remote_root)
            )
            return updated_items

        with feed_archive_path.open() as feed_archive_opened:
            archive_tree = etree.parse(feed_archive_opened)
        archive_root = archive_tree.getroot()
        archived_items_parent = feed_format.get_items_parent(archive_root)
        archived_items_iter = feed_format.iter_items(archive_root)
        archived_item_ids = set()

        # Iterate through the remote feed to make updates to the archived feed as
        # appropriate.
        for remote_item_elem in feed_format.iter_items(remote_root):
            remote_item_id = feed_format.get_item_id(remote_item_elem)
            if remote_item_id in archived_item_ids:
                # This item was already seen in the archived feed, we don't need to
                # update the archive or search further in the archived feed.
                continue
            for archived_item_elem in archived_items_iter:
                archived_item_ids.add(feed_format.get_item_id(archived_item_elem))
                if remote_item_id in archived_item_ids:
                    # Found this item in the archived feed, we don't need to
                    # update the archive and we can stop searching the archived feed for
                    # now.
                    break
            else:
                # The remote item ID was not found in the archived feed, update the feed
                # by adding this remote item.
                updated_items[remote_item_id] = remote_item_elem
                archived_items_parent.insert(0, remote_item_elem)

        if updated_items:
            # Update the archived feed file
            archive_tree.write(str(feed_archive_path))
            return updated_items

        return None
