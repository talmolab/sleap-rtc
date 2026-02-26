# Worker Mounts Capability

## ADDED Requirements

### Requirement: Mount Configuration
The system SHALL allow Workers to configure browsable filesystem mount points via TOML configuration.

#### Scenario: Worker loads mount configuration
- **WHEN** Worker starts with `[[worker.io.mounts]]` configuration
- **THEN** Worker SHALL parse each mount entry
- **AND** Worker SHALL validate that each `path` exists and is a directory
- **AND** Worker SHALL store mount configurations for runtime access

#### Scenario: Mount entry structure
- **WHEN** a mount entry is defined in configuration
- **THEN** it SHALL have a `path` field (required, absolute path string)
- **AND** it SHALL have a `label` field (required, human-readable display name)

#### Scenario: Missing mount path
- **WHEN** Worker loads a mount entry with non-existent `path`
- **THEN** Worker SHALL log a warning
- **AND** Worker SHALL exclude that mount from available mounts
- **AND** Worker SHALL continue loading other mounts

---

### Requirement: Worker Working Directory
The system SHALL allow Workers to set a working directory via CLI option.

#### Scenario: Set working directory via CLI
- **WHEN** Worker starts with `--working-dir /path/to/dir` option
- **THEN** Worker SHALL change to specified directory on startup
- **AND** Worker SHALL use this directory as base for relative paths

#### Scenario: Invalid working directory
- **WHEN** Worker starts with `--working-dir` pointing to non-existent path
- **THEN** Worker SHALL fail with clear error message
- **AND** Worker SHALL NOT start

#### Scenario: Working directory in config
- **WHEN** Worker has `working_dir` in TOML config and no CLI override
- **THEN** Worker SHALL use config value
- **AND** CLI option SHALL take precedence over config

---

### Requirement: Mount Advertisement
The system SHALL advertise available mounts to connected Clients upon request.

#### Scenario: Client requests available mounts
- **WHEN** Client sends `FS_GET_MOUNTS` message via data channel
- **THEN** Worker SHALL respond with `FS_MOUNTS_RESPONSE` message
- **AND** response SHALL include array of mount objects with `label` and `path` fields

#### Scenario: No mounts configured
- **WHEN** Client requests mounts and no mounts are configured
- **THEN** Worker SHALL respond with empty array

---

### Requirement: Worker Info
The system SHALL provide Worker information for browser status display.

#### Scenario: Client requests worker info
- **WHEN** Client sends `FS_GET_INFO` message via data channel
- **THEN** Worker SHALL respond with `FS_INFO_RESPONSE` message
- **AND** response SHALL include `worker_id`, `working_dir`, and `mounts` fields

---

### Requirement: Fuzzy Path Resolution with Wildcards
The system SHALL resolve Client file patterns to Worker paths using lazy fuzzy matching with wildcard support.

#### Scenario: Exact filename search
- **WHEN** Client sends `FS_RESOLVE` with filename pattern without wildcards
- **AND** exact filename exists within a configured mount
- **THEN** Worker SHALL return candidate with `match_type: "exact"`
- **AND** candidate SHALL include full Worker path, size, and modified date

#### Scenario: Wildcard pattern search
- **WHEN** Client sends `FS_RESOLVE` with pattern containing wildcards (`*`, `?`, `[abc]`)
- **THEN** Worker SHALL use glob-style matching (fnmatch)
- **AND** `*` SHALL match any sequence of characters
- **AND** `?` SHALL match any single character
- **AND** `[abc]` SHALL match any character in the set

#### Scenario: Pattern validation
- **WHEN** Client sends pattern with only wildcards (e.g., `*` or `*.*`)
- **THEN** Worker SHALL reject with `FS_ERROR` code `PATTERN_TOO_BROAD`
- **AND** error message SHALL explain minimum 3 non-wildcard characters required

#### Scenario: Lazy directory scanning
- **WHEN** Worker performs fuzzy search
- **THEN** Worker SHALL scan directories on-demand (not pre-indexed)
- **AND** Worker SHALL scan up to configured depth limit (default 5)
- **AND** Worker SHALL stop scanning a branch after finding sufficient matches

#### Scenario: Filename-first ranking
- **WHEN** Worker finds multiple candidate files
- **THEN** Worker SHALL rank by match type first:
  - Exact filename match (highest)
  - Wildcard pattern match
  - Fuzzy match (Levenshtein distance)
- **AND** Worker SHALL use file size as secondary ranking factor
- **AND** Worker SHALL use path token similarity as tertiary factor

#### Scenario: Result limits
- **WHEN** fuzzy search finds matches
- **THEN** Worker SHALL return maximum 20 candidates
- **AND** candidates SHALL be sorted by score descending
- **AND** response SHALL include `truncated: true` if more results exist

#### Scenario: Search timeout
- **WHEN** fuzzy search exceeds 10 seconds
- **THEN** Worker SHALL return partial results found so far
- **AND** response SHALL include `timeout: true` flag

---

### Requirement: Directory Listing
The system SHALL allow Clients to list directory contents within allowed mounts for the filesystem browser.

#### Scenario: List directory contents
- **WHEN** Client sends `FS_LIST_DIR` message with `path` parameter
- **AND** path is within an allowed mount
- **THEN** Worker SHALL respond with `FS_LIST_RESPONSE`
- **AND** response SHALL include array of entries with `name`, `type`, `size`, `modified` fields
- **AND** entries SHALL be sorted alphabetically with directories first

#### Scenario: Result pagination
- **WHEN** directory contains more than 20 items
- **THEN** Worker SHALL return first 20 items
- **AND** response SHALL include `total_count` with actual count
- **AND** response SHALL include `has_more: true`
- **AND** Client MAY request next page with `offset` parameter

#### Scenario: Metadata only
- **WHEN** Worker responds to `FS_LIST_DIR`
- **THEN** response SHALL contain only metadata (name, type, size, modified)
- **AND** response SHALL NOT contain file contents

#### Scenario: Path outside allowed mounts
- **WHEN** Client sends `FS_LIST_DIR` with path outside configured mounts
- **THEN** Worker SHALL respond with `FS_ERROR` message
- **AND** error SHALL have code `ACCESS_DENIED`

#### Scenario: Path traversal attempt
- **WHEN** Client sends path containing `..` segments
- **THEN** Worker SHALL canonicalize path before checking
- **AND** Worker SHALL reject if canonicalized path is outside mounts

---

### Requirement: Security Boundaries
The system SHALL enforce strict security boundaries for filesystem operations.

#### Scenario: Read-only operations
- **WHEN** Worker handles any `FS_*` message
- **THEN** Worker SHALL only perform read operations
- **AND** Worker SHALL NOT modify, create, or delete any files

#### Scenario: Symlink handling
- **WHEN** Worker encounters a symbolic link during listing or search
- **THEN** Worker SHALL resolve the link's target
- **AND** Worker SHALL only include the entry if target is within allowed mounts

#### Scenario: Permission errors
- **WHEN** Worker cannot read a directory due to filesystem permissions
- **THEN** Worker SHALL skip that directory silently
- **AND** Worker SHALL NOT expose permission error details to Client
- **AND** Worker SHALL log the error locally
