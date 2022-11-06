"""
Modifications to the standard library and other helpers.
"""

import os
import functools
import mimetypes
import urllib.parse
import logging
import tracemalloc

logger = logging.getLogger(__name__)

TRUE_STRS = {"1", "true", "yes", "on"}
DEBUG = "DEBUG" in os.environ and os.getenv("DEBUG").strip().lower() in TRUE_STRS
POST_MORTEM = (
    "POST_MORTEM" in os.environ
    and os.getenv("POST_MORTEM").strip().lower() in TRUE_STRS
)
PYTHONTRACEMALLOC = (
    "PYTHONTRACEMALLOC" in os.environ and os.getenv("PYTHONTRACEMALLOC").strip().lower()
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
        if priority_type not in strict_types_map_inv:  # pragma: no cover
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
quote_basename = functools.partial(urllib.parse.quote, safe=SAFE_CHARS_WIN10_SAMBA)
quote_path = functools.partial(
    urllib.parse.quote,
    safe=f"{SAFE_CHARS_WIN10_SAMBA}{os.sep}{os.altsep}",
)


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
