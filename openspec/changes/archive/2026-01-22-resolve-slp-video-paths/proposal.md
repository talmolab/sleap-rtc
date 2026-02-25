# Proposal: Resolve SLP Video Paths

## Why

SLEAP label files (`.slp`) store absolute paths to video files (e.g., `/Users/amickl/Google Drive/project/video.mp4`). When these files are used on a remote Worker, the paths are invalid because the Worker has the same shared storage mounted at a different path (e.g., `/mnt/gdrive/project/video.mp4`). This is a path translation problem, not a data transfer problem.

The `pkg.slp` format embeds video frames directly, avoiding path issues, but doesn't scale - multi-hour video experiments produce files too large to transfer practically. Users need a way to resolve broken video paths when using standard `.slp` files with remote Workers.

## What Changes

### Automatic Video Accessibility Check
- After Worker resolves/receives SLP file path, Worker checks if each video path is accessible
- If any videos are inaccessible, Worker reports missing video filenames to Client
- Client automatically launches resolution UI (no flag needed)

### Web UI Changes
- Add `/resolve` route to `FSViewerServer` for dedicated video path resolution view
- Create `fs_resolve.html` with:
  - Missing videos panel showing unresolved filenames and original paths
  - Integration with existing filesystem browser for video selection
  - When user selects a video file, system scans that directory for other missing filenames (SLP Viewer style)
  - Save button to write corrected SLP to Worker filesystem

### Worker-Side Changes
- Add `FS_CHECK_VIDEOS` message type to check video path accessibility
- Add `FS_SCAN_DIR` message type to scan a directory for specific filenames
- Add `FS_WRITE_SLP` message type for writing corrected SLP files
- Implement SLP rewriting using `sleap-io` Python API:
  - Load labels with `sio.load_file()`
  - Update video paths with `Labels.replace_filenames(filename_map={...})`
  - Save with timestamped filename: `resolved_YYYYMMDD_<original>.slp`

### CLI Integration
- Add standalone `sleap-rtc resolve-paths` command for pre-flight path resolution

### New Dependencies
- `sleap-io` (already a transitive dependency via sleap-nn)

## Impact

- **New capability**: `slp-video-resolution` - Resolving video paths in SLP files
- **Extends**: `filesystem-browser` from `add-web-file-selector` - Reuses remote file browser UI
- **Affected code**:
  - `sleap_rtc/client/fs_viewer_server.py` - Add /resolve route
  - **NEW** `sleap_rtc/client/static/fs_resolve.html` - Resolution web UI
  - `sleap_rtc/worker/file_manager.py` - Add video check, directory scan, SLP write capabilities
  - `sleap_rtc/worker/worker_class.py` - Auto-check videos after SLP path resolution
  - `sleap_rtc/protocol.py` - Add FS_CHECK_VIDEOS, FS_SCAN_DIR, FS_WRITE_SLP messages
  - `sleap_rtc/cli.py` - Add resolve-paths command

## Related Changes

- Depends on `add-web-file-selector` (100/126 tasks complete) - Provides filesystem browser foundation
- Does not conflict with `add-path-resolution` - That handles client→worker path translation for training data; this handles video references within SLP files
