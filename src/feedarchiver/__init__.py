"""
Archive RSS/Atom syndication feeds and their enclosures and assets.
"""

import pathlib
import logging
import argparse
import pprint

from . import utils
from . import archive

logger = logging.getLogger(__name__)

# Manage version through the VCS CI/CD process
__version__ = None
try:
    from . import version
except ImportError:  # pragma: no cover
    pass
else:  # pragma: no cover
    __version__ = version.version

# Define command line options and arguments
parser = argparse.ArgumentParser(
    description=__doc__.strip(),
    formatter_class=argparse.ArgumentDefaultsHelpFormatter,
)
parser.add_argument(
    "--archive-dir",
    "-a",
    help=(
        "the archive root directory into which all feeds, their enclosures and assets "
        "will be downloaded"
    ),
    nargs="?",
    type=pathlib.Path,
    default=pathlib.Path(),
)
# Define CLI sub-commands
subparsers = parser.add_subparsers(
    dest="command",
    required=True,
    help="sub-command",
)


def update(
    archive_dir=parser.get_default("--archive-dir"),
    recreate=parser.get_default("--recreate"),
):  # pragma: no cover, pylint: disable=missing-function-docstring
    feed_archive = archive.Archive(archive_dir, recreate)
    return feed_archive.update()


update.__doc__ = archive.Archive.update.__doc__
parser_update = subparsers.add_parser(
    "update",
    help=update.__doc__.strip(),
    description=update.__doc__.strip(),
)
# Make the function for the sub-command specified in the CLI argument available in the
# argument parser for delegation below.
parser_update.set_defaults(command=update)
parser_update.add_argument(
    "--recreate",
    "-r",
    help="ignore existing feed XML in the archive and rewrite it",
    action=argparse.BooleanOptionalAction,
)


def migrate(
    archive_dir=parser.get_default("--archive-dir"),
    target_dir=parser.get_default("target_dir"),
):  # pragma: no cover, pylint: disable=missing-function-docstring
    feed_archive = archive.Archive(archive_dir)
    return feed_archive.migrate(target_dir)


migrate.__doc__ = archive.Archive.migrate.__doc__
parser_migrate = subparsers.add_parser(
    "migrate",
    help=migrate.__doc__.strip(),
    description=migrate.__doc__.strip(),
)
# Make the function for the sub-command specified in the CLI argument available in the
# argument parser for delegation below.
parser_migrate.set_defaults(command=migrate)
parser_migrate.add_argument(
    "target_dir",
    help=(
        "the target root directory into which all feeds, their enclosures and assets "
        "will be migrated"
    ),
    type=pathlib.Path,
)


def config_cli_logging(
    root_level=logging.INFO, **kwargs
):  # pragma: no cover, pylint: disable=unused-argument
    """
    Configure logging CLI usage first, but also appropriate for writing to log files.
    """
    # Want just our logger's level, not others', to be controlled by options/environment
    logging.basicConfig(level=root_level)
    level = logging.INFO
    if utils.DEBUG:  # pragma: no cover
        level = logging.DEBUG
    logger.setLevel(level)
    # Finer control of external loggers to reduce logger noise or expose information
    # that may be useful to users.
    logging.getLogger("charset_normalizer").setLevel(logging.WARNING)
    return level


def main(args=None):  # pragma: no cover, pylint: disable=missing-function-docstring
    # Parse CLI options and positional arguments
    parsed_args = parser.parse_args(args=args)
    # Avoid noisy boilerplate, functions meant to handle CLI usage should accept kwargs
    # that match the defined option and argument names.
    cli_kwargs = dict(vars(parsed_args))
    # Remove any meta options and arguments, those used to direct option and argument
    # handling, that shouldn't be passed onto functions meant to handle CLI usage.  More
    # generally, err on the side of options and arguments being kwargs, remove the
    # exceptions.
    del cli_kwargs["command"]

    # Configure logging for CLI usage
    config_cli_logging(**cli_kwargs)

    # Delegate to the function for the sub-command CLI argument
    logger.debug("Running %r sub-command", parsed_args.command.__name__)
    # Sub-commands may return a result to be pretty printed, or handle output themselves
    # and return nothing.
    result = parsed_args.command(**cli_kwargs)
    if result is not None:
        pprint.pprint(result)


main.__doc__ = __doc__
