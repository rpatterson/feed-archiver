"""
Handle different feed XML formats.
"""


class FeedFormat:
    """
    An abstract feed XML format, such as RSS or Atom.
    """

    ROOT_TAG = ""
    ITEMS_PARENT_TAG = ""
    ITEM_TAG = ""
    ITEM_ID_TAG = ""

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


class RssFeedFormat(FeedFormat):
    """
    Handle the RSS feed XML format.
    """

    ROOT_TAG = "rss"
    ITEMS_PARENT_TAG = "channel"
    ITEM_TAG = "item"
    ITEM_ID_TAG = "guid"
