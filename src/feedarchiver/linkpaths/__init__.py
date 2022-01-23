"""
Plugins for linking feed item enclosures/content into media libraries.
"""

import sys
import re
import pprint

if sys.version_info < (3, 10):  # pragma: no cover
    # BBB:
    # https://packaging.python.org/en/latest/guides/creating-and-discovering-plugins/#using-package-metadata
    from importlib_metadata import entry_points
else:  # pragma: no cover
    from importlib.metadata import entry_points


def load_plugins(parent, parent_config):
    """
    Pre-process and validate the content link path configurations.
    """
    archive = getattr(parent, "archive", parent)
    link_path_defaults = archive.global_config.get("plugins", {}).get("link-paths", {})
    link_path_configs = parent_config.get("link-paths", [])
    if not isinstance(link_path_configs, list):  # pragma: no cover
        raise ValueError(
            f"Link paths must be a list/array:\n{pprint.pformat(link_path_configs)}"
        )
    link_path_entrypoints = entry_points(group="feedarchiver.linkpaths")
    for link_path_config in link_path_configs:
        # Perform any validation as early as possible
        link_path_plugin_name = link_path_config.get("plugin", "default")
        if link_path_plugin_name not in link_path_entrypoints.names:  # pragma: no cover
            raise ValueError(
                f"Link path plugin name not registered: {link_path_plugin_name}",
            )
        if (
            "match-pattern" in link_path_config
            and "match-string" not in link_path_config
        ) or (
            "match-string" in link_path_config
            and "match-pattern" not in link_path_config
        ):  # pragma: no cover
            raise ValueError(
                "Link path plugin config must define either both ``match-pattern`` and"
                " ``match-string`` or neither",
            )
        if "match-pattern" in link_path_config:
            link_path_config["match-re"] = re.compile(link_path_config["match-pattern"])

        # Load, instantiate, and configure the plugin
        link_path_plugin_class = link_path_entrypoints[link_path_plugin_name].load()
        # Override global defaults for this plugin with values from this specific
        # instance
        link_path_config = dict(
            link_path_defaults.get(link_path_plugin_name, {}),
            **link_path_config,
        )
        link_path_plugin = link_path_plugin_class(parent, link_path_config)
        link_path_plugin.load_config()
        yield link_path_plugin


class LinkPathPlugin:
    """
    A plugin for linking feed item enclosures/content into media libraries.
    """

    def __init__(self, parent, config):
        """
        Instantiate a plugin for linking enclosures/content into media libraries.
        """
        self.parent = parent
        self.config = config

    def load_config(self):  # pragma: no cover
        """
        Pre-process and validate the plugin config prior to linking each enclosure.
        """
        raise NotImplementedError(
            "Link path plugin subclasses must implement the `load_config` method"
        )

    def __call__(self, *args, **kwargs):  # pragma: no cover
        """
        Determine the paths that should be linked to the feed item enclosure/content.

        Plugin implementations may return a list of paths and let the `ArchiveFeed`
        instance handle the actual linking including appending an numerical index to the
        end of the stem when the link target already exists.  Alternatively, the plugin
        may handle the linking itself and return None.
        """
        raise NotImplementedError(
            "Link path plugin subclasses must implement the `__call__` method"
        )
