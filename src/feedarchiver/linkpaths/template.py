"""
The default link path plugin, expands a template into the target path.
"""

import pathlib

from .. import utils  # noqa, pylint: disable=unused-import
from .. import linkpaths


class TemplateLinkPathPlugin(linkpaths.LinkPathPlugin):
    """
    The default link path plugin, expands a template into the target path.
    """

    # Default a hierarchy under the feed title and item title
    template = str(
        pathlib.Path(
            "Feeds",
            "{feed_elem.find('title').text.strip()}",
            "{item_elem.find('title').text.strip()}",
            "{basename}",
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
        archive_feed,
        feed_elem,
        item_elem,
        url_result,
        basename,
        *args,
        **kwargs,
    ):  # pylint: disable=too-many-arguments
        """
        Link the feed item enclosure/content to a target path expanded from a template.
        """
        # Maybe find a better template format/engine, perhaps Jinja2?
        # We need a templating engine that supports a very rich set of operations
        # sufficient, for example, to extract data from `ElementTree` objects.  This
        # means we need to support execution of arbitrary code.  This shouldn't be a
        # problem since anyone that can run `$ feedarchiver` can also run `$ python`.
        # But still, this has a bad code smell.
        # https://python-forum.io/thread-24481.html
        return [eval(f"f{self.template!r}")]  # pylint: disable=eval-used
