# Implementation Tasks

## Phase 1: Configuration & Protocol

### 1.1 Mount Configuration
- [x] 1.1.1 Add `MountConfig` dataclass to `config.py` with `path`, `label` fields
- [x] 1.1.2 Add `MountsConfig` class to parse `[[worker.io.mounts]]` TOML array
- [x] 1.1.3 Add mount loading to Worker startup
- [x] 1.1.4 Add validation for mount paths (exists, is directory)
- [x] 1.1.5 Update `config.example.toml` with mount configuration examples
- [x] 1.1.6 Write unit tests for mount config parsing

### 1.2 Worker Working Directory
- [x] 1.2.1 Add `--working-dir` option to Worker CLI in `cli.py`
- [x] 1.2.2 Add `working_dir` field to Worker config in TOML
- [x] 1.2.3 Implement working directory change on Worker startup
- [x] 1.2.4 Add validation for working directory path
- [x] 1.2.5 CLI option should override config value

### 1.3 Protocol Messages
- [x] 1.3.1 Add `MSG_FS_GET_MOUNTS` and `MSG_FS_MOUNTS_RESPONSE` to `protocol.py`
- [x] 1.3.2 Add `MSG_FS_GET_INFO` and `MSG_FS_INFO_RESPONSE` constants
- [x] 1.3.3 Add `MSG_FS_RESOLVE` and `MSG_FS_RESOLVE_RESPONSE` constants
- [x] 1.3.4 Add `MSG_FS_LIST_DIR` and `MSG_FS_LIST_RESPONSE` constants
- [x] 1.3.5 Add `MSG_FS_ERROR` constant with error codes (`ACCESS_DENIED`, `PATTERN_TOO_BROAD`)
- [x] 1.3.6 Document message formats in protocol docstrings

## Phase 2: Worker Filesystem Operations

### 2.1 FileManager Extensions
- [x] 2.1.1 Add `mounts` property to `FileManager` class
- [x] 2.1.2 Implement `set_mounts(mounts: List[MountConfig])` method
- [x] 2.1.3 Implement `_is_path_allowed(path: Path) -> bool` security check
- [x] 2.1.4 Implement `get_mounts() -> List[dict]` returning mount metadata
- [x] 2.1.5 Implement `get_worker_info() -> dict` returning worker_id, working_dir, mounts

### 2.2 Fuzzy Resolution with Wildcards
- [x] 2.2.1 Implement `fuzzy_resolve(pattern: str, size: int, max_depth: int) -> List[dict]`
- [x] 2.2.2 Implement `_is_wildcard_pattern(pattern: str) -> bool` detection
- [x] 2.2.3 Implement `_validate_pattern(pattern: str)` - require min 3 non-wildcard chars
- [x] 2.2.4 Implement `_match_filename(pattern: str, filename: str) -> MatchResult` using fnmatch
- [x] 2.2.5 Implement `_scan_directory(path, pattern, depth, max_depth)` lazy scanner
- [x] 2.2.6 Implement `_calculate_score(match_type, size_match, path_tokens)` ranking
- [x] 2.2.7 Add early termination after 20 candidates
- [x] 2.2.8 Add 10-second timeout with partial results
- [x] 2.2.9 Write unit tests for wildcard matching
- [x] 2.2.10 Write unit tests for fuzzy ranking

### 2.3 Directory Listing
- [x] 2.3.1 Implement `list_directory(path: str, offset: int) -> dict` method
- [x] 2.3.2 Return max 20 items with `total_count` and `has_more` fields
- [x] 2.3.3 Return metadata only (name, type, size, modified)
- [x] 2.3.4 Sort directories first, then alphabetically
- [x] 2.3.5 Add path canonicalization for security
- [x] 2.3.6 Write security tests for path traversal prevention

### 2.4 Worker Message Routing
- [x] 2.4.1 Add `handle_fs_message(message: str) -> str` method to `RTCWorkerClient`
- [x] 2.4.2 Route `FS_GET_MOUNTS` to `FileManager.get_mounts()`
- [x] 2.4.3 Route `FS_GET_INFO` to `FileManager.get_worker_info()`
- [x] 2.4.4 Route `FS_RESOLVE` to `FileManager.fuzzy_resolve()`
- [x] 2.4.5 Route `FS_LIST_DIR` to `FileManager.list_directory()`
- [x] 2.4.6 Update data channel `on_message` to detect and route `FS_*` messages
- [x] 2.4.7 Wrap operations in try/except returning `FS_ERROR`

## Phase 3: Client Arrow Selection UI

### 3.1 Interactive Selection Component
- [x] 3.1.1 Add `prompt_toolkit` dependency to `pyproject.toml`
- [x] 3.1.2 Create `sleap_rtc/client/file_selector.py`
- [x] 3.1.3 Implement `ArrowSelector` class with keyboard handling
- [x] 3.1.4 Implement arrow key navigation (↑/↓) with wrap-around
- [x] 3.1.5 Implement Enter to confirm, Escape to cancel
- [x] 3.1.6 Implement display formatting (path, size, highlight)
- [x] 3.1.7 Implement terminal capability detection
- [x] 3.1.8 Implement numbered fallback for dumb terminals

### 3.2 Resolution Flow
- [x] 3.2.1 Add `resolve_file_path(local_path: str) -> str` method to `RTCClient`
- [x] 3.2.2 Extract filename and get local file size
- [x] 3.2.3 Send `FS_RESOLVE` message to Worker
- [x] 3.2.4 Parse `FS_RESOLVE_RESPONSE` candidates
- [x] 3.2.5 If exact match found on Worker, proceed without UI
- [x] 3.2.6 If fuzzy results, display arrow selector
- [x] 3.2.7 Handle no-matches case (show options menu)
- [x] 3.2.8 Handle 'W' key for wildcard retry prompt

### 3.3 CLI Integration for client-train
- [x] 3.3.1 Integrate resolution into `client-train` command flow
- [x] 3.3.2 Add `--worker-path` flag to skip resolution
- [x] 3.3.3 Add `--non-interactive` flag for CI/scripts
- [x] 3.3.4 Update CLI help text with examples

## Phase 4: Browse Command & Viewer

### 4.1 Browse CLI Command
- [x] 4.1.1 Add `browse` command to `cli.py`
- [x] 4.1.2 Add `--room` option (required)
- [x] 4.1.3 Add `--token` option (required)
- [x] 4.1.4 Add `--port` option (default 8765)
- [x] 4.1.5 Add `--no-browser` flag
- [x] 4.1.6 Add validation to fail if --room or --token missing
- [x] 4.1.7 Implement Worker connection via WebRTC
- [x] 4.1.8 Implement graceful shutdown on Ctrl+C

### 4.2 HTTP/WebSocket Server with Token Auth
- [x] 4.2.1 Add `aiohttp` dependency to `pyproject.toml`
- [x] 4.2.2 Create `sleap_rtc/client/fs_viewer_server.py`
- [x] 4.2.3 Implement `FSViewerServer` class with `start()`, `stop()` methods
- [x] 4.2.4 Implement token generation using `secrets.token_urlsafe(16)`
- [x] 4.2.5 Implement HTTP route `/` serving embedded HTML viewer
- [x] 4.2.6 Implement WebSocket handler `/ws` with token validation
- [x] 4.2.7 Reject connections without valid token (403)
- [x] 4.2.8 Implement port fallback logic (try 8765-8775)
- [x] 4.2.9 Implement browser auto-open using `webbrowser` module

### 4.3 Message Relay
- [x] 4.3.1 On WebSocket connect: request `FS_GET_INFO` and `FS_GET_MOUNTS` from Worker
- [x] 4.3.2 Implement relay of `list_dir` browser message to Worker `FS_LIST_DIR`
- [x] 4.3.3 Implement response forwarding from Worker to browser
- [x] 4.3.4 Handle Worker disconnection (send `connection_lost` to browser)
- [x] 4.3.5 Add request debouncing (100ms)

### 4.4 Browser UI (Based on scratch/browser_ui.html)
- [x] 4.4.1 Copy `scratch/browser_ui.html` to `sleap_rtc/client/static/fs_viewer.html`
- [x] 4.4.2 Remove simulation controls section
- [x] 4.4.3 Add worker status header with connection indicator
- [x] 4.4.4 Replace mock `workerFilesystem` with WebSocket data
- [x] 4.4.5 Implement WebSocket connection with token from URL param
- [x] 4.4.6 Implement mount list population from worker info
- [x] 4.4.7 Implement directory loading on click with `list_dir` message
- [x] 4.4.8 Implement breadcrumb navigation
- [x] 4.4.9 Replace "Use This Path" with "Copy Path" button
- [x] 4.4.10 Implement clipboard copy with `navigator.clipboard` API
- [x] 4.4.11 Add "showing 20 of N items" indicator when paginated
- [x] 4.4.12 Implement error display
- [x] 4.4.13 Implement connection lost state

## Phase 5: Testing & Documentation

### 5.1 Integration Tests
- [ ] 5.1.1 Test mount configuration loading and validation
- [ ] 5.1.2 Test working directory CLI option
- [ ] 5.1.3 Test wildcard pattern matching (`fly_*.slp`, `*tracking*`)
- [ ] 5.1.4 Test pattern validation (reject `*` alone)
- [ ] 5.1.5 Test fuzzy resolution with exact match (skips UI)
- [ ] 5.1.6 Test fuzzy resolution with multiple candidates
- [ ] 5.1.7 Test fuzzy resolution with no matches
- [ ] 5.1.8 Test directory listing with pagination
- [ ] 5.1.9 Test directory listing security (path traversal rejection)
- [ ] 5.1.10 Test arrow selector keyboard handling
- [ ] 5.1.11 Test viewer server token authentication
- [ ] 5.1.12 Test viewer server startup and shutdown

### 5.2 Manual Testing
- [ ] 5.2.1 Test arrow selection with real terminal
- [ ] 5.2.2 Test numbered fallback in dumb terminal
- [ ] 5.2.3 Test wildcard search with real `.slp` files
- [ ] 5.2.4 Test `browse` command opens browser
- [ ] 5.2.5 Test viewer UI on Chrome, Firefox, Safari
- [ ] 5.2.6 Test viewer with large directories
- [ ] 5.2.7 Test headless mode (print URL for remote browser)
- [ ] 5.2.8 Test token rejection for invalid tokens
- [ ] 5.2.9 Test complete training flow with path resolution

### 5.3 Documentation
- [ ] 5.3.1 Update README with usage examples
- [ ] 5.3.2 Add mount configuration to worker setup docs
- [ ] 5.3.3 Document CLI commands (`browse`, `client-train` with resolution)
- [ ] 5.3.4 Document `--working-dir`, `--worker-path`, `--non-interactive` flags
- [ ] 5.3.5 Add troubleshooting section for common issues

## Dependencies

- Phase 2 depends on Phase 1 (config and protocol)
- Phase 3 depends on Phase 2 (Worker operations)
- Phase 4 depends on Phase 1 and Phase 2 (protocol and Worker ops)
- Phase 5 depends on all previous phases

## Parallelizable Work

- 1.1 (Mounts), 1.2 (Working Dir), 1.3 (Protocol) can be done in parallel
- 2.2 (Fuzzy) and 2.3 (Listing) can be done in parallel
- 3.x (Arrow selection) and 4.x (Browse command) can be done in parallel after Phase 2
- 4.1 (CLI), 4.2 (Server), 4.3 (Relay), and 4.4 (UI) should be done sequentially

## New Dependencies

- `prompt_toolkit` - for arrow-key selection UI
- `aiohttp` - for HTTP/WebSocket server
- `secrets` - for token generation (stdlib, no install needed)
