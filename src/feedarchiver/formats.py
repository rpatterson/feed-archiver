"""
Handle different feed XML formats.
"""

import logging

from lxml import etree

logger = logging.getLogger(__name__)


def query_xpath(elem, xpath):
    """
    Return the XPath match raising or logging errors if not one.
    """
    xpath_results = elem.xpath(xpath)
    if not xpath_results:  # pragma: no cover
        raise ValueError(f"Matched nothing for {elem.tag!r}: {xpath!r}")
    if len(xpath_results) != 1:  # pragma: no cover
        logger.error(
            "Matched %s results for %r: %r",
            len(xpath_results),
            elem,
            xpath,
        )
    return xpath_results[0]


def all_xpaths_results(elem, xpaths):
    """
    Return the results of all xpaths combined, IOW `OR`.
    """
    return elem.xpath(" | ".join(xpaths))


class FeedFormat:
    """
    An abstract feed XML format, such as RSS or Atom.
    """

    # Constants that define the structural specifics that differ between the formats,
    # mostly tag and attribute names.
    ROOT_TAG = ""
    ITEM_TAG = ""
    ITEM_ID_TAG = ""
    DOWNLOAD_TEXT_TAGS = ["link", "url"]
    DOWNLOAD_CONTENT_TAGS = ["enclosure", "content"]
    DOWNLOAD_CONTENT_EXPR = "@rel='enclosure'"
    DOWNLOAD_ATTR_NAMES = ["href", "url", "src"]

    # XPaths that differ between formats but can't be generalized from the above
    ITEMS_PARENT_XPATH = ""
    SELF_LINK_XPATH = "./*[local-name() = 'link' and @rel = 'self']"

    # Map format-specific sub-classes to their corresponding root tag name.
    # Used to match a parsed feed XML tree to the corresponding format.
    FEED_FORMATS = {}

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

        download_text_expr = cls.assemble_download_text_expr()
        download_attr_step = cls.assemble_download_attr_step()
        download_feed_prefix = (
            f"{cls.ITEMS_PARENT_XPATH}/*[not(local-name() = '{cls.ITEM_TAG}')"
        )
        cls.DOWNLOAD_FEED_URLS_XPATHS = [
            f"{download_feed_prefix} and {download_text_expr}]/text()",
            f"{download_feed_prefix}]//{download_attr_step}",
        ]
        download_content_tags_expr = " or ".join(
            f"local-name()='{download_content_tag}'"
            for download_content_tag in cls.DOWNLOAD_CONTENT_TAGS
        )
        download_content_expr = (
            f"{download_content_tags_expr} or {cls.DOWNLOAD_CONTENT_EXPR}"
        )
        cls.DOWNLOAD_ITEM_ASSET_URLS_XPATHS = [
            f".//*[{download_text_expr}]/text()",
            f".//*[not({download_content_expr})]/{download_attr_step}",
        ]
        cls.DOWNLOAD_ITEM_CONTENT_URLS_XPATHS = [
            f".//*[{download_content_expr}]/{download_attr_step}",
        ]

        # Register this specific feed format by it's root element tag name
        cls.FEED_FORMATS[cls.ROOT_TAG] = cls

        logger.debug(
            "%s XPaths:\n%s",
            cls.__name__,
            "\n".join(
                f"{attr_name}={xpath}"
                for attr_name, xpath in vars(cls).items()
                if attr_name.endswith("_XPATH")
            ),
        )

    def __init__(self, archive_feed):
        """
        Capture a reference to the ArchiveFeed using this feed format.
        """
        self.archive_feed = archive_feed

    @classmethod
    def assemble_download_text_expr(cls):
        """
        Construct the Path predicate expression for text nodes containing URLs.

        Used to combine with other expressions inside different predicates for
        feed-level vs item-level queries.
        """
        elem_expr = " or ".join(
            f"local-name() = '{download_text_tag}'"
            for download_text_tag in cls.DOWNLOAD_TEXT_TAGS
        )
        attr_expr = " or ".join(
            f"@{download_attr_name}" for download_attr_name in cls.DOWNLOAD_ATTR_NAMES
        )
        return f"({elem_expr}) and not({attr_expr})"

    @classmethod
    def assemble_download_attr_step(cls):
        """
        Construct the XPath location step for element attributes containing URLs.
        """
        attr_expr = " or ".join(
            f"local-name()='{download_attr_name}'"
            for download_attr_name in cls.DOWNLOAD_ATTR_NAMES
        )
        return f"@*[{attr_expr}]"

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
        if not item_id.strip():  # pragma: no cover
            raise ValueError(f"Empty feed item ID: {self.ITEM_ID_XPATH!r}")
        return item_id.strip()

    @classmethod
    def from_tree(cls, archive_feed, feed_tree):
        """
        Identify feed format from parsed ElementTree, return corresponding format.

        Be as permissive as possible in identifying the feed format to tolerate poorly
        behaved feeds (e.g. wrong `Content-Type` header, XML namespace, etc.).  Identify
        feeds by the top-level XML tag name (e.g. `<rss>` or `<feed>`).
        """
        feed_root = feed_tree.getroot()
        feed_root_tag = etree.QName(feed_root.tag).localname.lower()
        if feed_root_tag not in cls.FEED_FORMATS:  # pragma: no cover
            raise NotImplementedError(
                f"No feed format handler for {feed_root.tag!r} root element"
            )
        return cls.FEED_FORMATS[feed_root_tag](archive_feed)


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
