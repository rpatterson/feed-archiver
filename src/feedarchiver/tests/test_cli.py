# SPDX-FileCopyrightText: 2023 Ross Patterson <me@rpatterson.net>
#
# SPDX-License-Identifier: MIT

"""
Test the feed-archiver Command-Line Interface.
"""

import sys
import os
import io
import runpy
import subprocess  # nosec B404
import contextlib
import pathlib


import feedarchiver

from .. import tests


class FeedarchiverCLITests(tests.FeedarchiverTestCase):
    """
    Test the feed-archiver Command-Line Interface.
    """

    def test_importable(self):
        """
        The Python package is on `sys.path` and thus importable.
        """
        import_process = subprocess.run(  # nosec B603
            [sys.executable, "-c", "import feedarchiver"],
            check=False,
        )
        self.assertEqual(
            import_process.returncode,
            0,
            "The Python package not importable",
        )

    def get_cli_error_messages(self, args):
        """
        Run the CLI script and return any error messages.
        """
        stderr_file = io.StringIO()
        with self.assertRaises(SystemExit, msg="CLI didn't exit"):
            with contextlib.redirect_stderr(stderr_file):
                feedarchiver.main(args=args)
        return stderr_file.getvalue()

    def test_cli_help(self):
        """
        The command line script is self-docummenting.
        """
        stdout_file = io.StringIO()
        with self.assertRaises(SystemExit, msg="CLI didn't exit"):
            with contextlib.redirect_stdout(stdout_file):
                feedarchiver.main(args=["--help"])
        stdout = stdout_file.getvalue()
        self.assertIn(
            feedarchiver.__doc__.strip(),
            stdout.replace("\n", " "),
            "The console script name missing from --help output",
        )

    def test_cli_subcommand(self):
        """
        The command line supports sub-commands.
        """
        cwd = pathlib.Path.cwd()
        os.chdir(self.archive.root_path)
        try:
            self.assertIsNone(
                feedarchiver.main(args=["update"]),
                "Wrong console script sub-command return value",
            )
        finally:
            os.chdir(cwd)

    def test_cli_option_errors(self):
        """
        The command line script displays useful messages for invalid option values.
        """
        stderr = self.get_cli_error_messages(args=["update", "--non-existent-option"])
        self.assertIn(
            "error: unrecognized arguments: --non-existent-option",
            stderr,
            "Wrong invalid option message",
        )

    def test_cli_dash_m_option(self):
        """
        The package supports execution via Python's `-m` CLI option.
        """
        module_main_process = subprocess.run(  # nosec B603
            [sys.executable, "-m", "feedarchiver", "update"],
            check=False,
            cwd=self.archive.root_path,
        )
        self.assertEqual(
            module_main_process.returncode,
            0,
            "Running via Python's `-m` option exited with non-zero status code",
        )

    def test_cli_module_main(self):
        """
        The package supports execution via Python's `-m` option.
        """
        with self.assertRaises(SystemExit, msg="CLI didn't exit") as exc_context:
            runpy.run_module("feedarchiver")
        self.assertEqual(
            exc_context.exception.code,
            2,
            "Wrong `runpy` exit status code",
        )

    def test_cli_exit_code(self):
        """
        The command line script exits with status code zero if there are no exceptions.
        """
        # Find the location of the `console_scripts` for this test environment
        prefix_path = pathlib.Path(sys.argv[0]).parent
        while not (prefix_path / "bin").is_dir():
            prefix_path = prefix_path.parent
            if prefix_path.parent is list(prefix_path.parents)[-1]:  # pragma: no cover
                raise ValueError(f"Could not find script prefix path: {sys.argv[0]}")

        script_process = subprocess.run(  # nosec B603
            [prefix_path / "bin" / "feed-archiver", "update"],
            check=False,
            cwd=self.archive.root_path,
        )
        self.assertEqual(
            script_process.returncode,
            0,
            "Running the console script exited with non-zero status code",
        )
