## Why

The CLI currently has inconsistent authentication patterns, scattered command structure, and mixed UI libraries. This proposal consolidates authentication flows, standardizes command naming, and establishes a clear UI strategy to improve developer experience.

## What Changes

### Authentication & Credentials
- **BREAKING**: Deprecate room token authentication (JWT + room-secret only)
- Add room-secret persistence to credentials store alongside JWT
- Consolidate all auth flows to use JWT for API access, room-secret for P2P PSK

### Command Structure
- **BREAKING**: Rename `client-train` → `train`, `client-track` → `track`
- Move `--browse` and `--resolve-paths` functionality to `test` subcommand (experimental)
- Add `sleap-rtc tui` command to expose Textual TUI for file browsing
- Add `sleap-rtc status` command for connection/auth status overview
- Add `sleap-rtc doctor` command for environment diagnostics

### Flag Standardization
- **BREAKING**: Standardize on `-f/--force` (not `-y/--yes`) for destructive confirmation bypass
- Convert all multi-word flags to kebab-case (e.g., `--room-secret`)
- Add short flags for frequently-used options

### UI Strategy
- Use rich-click for styled CLI help and output
- Use prompt_toolkit for interactive selections (worker, room)
- Use Textual TUI for complex file browsing workflows

## Impact

- Affected specs: `specs/cli/spec.md`
- Affected code:
  - `sleap_rtc/client/cli.py` - main CLI entry point
  - `sleap_rtc/client/file_selector.py` - worker/room selectors
  - `sleap_rtc/client/credentials.py` - credential storage
  - `sleap_rtc/tui/` - Textual TUI module
