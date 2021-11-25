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
    ITEM_ID_TAG = ""

    ITEMS_PARENT_XPATH = ""

    def __init_subclass__(cls, /, **kwargs):
        """Assemble the XPath components from the format constants.

        Done here so that the resulting XPaths are import-time constants that can be
        overridden by power users, either in their own subclasses or in some future
        configuration option.  The assembled paths can also be printed in logs or CLI
        help so that such power users can use them as a basis for modification.
        """
        super().__init_subclass__(**kwargs)

        cls.ITEMS_XPATH = f"./*[local-name() = '{cls.ITEM_TAG}']"
        cls.ITEM_ID_XPATH = f"./*[local-name() = '{cls.ITEM_ID_TAG}']/text()"

        logger.debug(
            "%s XPaths:\n%s",
            cls.__name__,
            "\n".join(
                f"{attr_name}={xpath}"
                for attr_name, xpath in vars(cls).items()
                if attr_name.endswith("_XPATH")
            ),
        )

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
    ITEM_ID_TAG = "guid"

    ITEMS_PARENT_XPATH = f"/*[local-name() = '{ROOT_TAG}']/*[local-name() = 'channel']"


class AtomFeedFormat(FeedFormat):
    """
    Handle the Atom feed XML format.
    """

    ROOT_TAG = "feed"
    ITEM_TAG = "entry"
    ITEM_ID_TAG = "id"

    ITEMS_PARENT_XPATH = "."
