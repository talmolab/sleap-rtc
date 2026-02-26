# Proposal: Add Shared Filesystem Save and Path Mapping Persistence

## Summary

Two related quality-of-life improvements for users who work with plain `.slp`
files on machines that have a shared filesystem mounted:

1. **Save to shared filesystem** — When the SLP Path Resolution dialog appears
   (because the worker cannot find the local `.slp`), offer "Save as .slp / .pkg.slp
   to folder..." buttons so the user can write the file to a shared mount first,
   then point the worker at it using the existing "Browse worker filesystem" button.

2. **Directory prefix path mapping persistence** — After the user successfully
   resolves a path (either in `SlpPathDialog` or `PathResolutionDialog`), prompt
   them to save the local→worker directory mapping to `~/.sleap-rtc/config.toml`.
   On subsequent runs the worker path field is pre-filled automatically using any
   saved mapping whose local prefix matches.

## Motivation

Currently a user with a new `.slp` project on their laptop must either:
- Know the exact worker-side path and type it manually, or
- Upload the file as `.pkg.slp` (which can be slow for large videos).

Users with a shared filesystem (NFS, VAST, etc.) have a faster third option —
copy the file there — but the dialog provides no guidance or tooling for it.

The path mapping feature removes the need to look up worker paths on every
submission once the user has resolved the mapping at least once.

## Scope

- `sleap_rtc/config.py` — `PathMapping` dataclass; `get_path_mappings()`,
  `save_path_mapping()`, `remove_path_mapping()` methods on `Config`
- `sleap_rtc/gui/widgets.py` — `SlpPathDialog`: new top section with save
  buttons; auto-fill worker path on init from saved mappings; save-mapping
  prompt on Continue
- `sleap_rtc/gui/presubmission.py` — thread `save_fn` through
  `run_presubmission_checks` → `check_video_paths`; save-mapping prompt after
  `PathResolutionDialog` resolves video paths
- `sleap_rtc/cli.py` — `sleap-rtc config add-path-mapping` and
  `sleap-rtc config remove-path-mapping` subcommands
- SLEAP GUI integration (`dialog.py`) — wire `save_fn=_save_fn`

## Out of Scope

- Automatic bidirectional sync or upload to shared mounts
- Google Drive / cloud storage mounts (separate effort)
- Path mapping UI in the dashboard
