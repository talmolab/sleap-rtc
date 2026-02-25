## ADDED Requirements

### Requirement: Browser-Based File Selection
The system SHALL provide a browser-based UI for selecting files from the worker's filesystem when automatic resolution fails.

#### Scenario: Open browser for file selection
- **Given** automatic path resolution returned `ambiguous` status
- **And** client has display available
- **When** resolution mode is `auto` or `interactive`
- **Then** client starts local HTTP server on port 8765
- **And** opens browser to `http://127.0.0.1:8765`
- **And** displays file browser UI

#### Scenario: Display initial candidates
- **Given** automatic resolution found multiple candidates
- **When** browser UI loads
- **Then** display candidates with:
  - File path
  - File size (human-readable)
  - Confidence score
  - Matching reasons
- **And** highlight recommended selection

#### Scenario: Browse worker filesystem
- **Given** browser UI is open
- **When** user clicks on a directory
- **Then** UI sends `FS_LIST` request to worker via WebSocket
- **And** displays directory contents
- **And** allows navigation up/down the directory tree

#### Scenario: Search from browser
- **Given** browser UI is open
- **When** user enters search term and clicks Search
- **Then** UI sends `FS_SEARCH` request to worker
- **And** displays search results
- **And** user can select from results

#### Scenario: Select file and confirm
- **Given** user navigates to or searches for a file
- **When** user clicks Select on a file
- **Then** browser sends selection to client
- **And** client receives selected path
- **And** continues with job submission using selected path

#### Scenario: Cancel selection
- **Given** browser UI is open
- **When** user clicks Cancel or closes browser
- **Then** client receives cancellation signal
- **And** job submission is aborted with clear message

---

### Requirement: Browser Bridge HTTP Server
The system SHALL run a local HTTP server to serve the browser UI and relay requests to the worker.

#### Scenario: Start browser bridge server
- **Given** path resolution requires browser interaction
- **When** browser bridge starts
- **Then** HTTP server binds to `127.0.0.1:8765`
- **And** serves static HTML/JS UI at `/`
- **And** WebSocket endpoint available at `/ws`

#### Scenario: Port conflict handling
- **Given** port 8765 is already in use
- **When** browser bridge attempts to start
- **Then** try next available port (8766, 8767, ...)
- **And** display actual URL to user

#### Scenario: Relay WebSocket messages to worker
- **Given** browser connected via WebSocket
- **When** browser sends `fs_*` message
- **Then** bridge forwards to worker via WebRTC data channel
- **And** returns worker response to browser

#### Scenario: Selection message handling
- **Given** browser sends `select_path` message
- **When** bridge receives selection
- **Then** store selected path
- **And** signal selection event to waiting client code
- **And** respond with confirmation

#### Scenario: Auto-open browser
- **Given** `auto_open_browser` is true (default)
- **When** browser bridge starts
- **Then** automatically open default browser to server URL
- **And** if browser fails to open, print URL for manual access

#### Scenario: Headless fallback message
- **Given** browser cannot be opened (headless environment)
- **When** `--browse` flag is used
- **Then** print URL to console
- **And** wait for user to manually open browser

---

### Requirement: Browser UI Design
The browser UI SHALL provide intuitive file navigation and selection.

#### Scenario: Initial UI state
- **Given** browser loads the file browser
- **When** page renders
- **Then** display:
  - Header with "SLEAP-RTC File Browser"
  - Searching for: `{filename}` (if provided)
  - Candidate files (if any, with confidence scores)
  - Allowed roots as starting points
  - Search input field
  - Cancel button

#### Scenario: Directory tree navigation
- **Given** user clicks on a directory
- **When** directory contents load
- **Then** display breadcrumb path
- **And** show directories first, then files
- **And** show file metadata (size, extension)
- **And** highlight `.slp` files visually

#### Scenario: File filtering
- **Given** directory contains many files
- **When** user is searching for `.slp` files
- **Then** `.slp` files are visually highlighted
- **And** option to filter to show only `.slp` files

#### Scenario: Selection confirmation
- **Given** user selects a file
- **When** user clicks Select button
- **Then** show confirmation: "Use `/path/to/file.slp` for training?"
- **And** provide Confirm and Back buttons

#### Scenario: Error display
- **Given** worker returns error (e.g., permission denied)
- **When** error response received
- **Then** display error message prominently
- **And** allow user to try different path

---

### Requirement: Browser Bridge Security
The browser bridge SHALL implement security measures to prevent unauthorized access.

#### Scenario: Localhost-only binding
- **Given** browser bridge starts
- **When** server binds
- **Then** bind only to `127.0.0.1` (not `0.0.0.0`)
- **And** reject connections from external IPs

#### Scenario: Session token validation (future consideration)
- **Given** malicious website attempts WebSocket connection
- **When** connection attempted without valid session
- **Then** connection is rejected
- **Note**: Initial implementation may skip token validation for simplicity

#### Scenario: Timeout on no selection
- **Given** browser bridge is waiting for selection
- **When** 5 minutes pass with no interaction
- **Then** timeout and close server
- **And** return timeout error to client

---

### Requirement: CLI Options for Path Resolution
The CLI SHALL provide options to control path resolution behavior.

#### Scenario: Use explicit worker path
- **Given** user runs: `sleap-rtc client-train --worker-path /home/jovyan/vast/labels.slp`
- **When** job submission starts
- **Then** skip all path resolution
- **And** use provided path directly as worker path

#### Scenario: Force browser selection
- **Given** user runs: `sleap-rtc client-train --browse`
- **When** job submission starts
- **Then** always open browser for file selection
- **And** skip automatic resolution

#### Scenario: Headless with best guess
- **Given** user runs: `sleap-rtc client-train --pkg_path /local/labels.slp --headless`
- **When** multiple candidates found
- **Then** automatically select highest confidence match
- **And** log warning about automatic selection

#### Scenario: Headless strict mode
- **Given** user runs: `sleap-rtc client-train --pkg_path /local/labels.slp --headless --strict`
- **When** resolution is ambiguous (multiple candidates, no high confidence)
- **Then** raise error with candidate list
- **And** suggest using `--worker-path` for explicit path

#### Scenario: Backward compatibility
- **Given** user runs: `sleap-rtc client-train --pkg_path /local/labels.slp`
- **When** worker has I/O paths configured
- **Then** attempt automatic resolution
- **And** fallback to browser if needed (auto mode)
- **And** existing behavior preserved if no I/O paths configured
