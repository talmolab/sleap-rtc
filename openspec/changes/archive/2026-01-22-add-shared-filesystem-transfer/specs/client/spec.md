# Client Specification

## ADDED Requirements

### Requirement: Shared Storage Initialization

The RTCClient SHALL initialize shared storage configuration on startup.

#### Scenario: Detect shared storage on initialization
- **WHEN** RTCClient is instantiated
- **THEN** Client SHALL attempt to detect shared storage mount point
- **AND** Client SHALL create `FilesystemAdapter` instance if shared storage detected

#### Scenario: Store shared storage configuration
- **WHEN** shared storage is detected
- **THEN** Client SHALL store `shared_storage_root` as Path attribute
- **AND** Client SHALL store `fs_adapter` (FilesystemAdapter) as attribute

#### Scenario: No shared storage detected
- **WHEN** no shared storage mount point is found
- **THEN** Client SHALL set `shared_storage_root = None`
- **AND** Client SHALL use RTC transfer for all file operations

### Requirement: Transfer Method Selection

The RTCClient SHALL automatically select the optimal file transfer method.

#### Scenario: Choose shared storage when available
- **WHEN** Client has `shared_storage_root` configured
- **AND** file size is greater than 100MB
- **THEN** Client SHALL use `send_file_via_shared_storage()` method

#### Scenario: Choose RTC transfer when shared storage unavailable
- **WHEN** Client has `shared_storage_root = None`
- **THEN** Client SHALL use existing `send_client_file()` RTC transfer method

#### Scenario: Fallback on shared storage failure
- **WHEN** shared storage transfer fails (copy error, path error)
- **THEN** Client SHALL automatically retry using RTC transfer
- **AND** Client SHALL log the failure reason

### Requirement: Shared Storage File Sending

The RTCClient SHALL implement shared storage file transfer.

#### Scenario: Create job directory
- **WHEN** Client sends file via shared storage
- **THEN** Client SHALL create unique job directory: `{shared_root}/jobs/{job_id}/`
- **AND** `{job_id}` SHALL be generated using UUID format `job_{uuid[:8]}`

#### Scenario: Copy file to shared storage
- **WHEN** Client has local file at arbitrary path
- **THEN** Client SHALL copy file to `{shared_root}/jobs/{job_id}/{filename}`
- **AND** Client SHALL use `fs_adapter.copy()` method

#### Scenario: Send relative paths over RTC
- **WHEN** file is successfully copied to shared storage
- **THEN** Client SHALL compute relative path from `shared_storage_root`
- **AND** Client SHALL send `SHARED_INPUT_PATH::{relative_path}` message
- **AND** Client SHALL send `SHARED_OUTPUT_PATH::{relative_output_path}` message

#### Scenario: Wait for path validation
- **WHEN** Client sends shared paths
- **THEN** Client SHALL wait for `PATH_VALIDATED::input` and `PATH_VALIDATED::output` responses
- **OR** Client SHALL handle `PATH_ERROR` and fallback to RTC

### Requirement: Result Retrieval from Shared Storage

The RTCClient SHALL retrieve results directly from shared storage.

#### Scenario: Receive job completion with output path
- **WHEN** Client receives `JOB_COMPLETE::{job_id}::{relative_output_path}` message
- **THEN** Client SHALL resolve relative path to absolute path using `shared_storage_root`
- **AND** Client SHALL access result files directly from shared storage

#### Scenario: List result files
- **WHEN** Client accesses output directory
- **THEN** Client SHALL use `fs_adapter.ls()` to list files
- **AND** Client SHALL report file names and sizes to user

#### Scenario: Optional local copy
- **WHEN** user wants results copied to local machine
- **THEN** Client SHALL provide option to copy from shared storage to local path
- **AND** Client SHALL use `fs_adapter.copy()` for the operation

### Requirement: CLI Integration

The Client CLI SHALL support shared storage configuration.

#### Scenario: Optional shared storage root flag
- **WHEN** user runs `sleap-rtc client-train`
- **THEN** CLI SHALL accept `--shared-storage-root` optional flag
- **AND** flag SHALL override auto-detection

#### Scenario: Display transfer method in output
- **WHEN** Client starts file transfer
- **THEN** CLI SHALL display which method is being used:
  - "Using shared storage transfer ({mount_point})"
  - "Using RTC transfer (shared storage not available)"

### Requirement: Error Handling

The RTCClient SHALL handle shared storage errors gracefully.

#### Scenario: Copy failure due to permissions
- **WHEN** Client cannot write to shared storage (permission denied)
- **THEN** Client SHALL log error with details
- **AND** Client SHALL fall back to RTC transfer

#### Scenario: Disk space exhausted
- **WHEN** Client attempts to copy large file but shared storage is full
- **THEN** Client SHALL detect disk space error
- **AND** Client SHALL fall back to RTC transfer
- **AND** Client SHALL warn user about disk space issue

#### Scenario: Mount point disappears
- **WHEN** shared storage mount point becomes unavailable during operation
- **THEN** Client SHALL detect the error
- **AND** Client SHALL fall back to RTC transfer for subsequent operations
