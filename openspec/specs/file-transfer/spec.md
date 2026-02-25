# file-transfer Specification

## Purpose
TBD - created by archiving change add-shared-filesystem-transfer. Update Purpose after archive.
## Requirements
### Requirement: Shared Filesystem Detection

The system SHALL automatically detect when Client and Worker have access to shared filesystem storage.

#### Scenario: Shared storage available on both sides
- **WHEN** Client and Worker both have access to `/home/jovyan/vast/amick` (or similar shared mount)
- **THEN** the system SHALL detect and use shared filesystem transfer instead of RTC transfer

#### Scenario: Shared storage not available
- **WHEN** Client or Worker cannot access shared filesystem
- **THEN** the system SHALL fall back to RTC chunked transfer

#### Scenario: Environment variable override
- **WHEN** `SHARED_STORAGE_ROOT` environment variable is set
- **THEN** the system SHALL use that path as the shared storage mount point

### Requirement: Mount Point Configuration

The system SHALL support different mount points for the same shared storage on Client and Worker.

#### Scenario: Different mount paths
- **WHEN** Client mounts shared storage at `/Volumes/talmo/amick`
- **AND** Worker mounts same storage at `/home/jovyan/vast/amick`
- **THEN** the system SHALL translate paths correctly using relative path resolution

#### Scenario: Auto-detection of mount points
- **WHEN** no explicit configuration is provided
- **THEN** the system SHALL attempt to auto-detect shared storage from known mount point patterns:
  - `/home/jovyan/vast/amick` (Vast.ai/JupyterHub)
  - `/Volumes/talmo/amick` (MacBook NFS mount)
  - `/workspace/shared` (Generic Kubernetes)
  - `/shared`, `/mnt/shared`, `/data/shared` (Generic)

### Requirement: File Copy to Shared Storage

The Client SHALL copy training packages to shared storage before notifying the Worker.

#### Scenario: Copy local file to shared storage
- **WHEN** Client has file at `/Users/amick/Downloads/training.zip`
- **AND** shared storage root is `/Volumes/talmo/amick`
- **THEN** Client SHALL copy file to `/Volumes/talmo/amick/jobs/{job_id}/training.zip`

#### Scenario: Create unique job directories
- **WHEN** Client initiates a new training job
- **THEN** Client SHALL create a unique job directory using format `jobs/{job_id}/`
- **AND** `{job_id}` SHALL be a unique identifier (e.g., `job_abc123`)

#### Scenario: Preserve file metadata
- **WHEN** copying files to shared storage
- **THEN** the system SHALL preserve file timestamps and permissions using `shutil.copy2`

### Requirement: Relative Path Communication

The system SHALL send relative paths over RTC data channel instead of absolute paths.

#### Scenario: Send relative input path
- **WHEN** Client copies file to `/Volumes/talmo/amick/jobs/job_123/training.zip`
- **THEN** Client SHALL send message `SHARED_INPUT_PATH::jobs/job_123/training.zip`
- **AND** Worker SHALL resolve to `/home/jovyan/vast/amick/jobs/job_123/training.zip`

#### Scenario: Send relative output path
- **WHEN** Client specifies output directory
- **THEN** Client SHALL send message `SHARED_OUTPUT_PATH::jobs/job_123/output`
- **AND** Worker SHALL resolve to `/home/jovyan/vast/amick/jobs/job_123/output`

### Requirement: Path Validation

The Worker SHALL validate all received paths before accessing files.

#### Scenario: Validate path exists
- **WHEN** Worker receives `SHARED_INPUT_PATH::jobs/job_123/training.zip`
- **AND** resolved path `/home/jovyan/vast/amick/jobs/job_123/training.zip` exists
- **THEN** Worker SHALL send `PATH_VALIDATED::input`

#### Scenario: Path does not exist
- **WHEN** Worker receives path that does not exist
- **THEN** Worker SHALL send `PATH_ERROR::Input path does not exist: {path}`
- **AND** Client SHALL fall back to RTC transfer

#### Scenario: Security - path traversal prevention
- **WHEN** Worker receives path containing `..` or resolving outside shared root
- **THEN** Worker SHALL reject the path
- **AND** Worker SHALL send `PATH_ERROR::Path outside shared storage: {path}`

#### Scenario: Security - validate within shared root
- **WHEN** Worker resolves received path
- **THEN** Worker SHALL verify resolved path is within shared storage root using `Path.resolve().relative_to(root)`
- **AND** Worker SHALL reject paths that escape shared root

### Requirement: Filesystem Abstraction with fsspec

The system SHALL use fsspec library to abstract filesystem operations.

#### Scenario: Initialize filesystem adapter
- **WHEN** Client or Worker initializes filesystem operations
- **THEN** system SHALL create `FilesystemAdapter` instance wrapping fsspec
- **AND** default protocol SHALL be `file://` for local/NFS filesystems

#### Scenario: Check file exists
- **WHEN** system needs to verify file existence
- **THEN** system SHALL use `fs.exists(path)` method

#### Scenario: Copy files
- **WHEN** Client copies file to shared storage
- **THEN** system SHALL use `fs.copy(src, dst)` method

#### Scenario: Create directories
- **WHEN** system needs to create job directory
- **THEN** system SHALL use `fs.mkdir(path, create_parents=True)` method

#### Scenario: Get file metadata
- **WHEN** system needs file size or modification time
- **THEN** system SHALL use `fs.info(path)` method

### Requirement: Direct File Access

The Worker SHALL read files directly from shared storage without transferring over RTC.

#### Scenario: Read input file from shared storage
- **WHEN** Worker receives validated `SHARED_INPUT_PATH`
- **THEN** Worker SHALL read file directly from resolved absolute path
- **AND** no data transfer over RTC data channel SHALL occur

#### Scenario: Write output to shared storage
- **WHEN** Worker completes training job
- **THEN** Worker SHALL write results directly to shared output path
- **AND** Worker SHALL send `JOB_COMPLETE::{job_id}::{relative_output_path}`

#### Scenario: Client retrieves results
- **WHEN** Client receives `JOB_COMPLETE` message with output path
- **THEN** Client SHALL resolve relative path to local absolute path
- **AND** Client SHALL access results directly from shared storage

### Requirement: Fallback to RTC Transfer

The system SHALL fall back to RTC chunked transfer when shared storage is unavailable or fails.

#### Scenario: Shared storage not detected
- **WHEN** Client cannot detect shared storage mount point
- **THEN** Client SHALL use existing RTC chunked transfer mechanism
- **AND** Client SHALL log "Shared storage not detected, using RTC transfer"

#### Scenario: Path validation fails
- **WHEN** Worker sends `PATH_ERROR` response
- **THEN** Client SHALL automatically retry using RTC chunked transfer
- **AND** Client SHALL log "Shared storage failed, falling back to RTC transfer"

#### Scenario: File copy fails
- **WHEN** Client cannot copy file to shared storage (permissions, disk space)
- **THEN** Client SHALL fall back to RTC transfer
- **AND** Client SHALL log error reason

### Requirement: Performance Optimization

The system SHALL minimize file transfer time when using shared storage.

#### Scenario: Large file transfer time
- **WHEN** Client sends 5GB training package via shared storage
- **THEN** total transfer time SHALL be less than 2 minutes (copy + path send)
- **AND** this SHALL be significantly faster than RTC transfer (~20 minutes)

#### Scenario: Instant worker access
- **WHEN** Worker receives `SHARED_INPUT_PATH` and validates successfully
- **THEN** Worker SHALL have immediate access to file contents
- **AND** no additional download time SHALL be required

### Requirement: Message Protocol Extension

The system SHALL extend RTC message protocol with shared storage path messages.

#### Scenario: New message types
- **WHEN** system uses shared storage transfer
- **THEN** system SHALL use following message types:
  - `SHARED_INPUT_PATH::{relative_path}` - Input file location
  - `SHARED_OUTPUT_PATH::{relative_path}` - Output directory location
  - `PATH_VALIDATED::input|output` - Path accessible confirmation
  - `PATH_ERROR::{error_message}` - Path validation failure

#### Scenario: Backward compatibility
- **WHEN** Worker receives existing RTC transfer messages (`FILE_META::`, etc.)
- **THEN** Worker SHALL process using existing chunked transfer logic
- **AND** new message types SHALL not interfere with existing protocol

### Requirement: Error Handling and Logging

The system SHALL provide clear error messages and logging for debugging.

#### Scenario: Log mount point detection
- **WHEN** system initializes shared storage configuration
- **THEN** system SHALL log detected or configured mount point
- **AND** log message SHALL indicate whether auto-detected or from environment variable

#### Scenario: Log transfer method selection
- **WHEN** Client chooses transfer method
- **THEN** Client SHALL log "Using shared storage transfer" or "Using RTC transfer"

#### Scenario: Clear error messages
- **WHEN** shared storage operation fails
- **THEN** system SHALL log specific error with context:
  - "Mount point not found: {path}"
  - "Permission denied: {path}"
  - "Disk space exhausted on {mount}"
  - "File not found: {path}"

#### Scenario: Path validation errors
- **WHEN** Worker rejects a path
- **THEN** Worker SHALL include reason in `PATH_ERROR` message
- **AND** Client SHALL log the rejection reason for debugging

