"""Smoke tests for the sleap-rtc package.

These tests verify that the installed package is structurally sound — all
subpackages importable, the CLI entry point reachable, and required data
files present. They are intentionally lightweight and fast (<5 s total).

Modeled after the CLI smoke test pattern used in SLEAP and sleap-nn
(tests/test_cli.py in each repo), using Click's CliRunner for in-process
invocation and plain imports for module-level checks.

The primary failure mode these tests guard against is a packaging bug
where subpackages or data files are missing from the published wheel
(as happened in v0.0.1, where sleap_rtc.worker was not included).
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from sleap_rtc.cli import cli


# ── Subpackage imports ────────────────────────────────────────────────────────


class TestSubpackageImports:
    """Each sleap_rtc subpackage must be importable without error.

    If any of these fail, the wheel is missing __init__.py files or the
    package was not correctly included in the distribution.
    """

    def test_import_worker(self):
        """sleap_rtc.worker must be importable."""
        import sleap_rtc.worker  # noqa: F401

    def test_import_worker_class(self):
        """RTCWorkerClient must be importable from sleap_rtc.worker."""
        from sleap_rtc.worker.worker_class import RTCWorkerClient  # noqa: F401

    def test_import_client(self):
        """sleap_rtc.client must be importable."""
        import sleap_rtc.client  # noqa: F401

    def test_import_client_class(self):
        """RTCClient must be importable from sleap_rtc.client."""
        from sleap_rtc.client.client_class import RTCClient  # noqa: F401

    def test_import_auth(self):
        """sleap_rtc.auth must be importable."""
        import sleap_rtc.auth  # noqa: F401

    def test_import_jobs(self):
        """sleap_rtc.jobs must be importable."""
        import sleap_rtc.jobs  # noqa: F401

    def test_import_gui(self):
        """sleap_rtc.gui must be importable."""
        import sleap_rtc.gui  # noqa: F401

    def test_import_tui(self):
        """sleap_rtc.tui must be importable."""
        import sleap_rtc.tui  # noqa: F401


# ── CLI entry point ───────────────────────────────────────────────────────────


class TestCLIEntryPoint:
    """The CLI entry point must be reachable and respond to --help."""

    def test_main_help(self):
        """sleap-rtc --help must exit 0 and list core commands."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "worker" in result.output
        assert "train" in result.output
        assert "track" in result.output
        assert "login" in result.output

    def test_worker_help(self):
        """sleap-rtc worker --help must exit 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["worker", "--help"])
        assert result.exit_code == 0

    def test_train_help(self):
        """sleap-rtc train --help must exit 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["train", "--help"])
        assert result.exit_code == 0

    def test_track_help(self):
        """sleap-rtc track --help must exit 0."""
        runner = CliRunner()
        result = runner.invoke(cli, ["track", "--help"])
        assert result.exit_code == 0


# ── Required data files ───────────────────────────────────────────────────────


class TestRequiredDataFiles:
    """Non-Python files that must be present in the installed package.

    The filesystem viewer server (fs_viewer_server.py) serves these HTML
    files at runtime using Path(__file__).parent / "static" / "...".
    If they are missing from the wheel the server returns HTTP 500.
    """

    def test_fs_viewer_html_present(self):
        """fs_viewer.html must be bundled with the package."""
        import sleap_rtc.client.fs_viewer_server as mod

        html_path = Path(mod.__file__).parent / "static" / "fs_viewer.html"
        assert html_path.exists(), (
            f"fs_viewer.html missing from installed package at {html_path}. "
            "Check the hatchling exclude config in pyproject.toml."
        )

    def test_fs_resolve_html_present(self):
        """fs_resolve.html must be bundled with the package."""
        import sleap_rtc.client.fs_viewer_server as mod

        html_path = Path(mod.__file__).parent / "static" / "fs_resolve.html"
        assert html_path.exists(), (
            f"fs_resolve.html missing from installed package at {html_path}. "
            "Check the hatchling exclude config in pyproject.toml."
        )
