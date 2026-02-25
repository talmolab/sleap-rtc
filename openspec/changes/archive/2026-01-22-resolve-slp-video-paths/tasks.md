# Tasks: Resolve SLP Video Paths

## 1. Protocol Messages

### 1.1 Add Message Constants
- [x] 1.1.1 Add `MSG_FS_CHECK_VIDEOS` constant to `protocol.py`
- [x] 1.1.2 Add `MSG_FS_CHECK_VIDEOS_RESPONSE` constant to `protocol.py`
- [x] 1.1.3 Add `MSG_FS_SCAN_DIR` constant to `protocol.py`
- [x] 1.1.4 Add `MSG_FS_SCAN_DIR_RESPONSE` constant to `protocol.py`
- [x] 1.1.5 Add `MSG_FS_WRITE_SLP` constant to `protocol.py`
- [x] 1.1.6 Add `MSG_FS_WRITE_SLP_OK` constant to `protocol.py`
- [x] 1.1.7 Add `MSG_FS_WRITE_SLP_ERROR` constant to `protocol.py`
- [x] 1.1.8 Document message formats in protocol.py docstring

## 2. Worker-Side: Video Accessibility Check

### 2.1 FileManager Extensions
- [x] 2.1.1 Add `check_video_accessibility(slp_path: str) -> dict` method to `FileManager`
- [x] 2.1.2 Use `sio.load_file(slp_path, open_videos=False)` to load SLP
- [x] 2.1.3 Check if each `video.filename` exists on filesystem (skip embedded)
- [x] 2.1.4 Return dict with `slp_path`, `total_videos`, `missing` list, `accessible` count

### 2.2 Auto-Check Integration
- [x] 2.2.1 Add video check after `WORKER_PATH_OK` in `worker_class.py`
- [x] 2.2.2 If SLP file, call `file_manager.check_video_accessibility()`
- [x] 2.2.3 If missing videos, send `FS_CHECK_VIDEOS_RESPONSE` to Client

### 2.3 Tests
- [x] 2.3.1 Test `check_video_accessibility()` with all videos accessible
- [x] 2.3.2 Test `check_video_accessibility()` with some videos missing
- [x] 2.3.3 Test embedded videos are excluded from check

## 3. Worker-Side: Directory Scanning

### 3.1 FileManager Extensions
- [x] 3.1.1 Add `scan_directory_for_filenames(directory: str, filenames: list[str]) -> dict` method
- [x] 3.1.2 Validate directory is within allowed mounts
- [x] 3.1.3 Check for each filename in the directory
- [x] 3.1.4 Return dict mapping filename → full path (or None if not found)

### 3.2 Message Handler
- [x] 3.2.1 Add `FS_SCAN_DIR` case to `handle_fs_message()` in `worker_class.py`
- [x] 3.2.2 Parse JSON payload (directory, filenames)
- [x] 3.2.3 Call `file_manager.scan_directory_for_filenames()`
- [x] 3.2.4 Return `FS_SCAN_DIR_RESPONSE` with results

### 3.3 Tests
- [x] 3.3.1 Test directory scanning with all filenames found
- [x] 3.3.2 Test directory scanning with partial matches
- [x] 3.3.3 Test directory scanning with no matches
- [x] 3.3.4 Test security: reject directory outside allowed mounts

## 4. Worker-Side: SLP Writing

### 4.1 FileManager Extensions
- [x] 4.1.1 Add `write_slp_with_new_paths(slp_path: str, output_dir: str, filename_map: dict) -> str` method
- [x] 4.1.2 Load SLP with `sio.load_file(slp_path, open_videos=False)`
- [x] 4.1.3 Apply `labels.replace_filenames(filename_map=...)`
- [x] 4.1.4 Generate output filename: `resolved_YYYYMMDD_<original>.slp`
- [x] 4.1.5 Save with `labels.save(output_path)`
- [x] 4.1.6 Return output path

### 4.2 Message Handler
- [x] 4.2.1 Add `FS_WRITE_SLP` case to `handle_fs_message()` in `worker_class.py`
- [x] 4.2.2 Parse JSON payload (slp_path, output_dir, filename_map)
- [x] 4.2.3 Validate output_dir is within allowed mounts
- [x] 4.2.4 Call `file_manager.write_slp_with_new_paths()`
- [x] 4.2.5 Return `FS_WRITE_SLP_OK` or `FS_WRITE_SLP_ERROR`

### 4.3 Tests
- [x] 4.3.1 Test SLP writing with valid filename_map
- [x] 4.3.2 Test output path security validation
- [x] 4.3.3 Test error handling for invalid SLP path
- [x] 4.3.4 Test metadata preservation after rewrite

## 5. Client-Side: Auto-Launch Resolution UI

### 5.1 Handle FS_CHECK_VIDEOS_RESPONSE
- [x] 5.1.1 Add handler for `FS_CHECK_VIDEOS_RESPONSE` in Client
- [x] 5.1.2 If missing videos list is non-empty, launch resolution UI
- [x] 5.1.3 Pass missing videos data to resolution UI via URL params or WebSocket

### 5.2 FSViewerServer Extensions
- [x] 5.2.1 Add `/resolve` route to `FSViewerServer`
- [x] 5.2.2 Serve `fs_resolve.html` for `/resolve` requests
- [x] 5.2.3 Add WebSocket handlers for `scan_dir` and `write_slp` messages
- [x] 5.2.4 Relay messages to Worker and responses back to browser

## 6. Resolution Web UI

### 6.1 HTML Structure
- [x] 6.1.1 Create `sleap_rtc/client/static/fs_resolve.html`
- [x] 6.1.2 Add header with connection status (reuse from fs_viewer.html)
- [x] 6.1.3 Add left panel: missing videos list with status icons
- [x] 6.1.4 Add right panel: embed filesystem browser component
- [x] 6.1.5 Add bottom action bar: Save button, Cancel button

### 6.2 JavaScript: Video List
- [x] 6.2.1 Parse missing videos from URL params or WebSocket message
- [x] 6.2.2 Render video list with filename, original path, status
- [x] 6.2.3 Update status icons when videos are resolved (❌ → ✅)
- [x] 6.2.4 Track filename_map: {original_path → resolved_path}

### 6.3 JavaScript: Directory Scanning
- [x] 6.3.1 When user selects a file, extract directory path
- [x] 6.3.2 Get list of remaining missing filenames
- [x] 6.3.3 Send `scan_dir` WebSocket message with directory and filenames
- [x] 6.3.4 Handle `scan_dir_response`: update resolved paths for found files
- [x] 6.3.5 Update UI to show auto-resolved videos

### 6.4 JavaScript: Save
- [x] 6.4.1 Implement Save button click handler
- [x] 6.4.2 If unresolved videos remain, show confirmation dialog
- [x] 6.4.3 Prompt user to select output directory (use filesystem browser)
- [x] 6.4.4 Send `write_slp` WebSocket message with filename_map
- [x] 6.4.5 Handle response: show success message with output path
- [x] 6.4.6 On success, notify parent (for training flow integration)

### 6.5 Styling
- [x] 6.5.1 Style split panel layout (left: video list, right: browser)
- [x] 6.5.2 Style video list items with status icons
- [x] 6.5.3 Match dark theme from fs_viewer.html

## 7. CLI Integration

### 7.1 Standalone Command
- [x] 7.1.1 Add `resolve-paths` command to `cli.py`
- [x] 7.1.2 Add options: `--room`, `--token`, `--slp`, `--port`, `--no-browser`
- [x] 7.1.3 Connect to Worker (similar to `browse` command)
- [x] 7.1.4 Send SLP path to Worker for video check
- [x] 7.1.5 If missing videos, launch resolution UI
- [x] 7.1.6 If all accessible, print success message

### 7.2 Training Flow Integration
- [x] 7.2.1 After `WORKER_PATH_OK`, wait for potential `FS_CHECK_VIDEOS_RESPONSE`
- [x] 7.2.2 If missing videos, launch resolution UI and wait for completion
- [x] 7.2.3 After resolution, use corrected SLP path for training

## 8. Testing

### 8.1 Integration Tests
- [ ] 8.1.1 Test end-to-end: SLP with missing videos → resolution → save
- [ ] 8.1.2 Test auto-detection triggers resolution UI
- [ ] 8.1.3 Test directory scanning auto-resolves multiple videos
- [ ] 8.1.4 Test training proceeds after resolution

### 8.2 UI Tests (Manual)
- [ ] 8.2.1 Verify video list displays correctly
- [ ] 8.2.2 Verify filesystem browser integration works
- [ ] 8.2.3 Verify directory scanning updates UI
- [ ] 8.2.4 Verify save produces correct SLP file

## Dependencies

- **Blocks on**: `add-web-file-selector` filesystem browser must be functional
- **Parallel**: Tasks 2.x, 3.x, 4.x (Worker-side) can run in parallel
- **Sequential**: Task 6.x (Web UI) requires 5.x (Client-side) infrastructure
