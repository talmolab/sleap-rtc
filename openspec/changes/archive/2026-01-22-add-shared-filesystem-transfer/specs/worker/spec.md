# Worker Specification

## ADDED Requirements

### Requirement: Shared Storage Initialization

The RTCWorkerClient SHALL initialize shared storage configuration on startup.

#### Scenario: Detect shared storage on initialization
- **WHEN** RTCWorkerClient is instantiated
- **THEN** Worker SHALL attempt to detect shared storage mount point
- **AND** Worker SHALL create `FilesystemAdapter` instance if shared storage detected

#### Scenario: Store shared storage configuration
- **WHEN** shared storage is detected
- **THEN** Worker SHALL store `shared_storage_root` as Path attribute
- **AND** Worker SHALL store `fs_adapter` (FilesystemAdapter) as attribute

#### Scenario: Container-specific mount point detection
- **WHEN** Worker runs in RunAI/Vast.ai container
- **THEN** Worker SHALL detect mount point `/home/jovyan/vast/amick`
- **OR** Worker SHALL use `SHARED_STORAGE_ROOT` environment variable if set

### Requirement: Shared Path Message Handling

The RTCWorkerClient SHALL handle incoming shared storage path messages.

#### Scenario: Receive shared input path
- **WHEN** Worker receives `SHARED_INPUT_PATH::{relative_path}` message
- **THEN** Worker SHALL parse relative path from message
- **AND** Worker SHALL resolve to absolute path: `{shared_root}/{relative_path}`
- **AND** Worker SHALL validate the path

#### Scenario: Receive shared output path
- **WHEN** Worker receives `SHARED_OUTPUT_PATH::{relative_path}` message
- **THEN** Worker SHALL parse relative path from message
- **AND** Worker SHALL resolve to absolute path: `{shared_root}/{relative_path}`
- **AND** Worker SHALL create output directory if it doesn't exist

### Requirement: Path Validation and Security

The RTCWorkerClient SHALL validate all received paths before accessing files.

#### Scenario: Validate path exists
- **WHEN** Worker resolves shared input path
- **THEN** Worker SHALL check if path exists using `fs_adapter.exists()`
- **AND** Worker SHALL send `PATH_VALIDATED::input` if exists
- **OR** Worker SHALL send `PATH_ERROR::Input path does not exist: {path}` if not found

#### Scenario: Validate path within shared root
- **WHEN** Worker resolves any received path
- **THEN** Worker SHALL call `validate_path_in_root(path, shared_root)`
- **AND** Worker SHALL verify `resolved_path.relative_to(shared_root)` succeeds
- **AND** Worker SHALL reject paths that escape shared root

#### Scenario: Reject path traversal attacks
- **WHEN** Worker receives path like `../../etc/passwd`
- **THEN** Worker SHALL detect path escapes shared root
- **AND** Worker SHALL send `PATH_ERROR::Path outside shared storage: {path}`
- **AND** Worker SHALL log security violation

#### Scenario: Resolve symlinks before validation
- **WHEN** Worker validates path
- **THEN** Worker SHALL resolve symlinks using `Path.resolve()`
- **AND** Worker SHALL validate resolved absolute path, not the symlink

### Requirement: Direct File Access

The RTCWorkerClient SHALL access files directly from shared storage.

#### Scenario: Read input file directly
- **WHEN** Worker receives validated `SHARED_INPUT_PATH`
- **THEN** Worker SHALL read file contents from absolute path
- **AND** Worker SHALL not receive file data over RTC data channel

#### Scenario: Process file in place
- **WHEN** Worker needs to extract training package ZIP
- **THEN** Worker SHALL extract to temporary directory or shared storage subdirectory
- **AND** Worker SHALL use extracted files for training

#### Scenario: Write results to shared output
- **WHEN** Worker completes training job
- **THEN** Worker SHALL write result files to shared output path
- **AND** Worker SHALL ensure files are flushed to disk (fsync)

### Requirement: Job Completion Notification

The RTCWorkerClient SHALL notify Client when job is complete with output location.

#### Scenario: Send completion with relative output path
- **WHEN** Worker finishes processing and writes results
- **THEN** Worker SHALL convert absolute output path to relative path
- **AND** Worker SHALL send `JOB_COMPLETE::{job_id}::{relative_output_path}` message

#### Scenario: Include result metadata
- **WHEN** Worker sends job completion
- **THEN** Worker MAY include result file count and total size in message
- **AND** format SHALL be `JOB_COMPLETE::{job_id}::{relative_path}::{file_count}::{total_mb}`

### Requirement: Shared Storage Error Handling

The RTCWorkerClient SHALL handle shared storage errors and report them to Client.

#### Scenario: File not found error
- **WHEN** Worker cannot find file at received path
- **THEN** Worker SHALL send `PATH_ERROR::File not found: {path}`
- **AND** Worker SHALL log error with full absolute path

#### Scenario: Permission denied error
- **WHEN** Worker cannot read file due to permissions
- **THEN** Worker SHALL send `PATH_ERROR::Permission denied: {path}`
- **AND** Worker SHALL log permission error

#### Scenario: Disk space error during write
- **WHEN** Worker cannot write results due to insufficient disk space
- **THEN** Worker SHALL send `JOB_FAILED::Disk space exhausted on shared storage`
- **AND** Worker SHALL attempt to clean up partial files

#### Scenario: Corrupted file detection
- **WHEN** Worker reads file but contents are corrupted (e.g., ZIP extraction fails)
- **THEN** Worker SHALL send `PATH_ERROR::File corrupted or invalid format: {path}`
- **AND** Worker SHALL request Client retry with RTC transfer

### Requirement: Backward Compatibility

The RTCWorkerClient SHALL maintain support for existing RTC chunked transfer.

#### Scenario: Receive RTC transfer messages
- **WHEN** Worker receives `FILE_META::` message (existing protocol)
- **THEN** Worker SHALL process using existing chunked transfer logic
- **AND** Worker SHALL not attempt shared storage path resolution

#### Scenario: Mixed transfer modes in same session
- **WHEN** Worker handles multiple jobs in same session
- **THEN** Worker SHALL support shared storage for some jobs and RTC transfer for others
- **AND** Worker SHALL select transfer mode based on received message type

### Requirement: Performance Monitoring

The RTCWorkerClient SHALL log performance metrics for shared storage operations.

#### Scenario: Log file access time
- **WHEN** Worker accesses file from shared storage
- **THEN** Worker SHALL log time taken to read file
- **AND** log SHALL include file size for performance analysis

#### Scenario: Log validation time
- **WHEN** Worker validates received path
- **THEN** Worker SHALL log validation duration
- **AND** Worker SHALL warn if validation takes longer than 1 second
