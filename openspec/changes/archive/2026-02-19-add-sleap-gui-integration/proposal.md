## Why

SLEAP users currently must use the CLI to run remote training/inference via sleap-rtc. Integrating sleap-rtc directly into the SLEAP GUI Training Configuration dialog would provide a seamless user experience, allowing researchers to leverage remote GPU workers without leaving the familiar GUI workflow.

## What Changes

- Add a new "Remote Training (Experimental)" section to SLEAP's Training Configuration dialog
- Create a high-level Python API (`sleap_rtc.api`) for GUI integration
- Implement Qt widgets for remote training configuration
- Create progress forwarding to reuse SLEAP's existing LossViewer
- Feature-gate the UI behind an "experimental features" preference

## Impact

- **Affected specs**: Creates two new capabilities:
  - `gui-integration`: Qt widgets and SLEAP dialog integration
  - `gui-python-api`: High-level Python API for programmatic access
- **Affected code (sleap-rtc)**:
  - New module: `sleap_rtc/api.py`
  - New module: `sleap_rtc/gui/__init__.py`
  - New module: `sleap_rtc/gui/widgets.py`
  - New module: `sleap_rtc/gui/runners.py`
- **Affected code (SLEAP)** - modifications needed in separate PRs:
  - `sleap/prefs.py` - add experimental features preference
  - `sleap/gui/app.py` - add menu toggle
  - `sleap/gui/learning/main_tab.py` - conditionally show RemoteTrainingWidget
  - `sleap/gui/learning/runners.py` - add remote training execution path

## Dependencies

- SLEAP v1.6.1+ (verified against this version)
- sleap-nn v0.1.0+ (uses ProgressReporterZMQ callback)
- PySide6 (Qt bindings, already a SLEAP dependency)
- Optional: sleap-rtc installed in SLEAP environment

## Notes

- The GUI integration should gracefully degrade when sleap-rtc is not installed
- Uses same ZMQ message format as sleap-nn for LossViewer compatibility
- See `scratch/2026-02-11-sleap-gui-rtc-integration/README.md` for full investigation
