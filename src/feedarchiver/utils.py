"""
Modifications to the standard library and other helpers.
"""

import mimetypes

PRIORITY_TYPES = {
    "application/xml": ".xml",
    "audio/ogg": ".ogg",
    "video/x-matroska": ".mkv",
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
