"""
An archive of RSS/Atom syndication feeds.
"""

from xml import etree


class ArchiveFeed:
    """
    An archive of one RSS/Atom syndication feed.
    """

    # Feed format specifics
    ITEMS_PARENT_TAG = "channel"
    ITEM_TAG = "item"
    ITEM_ID_TAG = "guid"

    def __init__(self, archive, config, url):
        """
        Instantiate a representation of an archive from a file-system path.
        """
        self.archive = archive
        self.config = config
        self.url = url

    def get_items_parent(self, feed_root):
        """
        Return the element that contains all feed item elements per the feed format.
        """
        return feed_root.find(self.ITEMS_PARENT_TAG)

    def iter_items(self, feed_root):
        """
        Iterate over the feed items given a feed tree root element.
        """
        return self.get_items_parent(feed_root).iter(self.ITEM_TAG)

    def get_item_id(self, item_elem):
        """
        Return the item element value that uniquely identifies it within this feed.
        """
        id_elem = item_elem.find(self.ITEM_ID_TAG)
        if id_elem is None:  # pragma: no cover
            raise ValueError(
                f"Could not find feed item unique identifier: {self.ITEM_ID_TAG}"
            )
        return id_elem.text.strip()

    def update(self):
        """
        Request the URL of one feed in the archive and update contents accordingly.
        """
        updated_items = {}
        feed_archive_path = self.archive.url_to_path(self.url)
        feed_response = self.archive.requests.get(self.url)
        remote_root = etree.ElementTree.fromstring(feed_response.text)

        if not feed_archive_path.exists():
            # First time requesting this feed, simply copy the remote feed to the
            # archive
            feed_archive_path.parent.mkdir(parents=True, exist_ok=True)
            with feed_archive_path.open("w") as feed_archive_opened:
                feed_archive_opened.write(feed_response.text)

            updated_items.update(
                (self.get_item_id(remote_item_elem), remote_item_elem)
                for remote_item_elem in self.iter_items(remote_root)
            )
            return updated_items

        archive_tree = etree.ElementTree.parse(feed_archive_path)
        archive_root = archive_tree.getroot()
        archived_items_parent = self.get_items_parent(archive_root)
        archived_items_iter = self.iter_items(archive_root)
        archived_item_ids = set()

        # Iterate through the remote feed to make updates to the archived feed as
        # appropriate.
        for remote_item_elem in self.iter_items(remote_root):
            remote_item_id = self.get_item_id(remote_item_elem)
            if remote_item_id in archived_item_ids:
                # This item was already seen in the archived feed, we don't need to
                # update the archive or search further in the archived feed.
                continue
            for archived_item_elem in archived_items_iter:
                archived_item_ids.add(self.get_item_id(archived_item_elem))
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
            archive_tree.write(feed_archive_path)
            return updated_items

        return None
