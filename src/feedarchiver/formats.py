"""
Handle different feed XML formats.
"""

import logging

logger = logging.getLogger(__name__)


def query_xpath(elem, xpath):
    """
    Return the XPath match raising or logging errors if not one.
    """
    xpath_results = elem.xpath(xpath)
    if not xpath_results:  # pragma: no cover
        raise ValueError(f"Matched nothing for {elem.tag!r}: {xpath!r}")
    elif len(xpath_results) != 1:  # pragma: no cover
        logger.error(
            "Matched %s results for %r: %r",
            len(xpath_results),
            elem,
            xpath,
        )
    return xpath_results[0]


class FeedFormat:
    """
    An abstract feed XML format, such as RSS or Atom.
    """

    ROOT_TAG = ""
    ITEM_TAG = ""

    ITEMS_PARENT_XPATH = ""
    ITEMS_XPATH = ""
    ITEM_ID_XPATH = ""

    def get_items_parent(self, feed_root):
        """
        Return the element that contains all feed item elements per the feed format.
        """
        return query_xpath(feed_root, self.ITEMS_PARENT_XPATH)

    def iter_items(self, feed_root):
        """
        Iterate over the feed items given a feed tree root element.
        """
        return self.get_items_parent(feed_root).xpath(self.ITEMS_XPATH)

    def get_item_id(self, item_elem):
        """
        Return the item element value that uniquely identifies it within this feed.
        """
        item_id = query_xpath(item_elem, self.ITEM_ID_XPATH)
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
    ITEM_TAG = "item"

    ITEMS_PARENT_XPATH = f"/*[local-name() = '{ROOT_TAG}']/*[local-name() = 'channel']"
    ITEMS_XPATH = f"./*[local-name() = '{ITEM_TAG}']"
    ITEM_ID_XPATH = "./*[local-name() = 'guid']/text()"


class AtomFeedFormat(FeedFormat):
    """
    Handle the Atom feed XML format.
    """

    ROOT_TAG = "feed"
    ITEM_TAG = "entry"

    ITEMS_PARENT_XPATH = "."
    ITEMS_XPATH = f"./*[local-name() = '{ITEM_TAG}']"
    ITEM_ID_XPATH = "./*[local-name() = 'id']/text()"
