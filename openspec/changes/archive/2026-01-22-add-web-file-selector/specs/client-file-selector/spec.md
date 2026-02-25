# Client File Selector Capability

## ADDED Requirements

### Requirement: Interactive Arrow Selection UI
The system SHALL display fuzzy match results using an interactive arrow-key selection interface.

#### Scenario: Display candidates with arrow selection
- **WHEN** Client receives `FS_RESOLVE_RESPONSE` with candidates
- **THEN** Client SHALL display interactive selection UI
- **AND** UI SHALL show candidates as selectable list
- **AND** current selection SHALL be highlighted with `>` prefix
- **AND** each candidate SHALL show path and size

#### Scenario: Arrow key navigation
- **WHEN** selection UI is displayed
- **THEN** ↑ (up arrow) SHALL move selection to previous item
- **AND** ↓ (down arrow) SHALL move selection to next item
- **AND** selection SHALL wrap around at list boundaries

#### Scenario: Confirm selection
- **WHEN** user presses Enter on a candidate
- **THEN** Client SHALL use selected path for job submission
- **AND** UI SHALL close

#### Scenario: Cancel selection
- **WHEN** user presses Escape
- **THEN** Client SHALL abort file selection
- **AND** Client SHALL display options menu (browse, manual entry, cancel)

#### Scenario: Single match display
- **WHEN** fuzzy resolution returns single candidate
- **THEN** Client SHALL still display selection UI (no auto-select)
- **AND** UI SHALL show "Press Enter to confirm" hint

#### Scenario: No matches menu
- **WHEN** fuzzy resolution returns empty candidates
- **THEN** Client SHALL display options menu:
  - [B] Open filesystem browser (run `sleap-rtc browse`)
  - [P] Enter path manually
  - [W] Try wildcard search
  - [C] Cancel

#### Scenario: Terminal fallback
- **WHEN** terminal does not support arrow keys (dumb terminal)
- **THEN** Client SHALL display numbered list
- **AND** user SHALL enter number to select
- **AND** user MAY enter 'b' for browse or 'c' for cancel

---

### Requirement: Default Resolution Flow
The system SHALL attempt path resolution automatically when user provides a local path.

#### Scenario: Automatic resolution trigger
- **WHEN** user runs `client-train --pkg_path /local/path/file.slp`
- **THEN** Client SHALL extract filename from path
- **AND** Client SHALL get file size if local file exists
- **AND** Client SHALL send `FS_RESOLVE` to Worker after RTC connection

#### Scenario: Path found immediately
- **WHEN** Worker finds exact path in its mounts
- **THEN** Client SHALL proceed with job using that path
- **AND** Client SHALL NOT display selection UI

#### Scenario: Path not found triggers fuzzy search
- **WHEN** Worker does not find exact path
- **THEN** Worker SHALL perform fuzzy search automatically
- **AND** Client SHALL display arrow selection with results

#### Scenario: Local file exists
- **WHEN** local file at `--pkg_path` exists
- **THEN** Client SHALL include file size in `FS_RESOLVE` request
- **AND** Worker SHALL use size for ranking matches

#### Scenario: Local file does not exist
- **WHEN** local file at `--pkg_path` does not exist
- **THEN** Client SHALL extract filename only
- **AND** Client SHALL send `FS_RESOLVE` without size parameter
- **AND** resolution SHALL proceed with filename matching only

---

### Requirement: Browse Command
The system SHALL provide a separate CLI command for browsing Worker filesystem.

#### Scenario: Start browse command
- **WHEN** user runs `sleap-rtc browse --room <room_id>`
- **THEN** Client SHALL connect to Worker via WebRTC
- **AND** Client SHALL start local HTTP server
- **AND** Client SHALL open browser to viewer URL

#### Scenario: Browse command options
- **WHEN** browse command is invoked
- **THEN** it SHALL accept `--room` option (required)
- **AND** it SHALL accept `--token` option (required)
- **AND** it SHALL accept `--port` option (default 8765)
- **AND** it SHALL accept `--no-browser` to skip auto-open

#### Scenario: Missing credentials
- **WHEN** browse command is invoked without `--room` or `--token`
- **THEN** Client SHALL fail with clear error message
- **AND** Client SHALL NOT attempt connection

---

### Requirement: Filesystem Viewer Server
The system SHALL provide a local HTTP server to host the read-only filesystem viewer.

#### Scenario: Start viewer server
- **WHEN** browse command starts viewer
- **THEN** server SHALL generate random session token
- **AND** server SHALL bind to `127.0.0.1:8765` (or fallback port)
- **AND** server SHALL serve filesystem viewer UI at `/`
- **AND** server SHALL expose WebSocket endpoint at `/ws`

#### Scenario: Token authentication
- **WHEN** server generates URL for browser
- **THEN** URL SHALL include token parameter: `http://127.0.0.1:8765?token=<random>`
- **AND** WebSocket connections SHALL require matching token
- **AND** connections without valid token SHALL be rejected with 403

#### Scenario: Port already in use
- **WHEN** default port 8765 is unavailable
- **THEN** server SHALL try ports 8766, 8767, etc. up to 8775
- **AND** server SHALL display actual URL to user
- **AND** server SHALL fail with clear error if no ports available

#### Scenario: Auto-open browser
- **WHEN** viewer server starts
- **AND** `--no-browser` flag is NOT set
- **AND** display is available (DISPLAY set, or macOS/Windows)
- **THEN** Client SHALL attempt to open default browser to server URL
- **AND** Client SHALL print URL if browser fails to open

#### Scenario: Server stays open
- **WHEN** viewer is running
- **THEN** server SHALL remain open until user presses Ctrl+C
- **AND** user MAY copy multiple paths in one session
- **AND** server SHALL handle browser refresh/reconnect

---

### Requirement: WebSocket Relay
The system SHALL relay filesystem metadata requests between browser and Worker.

#### Scenario: Browser connects via WebSocket
- **WHEN** browser connects to `/ws?token=<token>` endpoint
- **THEN** server SHALL validate token
- **AND** server SHALL request worker info via `FS_GET_INFO`
- **AND** server SHALL request mounts via `FS_GET_MOUNTS`
- **AND** server SHALL send worker info and mounts to browser

#### Scenario: Browser requests directory listing
- **WHEN** browser sends `list_dir` message with `path`
- **THEN** server SHALL send `FS_LIST_DIR` to Worker via RTC data channel
- **AND** server SHALL wait for `FS_LIST_RESPONSE`
- **AND** server SHALL forward metadata response to browser

#### Scenario: Worker disconnection during browsing
- **WHEN** Worker WebRTC connection drops
- **THEN** server SHALL send `connection_lost` message to browser
- **AND** browser SHALL display reconnection prompt

---

### Requirement: Read-Only Viewer UI
The system SHALL provide a browser-based read-only filesystem viewer based on scratch/browser_ui.html design.

#### Scenario: Initial UI load
- **WHEN** user opens viewer URL in browser
- **THEN** UI SHALL display dark theme matching SLEAP branding
- **AND** UI SHALL connect to WebSocket endpoint with token
- **AND** UI SHALL display worker connection status

#### Scenario: Worker status display
- **WHEN** browser receives worker info
- **THEN** UI SHALL display worker identifier prominently
- **AND** UI SHALL show connection status indicator (connected/disconnected)
- **AND** UI SHALL display available mounts in sidebar or tabs

#### Scenario: Directory navigation
- **WHEN** user clicks on a directory
- **THEN** UI SHALL request directory listing from server (lazy loading)
- **AND** UI SHALL display contents in file grid with icons
- **AND** UI SHALL show breadcrumb navigation for current path
- **AND** UI SHALL allow navigating up to parent directory

#### Scenario: File metadata display
- **WHEN** directory contents are displayed
- **THEN** UI SHALL show file name, size (human-readable), and modified date
- **AND** UI SHALL display file type icons (folder, .slp, video, model)
- **AND** UI SHALL highlight `.slp` files with distinct color

#### Scenario: Path copying
- **WHEN** user clicks "Copy Path" button on a file
- **THEN** UI SHALL copy full Worker path to clipboard
- **AND** UI SHALL show toast notification confirming copy
- **AND** copied path SHALL be directly usable in CLI commands

#### Scenario: Result limits in viewer
- **WHEN** directory contains more than 20 items
- **THEN** UI SHALL display first 20 items
- **AND** UI SHALL show "showing 20 of N items" indicator
- **AND** UI MAY provide "Load more" button for additional items

#### Scenario: No file modification
- **WHEN** user interacts with viewer
- **THEN** UI SHALL NOT provide any file modification controls
- **AND** UI SHALL NOT allow file upload, download, rename, or delete
- **AND** UI SHALL be purely for viewing and path copying

---

### Requirement: Headless Fallback
The system SHALL support path discovery in headless environments.

#### Scenario: No display available for browse
- **WHEN** `browse` command is used in headless environment
- **THEN** Client SHALL print viewer URL to console
- **AND** Client SHALL instruct user to open URL in local browser
- **AND** Client SHALL wait for remote browser connection

#### Scenario: Non-interactive mode for training
- **WHEN** user specifies `--non-interactive` flag on `client-train`
- **AND** fuzzy resolution returns candidates
- **THEN** Client SHALL use first (highest-ranked) candidate automatically
- **AND** Client SHALL NOT display selection UI

#### Scenario: Skip resolution
- **WHEN** user provides `--worker-path` flag with exact Worker path
- **THEN** Client SHALL skip fuzzy resolution entirely
- **AND** Client SHALL use provided path directly

---

### Requirement: Error Handling
The system SHALL handle errors gracefully.

#### Scenario: Worker returns error
- **WHEN** Worker sends `FS_ERROR` response
- **THEN** Client SHALL display user-friendly error message
- **AND** Client SHALL offer alternative options (browse, manual, cancel)

#### Scenario: Connection timeout
- **WHEN** fuzzy resolution takes longer than 15 seconds
- **THEN** Client SHALL display partial results if available
- **AND** Client SHALL inform user of timeout
