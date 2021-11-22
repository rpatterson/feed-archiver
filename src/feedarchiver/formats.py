"""
Handle different feed XML formats.
"""

import logging

logger = logging.getLogger(__name__)


class FeedFormat:
    """
    An abstract feed XML format, such as RSS or Atom.
    """

    ROOT_TAG = ""

    ITEMS_PARENT_XPATH = ""
    ITEMS_XPATH = ""
    ITEM_ID_XPATH = ""

    def get_items_parent(self, feed_root):
        """
        Return the element that contains all feed item elements per the feed format.
        """
        items_parents = feed_root.xpath(self.ITEMS_PARENT_XPATH)
        if not items_parents:  # pragma: no cover
            raise ValueError(
                f"Could not find feed items parent element: {self.ITEMS_PARENT_XPATH!r}"
            )
        elif len(items_parents) != 1:  # pragma: no cover
            logger.error(
                "Found more than one feed items parent element: %r",
                self.ITEMS_PARENT_XPATH,
            )
        return items_parents[0]

    def iter_items(self, feed_root):
        """
        Iterate over the feed items given a feed tree root element.
        """
        return self.get_items_parent(feed_root).xpath(self.ITEMS_XPATH)

    def get_item_id(self, item_elem):
        """
        Return the item element value that uniquely identifies it within this feed.
        """
        item_ids = item_elem.xpath(self.ITEM_ID_XPATH)
        if not item_ids:  # pragma: no cover
            raise ValueError(f"Could not find feed item ID: {self.ITEM_ID_XPATH!r}")
        elif len(item_ids) != 1:  # pragma: no cover
            logger.error(
                "Found more than one feed item ID: %r",
                self.ITEM_ID_XPATH,
            )
        item_id = item_ids[0]
        if not isinstance(item_id, str):  # pragma: no cover
            raise ValueError(f"Item ID is not a string: {self.ITEM_ID_XPATH!r}")
        elif not item_id.strip():  # pragma: no cover
            raise ValueError(f"Empty feed item ID: {self.ITEM_ID_XPATH!r}")
        return item_id.strip()


class RssFeedFormat(FeedFormat):
    """
    Handle the RSS feed XML format.
    """

    ROOT_TAG = "rss"

    ITEMS_PARENT_XPATH = f"/*[local-name() = '{ROOT_TAG}']/*[local-name() = 'channel']"
    ITEMS_XPATH = "./*[local-name() = 'item']"
    ITEM_ID_XPATH = "./*[local-name() = 'guid']/text()"


class AtomFeedFormat(FeedFormat):
    """
    Handle the Atom feed XML format.
    """

    ROOT_TAG = "feed"

    ITEMS_PARENT_XPATH = "."
    ITEMS_XPATH = "./*[local-name() = 'entry']"
    ITEM_ID_XPATH = "./*[local-name() = 'id']/text()"
