"""
Plugins for linking feed item enclosures into media libraries.
"""

import re
import pprint

try:
    from importlib.metadata import entry_points  # type: ignore
except ImportError:  # pragma: no cover
    from importlib_metadata import entry_points  # type: ignore


def load_plugins(parent, parent_config):
    """
    Pre-process and validate the enclosure plugin configurations.
    """
    archive = getattr(parent, "archive", parent)
    defaults = archive.global_config.get("plugins", {}).get("enclosures", {})
    configs = parent_config.get("enclosures", [])
    if not isinstance(configs, list):  # pragma: no cover
        raise ValueError(
            f"`enclosures` must be a list/array:\n{pprint.pformat(configs)}"
        )
    entrypoints = {ep.name: ep for ep in entry_points()["feedarchiver.enclosures"]}
    plugins = []
    fallack_plugins = []
    for config in configs:
        # Perform any validation as early as possible
        name = config.get("plugin", "default")
        if name not in entrypoints:  # pragma: no cover
            raise ValueError(
                f"enclosure plugin name not registered: {name}",
            )
        if ("match-pattern" in config and "match-string" not in config) or (
            "match-string" in config and "match-pattern" not in config
        ):  # pragma: no cover
            raise ValueError(
                "enclosure plugin config must define either both ``match-pattern`` and"
                " ``match-string`` or neither",
            )
        if "match-pattern" in config:
            config["match-re"] = re.compile(config["match-pattern"])

        # Load, instantiate, and configure the plugin
        plugin_class = entrypoints[name].load()
        # Override global defaults for this plugin with values from this specific
        # instance
        config = dict(
            defaults.get(name, {}),
            **config,
        )
        plugin = plugin_class(parent, config)
        plugin.load_config()

        if plugin.config.get("fallback", False):
            fallack_plugins.append(plugin)
        else:
            plugins.append(plugin)

    return plugins, fallack_plugins


class EnclosurePlugin:
    """
    A plugin for linking feed item enclosures into media libraries.
    """

    def __init__(self, parent, config):
        """
        Instantiate a plugin for linking enclosures into media libraries.
        """
        self.parent = parent
        self.config = config

    def load_config(self):  # pragma: no cover
        """
        Pre-process and validate the plugin config prior to linking each enclosure.
        """
        raise NotImplementedError(
            "Enclosure plugin subclasses must implement the `load_config` method"
        )

    def __call__(self, *args, **kwargs):  # pragma: no cover
        """
        Determine the paths that should be linked to the feed item enclosure.

        Plugin implementations may return a list of paths and let the `ArchiveFeed`
        instance handle the actual linking including appending an numerical index to the
        end of the stem when the link target already exists.  Alternatively, the plugin
        may handle the linking itself and return None.
        """
        raise NotImplementedError(
            "Enclosure plugin subclasses must implement the `__call__` method"
        )
