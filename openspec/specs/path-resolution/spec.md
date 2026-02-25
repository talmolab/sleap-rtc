# path-resolution Specification

## Purpose
TBD - created by archiving change add-path-resolution. Update Purpose after archive.
## Requirements
### Requirement: Mount Alias Configuration
The system SHALL support configuration of mount aliases that map client-side paths to worker-side paths.

#### Scenario: Configure mount aliases in TOML
- **Given** a `sleap-rtc.toml` file with:
  ```toml
  [worker.io]
  allowed_roots = ["/home/jovyan/vast"]

  [[worker.io.mounts]]
  name = "lab_data"
  worker_path = "/home/jovyan/vast/amick"
  client_paths = ["/Volumes/talmo/amick", "/mnt/talmo/amick"]
  ```
- **When** the worker loads configuration
- **Then** the worker registers the mount alias mapping
- **And** the mapping is available for path resolution

#### Scenario: Multiple mount aliases
- **Given** configuration with two mount aliases:
  ```toml
  [[worker.io.mounts]]
  name = "lab_data"
  worker_path = "/home/jovyan/vast/amick"
  client_paths = ["/Volumes/talmo/amick"]

  [[worker.io.mounts]]
  name = "scratch"
  worker_path = "/scratch"
  client_paths = ["/tmp/sleap-scratch"]
  ```
- **When** the worker loads configuration
- **Then** both mount aliases are registered
- **And** paths under either client prefix can be resolved

---

### Requirement: Automatic Path Resolution via Mount Aliases
The system SHALL automatically translate client paths to worker paths using configured mount aliases.

#### Scenario: Successful mount alias translation
- **Given** mount alias: `/Volumes/talmo/amick` -> `/home/jovyan/vast/amick`
- **And** client provides path `/Volumes/talmo/amick/project/labels.slp`
- **When** the client requests path resolution
- **Then** the system resolves to `/home/jovyan/vast/amick/project/labels.slp`
- **And** returns resolution status `resolved` with method `mount_alias`
- **And** returns confidence `1.0`

#### Scenario: Windows path translation
- **Given** mount alias: `Z:\talmo\amick` -> `/home/jovyan/vast/amick`
- **And** client provides path `Z:\talmo\amick\project\labels.slp`
- **When** the client requests path resolution
- **Then** path separators are normalized
- **And** the system resolves to `/home/jovyan/vast/amick/project/labels.slp`

#### Scenario: No matching mount alias
- **Given** mount aliases that do not match client path
- **And** client provides path `/Users/local/data/labels.slp`
- **When** the client requests path resolution
- **Then** the system falls back to filename search

---

### Requirement: Filename Search Fallback
The system SHALL search for files by filename when mount alias translation fails.

#### Scenario: Single filename match
- **Given** no mount alias matches the client path
- **And** client provides path `/local/data/labels.slp`
- **And** file `labels.slp` exists at `/home/jovyan/vast/project/labels.slp` (and nowhere else)
- **When** the worker searches for the filename
- **Then** returns the single match
- **And** resolution status is `resolved` with method `filename_search`

#### Scenario: Multiple filename matches with ranking
- **Given** no mount alias matches
- **And** file `labels.slp` exists at:
  - `/home/jovyan/vast/amick/project/labels.slp` (100 MB)
  - `/home/jovyan/vast/other/labels.slp` (50 MB)
- **And** client's local file is 100 MB
- **When** the worker searches and ranks candidates
- **Then** candidates are ranked by:
  - Exact size match (highest weight)
  - Path component overlap with client path
  - Filename match (base score)
- **And** resolution status is `ambiguous` if top confidence < 0.9

#### Scenario: High confidence auto-select
- **Given** multiple matches but one has confidence > 0.9
- **When** ranking candidates
- **Then** automatically select the high-confidence match
- **And** include alternatives in response for transparency

---

### Requirement: Worker Filesystem Browsing
The system SHALL allow clients to browse the worker's filesystem within allowed roots.

#### Scenario: Get allowed roots
- **Given** worker configured with `allowed_roots = ["/home/jovyan/vast", "/scratch"]`
- **When** client sends `FS_GET_ROOTS` message
- **Then** worker responds with:
  ```json
  {
    "type": "FS_GET_ROOTS_RESPONSE",
    "roots": [
      {"path": "/home/jovyan/vast", "name": "vast", "exists": true},
      {"path": "/scratch", "name": "scratch", "exists": true}
    ]
  }
  ```

#### Scenario: List directory contents
- **Given** allowed root `/home/jovyan/vast`
- **When** client sends `FS_LIST::/home/jovyan/vast/amick::2` (depth 2)
- **Then** worker returns directory contents up to depth 2:
  ```json
  {
    "type": "FS_LIST_RESPONSE",
    "path": "/home/jovyan/vast/amick",
    "contents": [
      {"name": "project", "type": "dir", "children": [...]},
      {"name": "data.slp", "type": "file", "size": 104857600, "extension": "slp"}
    ]
  }
  ```

#### Scenario: Reject path outside allowed roots
- **Given** allowed roots do not include `/etc`
- **When** client sends `FS_LIST::/etc/passwd`
- **Then** worker responds with `FS_ERROR::Permission denied`

#### Scenario: Reject path traversal attempt
- **Given** allowed root `/home/jovyan/vast`
- **When** client sends `FS_LIST::/home/jovyan/vast/../../../etc/passwd`
- **Then** worker resolves path and detects escape attempt
- **And** responds with `FS_ERROR::Permission denied`

---

### Requirement: File Search
The system SHALL support searching for files by name or pattern within allowed roots.

#### Scenario: Search by exact filename
- **Given** allowed root `/home/jovyan/vast`
- **When** client sends `FS_SEARCH::labels.slp`
- **Then** worker searches recursively under allowed roots
- **And** returns matching files:
  ```json
  {
    "type": "FS_SEARCH_RESPONSE",
    "results": [
      {"path": "/home/jovyan/vast/project/labels.slp", "size": 104857600, "type": "file"}
    ]
  }
  ```

#### Scenario: Search with glob pattern
- **Given** allowed root `/home/jovyan/vast`
- **When** client sends `FS_SEARCH::*.slp`
- **Then** worker finds all `.slp` files under allowed roots
- **And** limits results to `max_results` (default 20)

#### Scenario: Search timeout
- **Given** very large filesystem
- **And** search timeout configured as 30 seconds
- **When** search exceeds timeout
- **Then** return partial results found so far
- **And** include `truncated: true` in response

---

### Requirement: Client Path Resolver Orchestration
The client SHALL orchestrate path resolution with configurable fallback strategies.

#### Scenario: Auto mode with display available
- **Given** client runs in environment with display (macOS, Windows, or DISPLAY set)
- **And** resolution mode is `auto`
- **When** automatic resolution fails or is ambiguous
- **Then** client opens browser for manual selection

#### Scenario: Headless mode with best guess
- **Given** client runs in headless environment (no display)
- **And** `--headless` flag is set
- **And** headless strategy is `best_guess`
- **When** multiple ambiguous candidates are found
- **Then** client selects highest confidence candidate
- **And** logs warning about automatic selection

#### Scenario: Headless mode with strict
- **Given** client runs with `--headless --strict` flags
- **When** resolution is ambiguous
- **Then** client raises error instead of guessing
- **And** displays candidates for manual intervention

#### Scenario: Explicit worker path bypass
- **Given** user provides `--worker-path /home/jovyan/vast/exact/path.slp`
- **When** client submits job
- **Then** skip all resolution
- **And** use provided path directly

---

### Requirement: Message Protocol for Filesystem Operations
The system SHALL use the existing message protocol pattern for filesystem operations.

#### Scenario: Format filesystem messages
- **Given** existing `format_message` and `parse_message` functions
- **When** sending filesystem operation
- **Then** use format: `MSG_TYPE::arg1::arg2::...`
- **And** message types follow `MSG_FS_*` naming convention

#### Scenario: Handle filesystem errors
- **Given** filesystem operation fails
- **When** worker sends error response
- **Then** message format is `FS_ERROR::error_type::details`
- **And** error types include: `Permission denied`, `Not found`, `Timeout`

