# Proposal: Add Hybrid Path Resolution System

## Why

Currently, users must manually place files in the worker's exact `input_path` directory and know the exact filename. This creates friction for users who have data scattered across different locations on their machines. Users expect to provide a path to their `.slp` file (as they do with other SLEAP-adjacent packages) and have the system figure out where that file exists on the worker's filesystem.

This proposal introduces automatic path resolution that translates client paths to worker paths using mount alias configuration, with fallback to file search and browser-based selection when automatic resolution fails.

## What Changes

### Configuration Changes
- **BREAKING**: Remove single `input_path`/`output_path` restriction from `[worker.io]`
- Add `allowed_roots` list for worker filesystem browsing security
- Add `[[worker.io.mounts]]` array for mount alias configuration (client-to-worker path translation)

### Worker Changes
- Extend `FileManager` class with filesystem browsing capabilities:
  - `get_allowed_roots()` - Return browsable directories
  - `list_directory()` - List directory contents with depth control
  - `search_file()` - Search for files by name across allowed roots
  - `resolve_path()` - Translate client paths using mount aliases
- Add new message types to `protocol.py`: `MSG_FS_*` for filesystem operations
- Route filesystem messages in worker data channel handler

### Client Changes
- Create `path_resolver.py` for orchestrating path resolution
- Add browser-based file browser (`browser_bridge.py`) using aiohttp
- Insert path resolution before file transfer in `on_channel_open()`
- Add CLI options: `--worker-path` (escape hatch), keep `--pkg_path` for backward compatibility

### New Dependencies
- `aiohttp` for browser bridge HTTP server

## Impact

- **Affected specs**: `worker-io` (modify), `path-resolution` (new), `filesystem-browser` (new)
- **Affected code**:
  - `sleap_rtc/config.py` - Add mount alias config classes
  - `sleap_rtc/protocol.py` - Add MSG_FS_* constants
  - `sleap_rtc/worker/file_manager.py` - Add filesystem operations
  - `sleap_rtc/worker/worker_class.py` - Route fs_* messages
  - `sleap_rtc/client/client_class.py` - Integrate path resolution
  - **NEW** `sleap_rtc/client/path_resolver.py` - Path resolution orchestration
  - **NEW** `sleap_rtc/client/browser_bridge.py` - Browser UI server
  - **NEW** `sleap_rtc/client/static/browser_ui.html` - Browser UI

## Related Changes

- Builds on `simplify-worker-io-paths` (partially implemented)
- Does not conflict with other pending changes
