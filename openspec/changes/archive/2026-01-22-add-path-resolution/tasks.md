# Implementation Tasks

## Phase 1: Configuration & Protocol Foundation

### 1.1 Configuration Extensions
- [ ] 1.1.1 Add `MountAlias` dataclass to `config.py` with fields: `name`, `worker_path`, `client_paths`, `description`
- [ ] 1.1.2 Add `allowed_roots` field to `WorkerIOConfig` class
- [ ] 1.1.3 Add `mounts` list field to `WorkerIOConfig` for mount aliases
- [ ] 1.1.4 Update TOML parsing to handle `[[worker.io.mounts]]` array
- [ ] 1.1.5 Add validation for mount alias paths (worker_path exists, no overlapping prefixes)
- [ ] 1.1.6 Write unit tests for config parsing with mount aliases

### 1.2 Protocol Extension
- [ ] 1.2.1 Add `MSG_FS_GET_ROOTS` and `MSG_FS_GET_ROOTS_RESPONSE` constants to `protocol.py`
- [ ] 1.2.2 Add `MSG_FS_LIST` and `MSG_FS_LIST_RESPONSE` constants
- [ ] 1.2.3 Add `MSG_FS_SEARCH` and `MSG_FS_SEARCH_RESPONSE` constants
- [ ] 1.2.4 Add `MSG_FS_RESOLVE` and `MSG_FS_RESOLVE_RESPONSE` constants
- [ ] 1.2.5 Add `MSG_FS_ERROR` constant
- [ ] 1.2.6 Update `format_message` and `parse_message` to handle new message types if needed

## Phase 2: Worker Filesystem Operations

### 2.1 FileManager Extension
- [ ] 2.1.1 Add `allowed_roots` property to `FileManager` class
- [ ] 2.1.2 Implement `_is_path_allowed(path)` method for security validation
- [ ] 2.1.3 Implement `get_allowed_roots()` method returning list of browsable directories
- [ ] 2.1.4 Implement `list_directory(path, depth)` method with recursive listing
- [ ] 2.1.5 Implement `search_file(filename, root, max_results)` method using `rglob`
- [ ] 2.1.6 Implement `resolve_path(client_path, aliases, size)` method with mount alias translation
- [ ] 2.1.7 Implement `_rank_candidates(original_path, size, candidates)` for confidence scoring
- [ ] 2.1.8 Add comprehensive security tests for path traversal prevention
- [ ] 2.1.9 Add unit tests for each filesystem method

### 2.2 Worker Message Routing
- [ ] 2.2.1 Add `handle_filesystem_message(message)` method to `RTCWorkerClient`
- [ ] 2.2.2 Route `FS_GET_ROOTS` to `FileManager.get_allowed_roots()`
- [ ] 2.2.3 Route `FS_LIST` to `FileManager.list_directory()`
- [ ] 2.2.4 Route `FS_SEARCH` to `FileManager.search_file()`
- [ ] 2.2.5 Route `FS_RESOLVE` to `FileManager.resolve_path()`
- [ ] 2.2.6 Update `on_message` handler in `worker_class.py` to detect and route `FS_*` messages
- [ ] 2.2.7 Add error handling wrapper that returns `FS_ERROR` on exceptions

## Phase 3: Client Path Resolution

### 3.1 Path Resolver Module
- [ ] 3.1.1 Create `sleap_rtc/client/path_resolver.py`
- [ ] 3.1.2 Implement `ResolutionResult` dataclass (status, path, method, confidence, candidates, error)
- [ ] 3.1.3 Implement `PathResolver` class with `__init__(send_to_worker, mount_aliases, browser_port, timeout)`
- [ ] 3.1.4 Implement `resolve(client_path, mode, headless_strategy)` async method
- [ ] 3.1.5 Implement `_handle_not_found()` method for not found cases
- [ ] 3.1.6 Implement `_handle_ambiguous()` method for multiple candidates
- [ ] 3.1.7 Implement `_select_via_cli()` for headless terminal prompts
- [ ] 3.1.8 Implement `_has_display()` method to detect GUI availability
- [ ] 3.1.9 Add unit tests for path resolver logic

### 3.2 Client Integration
- [ ] 3.2.1 Create `send_and_wait(message)` helper method in `RTCClient` for request/response pattern
- [ ] 3.2.2 Integrate path resolution into `on_channel_open()` before file transfer
- [ ] 3.2.3 Store resolved path for use in job submission
- [ ] 3.2.4 Handle resolution failure with appropriate error messages
- [ ] 3.2.5 Update `send_file_via_io_paths()` to use resolved path

### 3.3 CLI Options
- [ ] 3.3.1 Add `--worker-path` option to `client-train` command in `cli.py`
- [ ] 3.3.2 Add `--browse` flag to force browser selection
- [ ] 3.3.3 Add `--headless` flag to disable browser fallback
- [ ] 3.3.4 Add `--strict` flag to fail on ambiguous resolution
- [ ] 3.3.5 Update CLI help text with path resolution examples
- [ ] 3.3.6 Ensure backward compatibility with existing `--pkg_path` usage

## Phase 4: Browser-Based File Browser

### 4.1 Browser Bridge Server
- [ ] 4.1.1 Add `aiohttp` to project dependencies in `pyproject.toml`
- [ ] 4.1.2 Create `sleap_rtc/client/browser_bridge.py`
- [ ] 4.1.3 Implement `FilesystemBrowserBridge` class
- [ ] 4.1.4 Implement `start(open_browser, initial_candidates, searching_for)` method
- [ ] 4.1.5 Implement `stop()` method for cleanup
- [ ] 4.1.6 Implement `wait_for_selection(timeout)` async method
- [ ] 4.1.7 Implement HTTP route `/` for serving static UI
- [ ] 4.1.8 Implement HTTP route `/api/init` for initial state
- [ ] 4.1.9 Implement WebSocket handler `/ws` for filesystem operations
- [ ] 4.1.10 Implement message relay to worker via WebRTC data channel
- [ ] 4.1.11 Handle `select_path` and `cancel` messages from browser
- [ ] 4.1.12 Implement port fallback when 8765 is in use

### 4.2 Browser UI
- [ ] 4.2.1 Create `sleap_rtc/client/static/` directory
- [ ] 4.2.2 Create `browser_ui.html` with embedded CSS and JavaScript
- [ ] 4.2.3 Implement WebSocket connection to bridge server
- [ ] 4.2.4 Implement initial state loading from `/api/init`
- [ ] 4.2.5 Implement candidate display with confidence scores
- [ ] 4.2.6 Implement directory tree navigation
- [ ] 4.2.7 Implement breadcrumb navigation
- [ ] 4.2.8 Implement file search UI
- [ ] 4.2.9 Implement file selection and confirmation
- [ ] 4.2.10 Implement cancel functionality
- [ ] 4.2.11 Implement error display
- [ ] 4.2.12 Style UI with dark theme matching SLEAP branding

### 4.3 Path Resolver Browser Integration
- [ ] 4.3.1 Implement `_select_via_browser()` method in `PathResolver`
- [ ] 4.3.2 Initialize and manage `FilesystemBrowserBridge` lifecycle
- [ ] 4.3.3 Handle browser selection result
- [ ] 4.3.4 Handle browser cancellation

## Phase 5: Testing & Documentation

### 5.1 Integration Tests
- [ ] 5.1.1 Test mount alias configuration loading
- [ ] 5.1.2 Test path resolution with exact mount alias match
- [ ] 5.1.3 Test path resolution with filename search fallback
- [ ] 5.1.4 Test ambiguous resolution handling
- [ ] 5.1.5 Test headless mode best guess selection
- [ ] 5.1.6 Test headless mode strict failure
- [ ] 5.1.7 Test `--worker-path` bypass
- [ ] 5.1.8 Test security (path traversal rejection)

### 5.2 Manual Testing
- [ ] 5.2.1 Test browser UI on macOS
- [ ] 5.2.2 Test browser UI on Linux with display
- [ ] 5.2.3 Test headless mode in SSH session
- [ ] 5.2.4 Test with real SLEAP .slp files
- [ ] 5.2.5 Test end-to-end training job with path resolution

### 5.3 Documentation
- [ ] 5.3.1 Update README with path resolution usage examples
- [ ] 5.3.2 Add configuration section for mount aliases
- [ ] 5.3.3 Document CLI options for path resolution
- [ ] 5.3.4 Add troubleshooting section for common resolution issues

## Dependencies

- Phase 2 depends on Phase 1 (config and protocol)
- Phase 3 depends on Phase 2 (worker filesystem operations)
- Phase 4 depends on Phase 3 (path resolver)
- Phase 5 depends on all previous phases

## Parallelizable Work

- 1.1 (Config) and 1.2 (Protocol) can be done in parallel
- 2.1 (FileManager) and 2.2 (Message Routing) should be sequential
- 3.1 (Path Resolver), 3.2 (Client Integration), 3.3 (CLI) can be partially parallel
- 4.1 (Browser Bridge) and 4.2 (Browser UI) can be done in parallel
- 5.1 (Integration Tests) and 5.3 (Documentation) can be partially parallel
