"""
Utility functions or other shared constants and values.

Particularly useful to avoid circular imports.
"""

import os
import functools
import copy
import mimetypes
import urllib.parse
import email
import logging
import tracemalloc

import feedparser

from lxml import etree  # nosec B410

logger = logging.getLogger(__name__)

# Configure the XML parser as securely as possible since we're parsing XML from
# untrusted sources:
# https://lxml.de/FAQ.html#how-do-i-use-lxml-safely-as-a-web-service-endpoint
XML_PARSER = etree.XMLParser(resolve_entities=False)

TRUE_STRS = {"1", "true", "yes", "on"}
DEBUG = (  # noqa: F841
    "DEBUG" in os.environ and os.environ["DEBUG"].strip().lower() in TRUE_STRS
)
POST_MORTEM = (  # noqa: F841
    "POST_MORTEM" in os.environ
    and os.environ["POST_MORTEM"].strip().lower() in TRUE_STRS
)
PYTHONTRACEMALLOC = (
    "PYTHONTRACEMALLOC" in os.environ
    and os.environ["PYTHONTRACEMALLOC"].strip().lower()
)

PRIORITY_TYPES = {
    "application/xml": ".xml",
    "audio/ogg": ".ogg",
    "video/x-matroska": ".mkv",
    # Not actually needed as overrides but found in the wild
    # and not in `/etc/mime.types`
    "application/rss+xml": ".rss",  # `application/x-rss+xml` in `/etc/mime.types`
}


def init(files=None, priority_types=None):
    """
    Fix broken defaults in the Python's `mimetypes` standard library module.

    https://bugs.python.org/issue1043134

    Unfortunately, the defaults in the `mimetypes` module are wrong; `application/xml`
    for example is associated with `.xsl`.  Also unfortunately, `**/mime.types` files
    are also often wrong; `audio/mpeg` for example is associated with `.mpga`, at least
    in Ubuntu's `/etc/mime.types`.  Since both are wrong in different ways, there's no
    avoiding manual intervention.

    For each given priority type, ensure that the extension is returned first.
    Internally, the `mimetypes` module relies on the order in which types are added to
    the registry to decide which extension/suffix is first and thus the default for a
    given MIME type.  As such, for each priority type we manually move the priority
    extension to the front of the list extensions are appended to when they're added.
    Also requires promoting any such types to `strict=True` types if they were
    originally registered as `strict=False`.
    """
    if priority_types is None:  # pragma: no cover
        priority_types = PRIORITY_TYPES

    # Ensure the standard library module has registered all the types first
    mimetypes.init(files=files)
    mimetypes_db = mimetypes._db  # pylint: disable=protected-access
    strict_types_map_inv = mimetypes_db.types_map_inv[True]
    loose_types_map_inv = mimetypes_db.types_map_inv[False]

    # Manually promote the priority extensions to the front of the list
    for priority_type, priority_ext in priority_types.items():
        priority_type = priority_type.lower()
        if priority_type not in strict_types_map_inv:
            # Must re-register as a strict type first
            mimetypes.add_type(priority_type, priority_ext)
        for types_map_inv in (strict_types_map_inv, loose_types_map_inv):
            if priority_type not in types_map_inv:
                continue
            extensions = types_map_inv[priority_type] = list(
                types_map_inv[priority_type],
            )
            if priority_ext not in extensions:  # pragma: no cover
                continue
            extensions.remove(priority_ext)
            extensions.insert(0, priority_ext)


init()


# Abuse URL quoting for paths that are safe across filesystems:
# - *do* quote (IOW, do *not* allow) "/"
# - do *not* quote (IOW, *do* allow) spaces and other special characters found not to
#   cause problems
#
# So far, special characters have been checked in a Samba share as browsed in the
# Windows 10 explorer in order to determine which should be allowed/unquoted.  The `%`
# character works in this test bed but of course it *must* be quoted, otherwise quoting
# and unquoting would not be symmetrical.  A directory with a Unicode character was also
# tested against this environment and found to be working but it doesn't seem possible
# to get `urllib.parse.quote` to leave them unquoted.  Test files were generated in the
# Samba share from the Linux side using the following:
#
#     tmp_path = pathlib.Path("/media/Library/tmp/feed-archiver")
#     [
#         (tmp_path / f"{char_idx}{char}").write_text("")
#         for char_idx, char in enumerate(string.printable)
#         if urllib.parse.quote(char, safe=" ").startswith("%")
#     ]
#
# Please do report any additional cases that cause issues in any other
# common filesystems.
SAFE_CHARS_WIN10_SAMBA = " !#$&'()+,;=@[]^`{}"
QUOTED_SEP = urllib.parse.quote(os.sep, safe="")
QUOTED_ALTSEP = None
if os.altsep is not None:  # pragma: no cover
    QUOTED_ALTSEP = urllib.parse.quote(os.altsep)
quote_basename = functools.partial(urllib.parse.quote, safe=SAFE_CHARS_WIN10_SAMBA)
quote_path = functools.partial(
    urllib.parse.quote,
    safe=f"{SAFE_CHARS_WIN10_SAMBA}{os.sep}{os.altsep}",
)


def quote_sep(string_):  # noqa: V103
    """
    Return the string with all occurrences of path separators, slashes, quoted.

    Useful to sanitize input from feed XML when used in enclosure template plugin string
    formats from adding unintended path parts.
    """
    quoted = string_.replace(os.sep, QUOTED_SEP)
    if os.altsep is not None:  # pragma: no cover
        quoted = quoted.replace(os.altsep, QUOTED_ALTSEP)
    return quoted


def compare_memory_snapshots(parent):  # pragma: no cover
    """
    Compare two traemalloc snapshots and log the results.
    """
    snapshot = tracemalloc.take_snapshot()
    if getattr(parent, "tracemalloc_snapshot", None) is not None:
        stats = snapshot.compare_to(
            parent.tracemalloc_snapshot,
            "lineno",
        )
        logger.debug(
            "Memory consumption changes:\n%s",
            "\n".join(str(stat) for stat in stats[:10]),
        )
    return snapshot


def parse_content_type(content_type):
    """
    Parse an RFC822-style `Content-Type` header.

    Useful to safely extract the MIME type from the charset.
    """
    message = email.message.Message()
    message["Content-Type"] = content_type
    return message.get_params()[0][0]


def copy_empty_items_parent(feed_format, items_parent):
    """
    Create an `etree` copy of the feed items parent without any items.

    Useful for richer parsing of single items at a time.
    """
    items_parent_copy = etree.Element(items_parent.tag, items_parent.attrib)
    for child in items_parent:
        if child.tag == feed_format.ITEM_TAG:
            # Optimization: This is not strictly correct as feed XML may contain
            # non-item elements after feed item elements, either interspersed or at the
            # end.  This is rare, however, in fact I've never seen an instance of it,
            # items are *most* of a feed's elements and use of the items parent other
            # elements in enclosure plugin configurations is rare, so avoid unnecessary
            # iteration until someone reports an issue with this.
            break
        items_parent_copy.append(copy.deepcopy(child))
    return items_parent_copy


# We need to parse the archive and remote feed XML using `etree` because we need to be
# able to modify the XML and write it to the archive, something that `feedparser`
# doesn't provide.  enclosure plugins, however, frequently need the richer parsing
# support that `feedparser` *does* provide, such as parsing dates and times.  That rich
# parsing is only needed in the rare case of new items being added to the archive's
# version of the feed, so only do the rich parsing on a per-item basis.
def parse_item_feed(feed_format, feed_elem, item_elem):
    """
    Reconstruct a "feed" of just one item and return the richly parsed version.
    """
    item_feed_elem = copy_empty_items_parent(feed_format, feed_elem)
    item_feed_elem.append(copy.deepcopy(item_elem))
    return feedparser.parse(etree.tostring(item_feed_elem))
