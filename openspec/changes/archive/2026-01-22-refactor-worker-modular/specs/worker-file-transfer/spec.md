# Worker File Transfer Specification

## ADDED Requirements

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
