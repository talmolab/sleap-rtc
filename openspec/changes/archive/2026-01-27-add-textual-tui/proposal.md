## Why

The current `browse` and `resolve-paths` commands rely on a localhost HTTP server that opens a browser UI. This creates friction for SSH workflows (can't access localhost from remote), adds browser dependency, and breaks unified terminal experience. A TUI replaces the browser with native terminal rendering.

## What Changes

- Add new `sleap-rtc tui` command using Textual framework
- Replace `FSViewerServer` (localhost HTTP/WebSocket bridge) with direct Textual rendering
- Reuse existing `BrowseClient` WebRTC connection logic unchanged
- Miller columns layout for file browsing (matches current web UI)
- Inline SLP video status panel for path resolution
- Worker tabs for multi-worker rooms
- **JWT-based room picker**: If logged in, fetch rooms via API and show interactive selector (no `--room --token` flags needed)
- **Login flow**: If not logged in, display login URL and poll for JWT (same flow as `sleap-rtc login`)
- Foundation for future GUI (Textual concepts port well to desktop frameworks)

## Impact

- Affected specs: `filesystem-browser`, `path-resolution`
- New spec: `tui` (new capability)
- Affected code:
  - New: `sleap_rtc/tui/` module
  - Modified: `sleap_rtc/cli.py` (add `tui` command)
  - Reused: `sleap_rtc/client/rtc_browse.py` (WebRTC logic)
  - Deprecated: `sleap_rtc/client/fs_viewer_server.py` (HTTP bridge - kept for backward compat)
