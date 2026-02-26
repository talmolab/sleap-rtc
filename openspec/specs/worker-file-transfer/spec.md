# worker-file-transfer Specification

## Purpose
TBD - created by archiving change refactor-worker-modular. Update Purpose after archive.
## Requirements
### Requirement: File Transfer to Client

The file manager SHALL send files to client via RTC data channel with chunked transfer and flow control.

#### Scenario: Send model file to client

- **WHEN** training completes with model file
- **THEN** file manager SHALL send "FILE_META::{name}:{size}:{output_dir}" message
- **AND** send file in 32KB chunks
- **AND** wait when channel bufferedAmount exceeds 16MB
- **AND** send "END_OF_FILE" marker when complete

#### Scenario: Data channel not open

- **WHEN** attempting to send file but channel readyState is not "open"
- **THEN** file manager SHALL log error
- **AND** return without attempting transfer

### Requirement: File Compression

The file manager SHALL compress training results into zip archives for efficient transfer.

#### Scenario: Zip training results

- **WHEN** training completes with models in output directory
- **THEN** file manager SHALL create zip archive with all contents
- **AND** save archive with "trained_{original_name}" naming
- **AND** return path to zipped file

#### Scenario: Directory does not exist

- **WHEN** attempting to zip non-existent directory
- **THEN** file manager SHALL log error
- **AND** return without creating archive

### Requirement: File Decompression

The file manager SHALL extract zip archives received from client.

#### Scenario: Unzip training package

- **WHEN** client sends zip file via RTC
- **THEN** file manager SHALL extract to save directory
- **AND** set unzipped_dir attribute to extracted path
- **AND** remove .zip extension from directory name

#### Scenario: Zip extraction failure

- **WHEN** zip extraction raises exception
- **THEN** file manager SHALL log error with details
- **AND** NOT proceed with job execution

### Requirement: Shared Storage Path Validation

The file manager SHALL validate shared storage paths for security and correctness before processing jobs.

#### Scenario: Valid input path within root

- **WHEN** client sends relative input path "jobs/job_abc/training.zip"
- **THEN** file manager SHALL convert to absolute path
- **AND** validate path is within shared_storage_root
- **AND** verify file exists
- **AND** send PATH_VALIDATED confirmation

#### Scenario: Path outside shared root

- **WHEN** client sends path with "../../../etc/passwd" traversal
- **THEN** file manager SHALL reject with PathValidationError
- **AND** send PATH_ERROR message
- **AND** NOT process job

#### Scenario: Input file does not exist

- **WHEN** absolute path validation succeeds but file does not exist
- **THEN** file manager SHALL send PATH_ERROR message
- **AND** NOT process job

### Requirement: Shared Storage Output Directory Creation

The file manager SHALL create and validate output directories in shared storage for job results.

#### Scenario: Create output directory

- **WHEN** client sends relative output path "jobs/job_abc/models"
- **THEN** file manager SHALL convert to absolute path
- **AND** validate path is within shared_storage_root
- **AND** create directory with safe_mkdir
- **AND** send PATH_VALIDATED confirmation

#### Scenario: Output path validation failure

- **WHEN** output path contains invalid characters or traversal
- **THEN** file manager SHALL reject with PathValidationError
- **AND** send PATH_ERROR message

### Requirement: Shared Storage Configuration

The file manager SHALL initialize shared storage root from configuration or CLI override.

#### Scenario: Shared storage configured via environment

- **WHEN** SLEAP_RTC_SHARED_STORAGE_ROOT environment variable is set
- **THEN** file manager SHALL use configured path as shared_storage_root
- **AND** create jobs directory at {root}/jobs
- **AND** log "Worker shared storage enabled"

#### Scenario: Shared storage not configured

- **WHEN** no shared storage configuration provided
- **THEN** file manager SHALL set shared_storage_root to None
- **AND** log "Worker shared storage not configured, will use RTC transfer"

#### Scenario: Shared storage configuration error

- **WHEN** shared storage path is invalid or inaccessible
- **THEN** file manager SHALL log error with details
- **AND** fall back to RTC transfer mode

### Requirement: Client-to-Worker Upload Receive Handler

The `FileManager` SHALL accept incoming file uploads from clients via the RTC data
channel, writing chunks to disk and reporting progress.

#### Scenario: Start upload session
- **WHEN** worker receives `FILE_UPLOAD_START::{filename}::{total_bytes}::{dest_dir}::{create_subdir}`
- **AND** `dest_dir` resolves within a configured mount
- **THEN** worker creates the destination directory (and `sleap-rtc-downloads/`
  subfolder if `create_subdir` is `1`)
- **AND** opens a write handle for the incoming file
- **AND** replies `FILE_UPLOAD_READY`

#### Scenario: Receive and write chunks
- **WHEN** worker receives binary data chunks during an active upload session
- **THEN** worker appends each chunk to the open write handle
- **AND** sends `FILE_UPLOAD_PROGRESS::{bytes_received}::{total_bytes}` at most
  every 500 ms

#### Scenario: Finalise upload
- **WHEN** worker receives `FILE_UPLOAD_END`
- **THEN** worker closes the write handle and flushes to disk
- **AND** verifies the written file size matches `{total_bytes}`
- **AND** sends `FILE_UPLOAD_COMPLETE::{absolute_path}`

#### Scenario: Reject destination outside mounts
- **WHEN** worker receives `FILE_UPLOAD_START` with a `dest_dir` that resolves
  outside all configured mounts
- **THEN** worker sends `FILE_UPLOAD_ERROR::Destination outside configured mounts`
- **AND** no file is written to disk

#### Scenario: Disk write failure
- **WHEN** an I/O error occurs while writing a chunk
- **THEN** worker sends `FILE_UPLOAD_ERROR::{reason}`
- **AND** worker deletes the partial file

### Requirement: Upload Cache Index

The `FileManager` SHALL maintain an in-memory index of uploaded files keyed by
SHA-256 so repeat uploads of unchanged files can be skipped.

#### Scenario: Cache hit
- **WHEN** worker receives `FILE_UPLOAD_CHECK::{sha256}::{filename}`
- **AND** the index contains an entry for `{sha256}` pointing to a file that
  still exists on disk
- **THEN** worker replies `FILE_UPLOAD_CACHE_HIT::{absolute_path}`

#### Scenario: Cache miss
- **WHEN** worker receives `FILE_UPLOAD_CHECK::{sha256}::{filename}`
- **AND** no matching entry exists in the index (or the cached file no longer
  exists on disk)
- **THEN** worker replies `FILE_UPLOAD_READY`

#### Scenario: Index updated after successful upload
- **WHEN** an upload completes successfully
- **THEN** the SHA-256 and absolute path are stored in the index
- **AND** subsequent checks for the same hash hit the cache

