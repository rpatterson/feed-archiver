"""
The default enclosure plugin, expands a template into the target path.
"""

import pathlib

from .. import utils  # noqa, pylint: disable=unused-import
from .. import enclosures


class TemplateEnclosurePlugin(enclosures.EnclosurePlugin):  # noqa: V102
    """
    The default enclosure plugin, expands a template into the target path.
    """

    # Default a hierarchy under the feed title and item title
    template = str(
        pathlib.Path(
            "Feeds",
            "{utils.quote_sep(feed_parsed.feed.title).strip()}",
            "{utils.quote_sep(item_parsed.title).strip()}{enclosure_path.suffix}",
        )
    )

    def load_config(self):
        """
        Pre-process and validate the plugin config prior to linking each enclosure.
        """
        self.template = self.config.get("template", self.template)
        if not isinstance(self.template, str):  # pragma: no cover
            raise ValueError(
                f"Format `template` for plugin must be a string: {self.template!r}"
            )

    def __call__(
        self,
        *args,
        **kwargs,
    ):  # pylint: disable=too-many-arguments
        """
        Link the feed item enclosure to a target path expanded from a template.
        """
        # Maybe find a better template format/engine, perhaps Jinja2?
        # We need a templating engine that supports a very rich set of operations
        # sufficient, for example, to extract data from `ElementTree` objects.  This
        # means we need to support execution of arbitrary code.  This shouldn't be a
        # problem since anyone that can run `$ feedarchiver` can also run `$ python`.
        # But still, this has a bad code smell.
        # https://python-forum.io/thread-24481.html
        return [
            eval(  # nosec: B307, pylint: disable=eval-used
                f"f{self.template!r}",
                globals(),
                dict(locals(), **kwargs),
            )
        ]
