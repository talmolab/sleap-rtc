# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.2] - 2026-02-27

### Fixed

- **`ModuleNotFoundError: No module named 'sleap_rtc.worker'`** — `sleap_rtc/`, `sleap_rtc/worker/`, and `sleap_rtc/client/` were missing `__init__.py` files, so hatchling excluded those sub-packages from the wheel. Installing via `uvx sleap-rtc` or `pip install sleap-rtc` would fail at import time. ([#55](https://github.com/talmolab/sleap-rtc/pull/55))
- **Explicit build backend** — Added `[build-system]` table declaring `hatchling` so the build backend is never left implicit. ([#55](https://github.com/talmolab/sleap-rtc/pull/55))
- **Wheel bloat** — Excluded Dockerfiles, static HTML assets, devcontainer configs, and nested `pyproject.toml` files from the distribution. ([#55](https://github.com/talmolab/sleap-rtc/pull/55))

### Added

- **Package smoke test** — CI now installs the built wheel and imports each top-level package to catch missing sub-packages before release. ([#55](https://github.com/talmolab/sleap-rtc/pull/55))
- **Windows test matrix** — CI runs the full test suite on `windows-latest` in addition to `ubuntu-latest` and `macos-latest`. Cross-platform fixes include `posixpath` for remote Linux filesystem navigation, `os.replace()` for atomic credential writes, and `.as_posix()` for Linux worker command paths. ([#55](https://github.com/talmolab/sleap-rtc/pull/55))

## [0.0.1] - 2026-02-26

Initial release.
