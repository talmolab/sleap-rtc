# Model Transfer Protocol Specification

## ADDED Requirements

### Requirement: Registry Query Protocol
The system SHALL provide WebRTC message-based queries for client to query worker model registries.

#### Scenario: List models on worker
- **WHEN** client sends registry_query message with command="list_models"
- **THEN** the worker SHALL query its local registry
- **AND** the worker SHALL apply any filters provided (status, model_type, etc.)
- **AND** the worker SHALL send registry_response message with matching models
- **AND** the response SHALL include model ID, type, alias, status, metrics, and paths

#### Scenario: Get model info from worker
- **WHEN** client sends registry_query message with command="get_model_info" and model_id
- **THEN** the worker SHALL retrieve the model entry from its registry
- **AND** if model exists, the worker SHALL send complete model metadata
- **AND** if model not found, the worker SHALL send error response with status=404
- **AND** the response time SHALL be under 1 second for typical registries

#### Scenario: Check model exists on worker
- **WHEN** client sends registry_query message with command="check_model_exists"
- **THEN** the worker SHALL check if model_id or alias exists in registry
- **AND** the worker SHALL respond with boolean exists=true/false
- **AND** the worker SHALL include checkpoint file validation status
- **AND** the response SHALL complete within 500ms

#### Scenario: Query timeout
- **WHEN** client sends registry_query but receives no response within timeout
- **THEN** the client SHALL wait for default timeout of 10 seconds
- **AND** the client SHALL retry once after timeout
- **AND** if second attempt fails, the client SHALL display error and abort operation
- **AND** the client SHALL log timeout event with worker connection details

### Requirement: Model Push Protocol (Client to Worker)
The system SHALL enable clients to upload local models to workers via WebRTC data channels.

#### Scenario: Initiate model push
- **WHEN** client initiates push of a local model to worker
- **THEN** the client SHALL send model_transfer message with:
  - command="push"
  - model_id
  - model_type
  - alias (if present)
  - file manifest (filenames, sizes, checksums)
- **AND** the worker SHALL validate it has sufficient disk space
- **AND** the worker SHALL create temporary directory for incoming files
- **AND** the worker SHALL respond with status="ready" or error if cannot accept

#### Scenario: Stream model files to worker
- **WHEN** worker accepts push request
- **THEN** the client SHALL chunk each file using CHUNK_SIZE (64KB default)
- **AND** the client SHALL send model_file_chunk messages for each chunk:
  - model_id
  - filename (relative path)
  - chunk_index (0-based)
  - total_chunks
  - data (base64-encoded bytes)
- **AND** the client SHALL include MD5 checksum in final chunk message
- **AND** the client SHALL display progress bar showing percentage and transfer rate

#### Scenario: Worker receives and validates chunks
- **WHEN** worker receives model_file_chunk messages
- **THEN** the worker SHALL reassemble chunks into complete files
- **AND** the worker SHALL write to temporary directory
- **AND** the worker SHALL validate checksums after each file completes
- **AND** if checksum mismatch, the worker SHALL send error and request retransmission
- **AND** the worker SHALL acknowledge successful file completion

#### Scenario: Complete model push
- **WHEN** all files transferred successfully
- **THEN** the worker SHALL move files from temp directory to final location
- **AND** the worker SHALL use directory naming: models/{model_type}_{model_id}/
- **AND** the worker SHALL register model in worker registry with source="client-upload"
- **AND** the worker SHALL send model_transfer_complete message with status="success"
- **AND** the worker SHALL clean up temporary directory
- **AND** the client SHALL update its registry with on_worker=true

#### Scenario: Push failure mid-transfer
- **WHEN** transfer fails due to network error or cancellation
- **THEN** the worker SHALL clean up partial files from temporary directory
- **AND** the worker SHALL NOT register incomplete model in registry
- **AND** the worker SHALL send model_transfer_complete with status="failed" and reason
- **AND** the client SHALL log error and offer retry
- **AND** the client SHALL preserve local model unchanged

### Requirement: Model Pull Protocol (Worker to Client)
The system SHALL enable clients to download worker models to local machine via WebRTC data channels.

#### Scenario: Initiate model pull
- **WHEN** client initiates pull of a worker model
- **THEN** the client SHALL send model_transfer message with:
  - command="pull"
  - model_id or alias
- **AND** the worker SHALL resolve identifier to model entry
- **AND** the worker SHALL validate checkpoint files exist on disk
- **AND** the worker SHALL generate file manifest with sizes and checksums
- **AND** the worker SHALL send manifest to client

#### Scenario: Client prepares for download
- **WHEN** client receives pull manifest from worker
- **THEN** the client SHALL validate it has sufficient local disk space
- **AND** the client SHALL create temporary directory for incoming files
- **AND** the client SHALL send ready acknowledgment to worker
- **AND** if insufficient space, the client SHALL abort with error message

#### Scenario: Worker streams model files to client
- **WHEN** client confirms ready for download
- **THEN** the worker SHALL chunk each file using CHUNK_SIZE
- **AND** the worker SHALL send model_file_chunk messages sequentially
- **AND** the worker SHALL include checksums for validation
- **AND** the worker SHALL implement flow control to avoid overwhelming client
- **AND** the client SHALL display progress bar with estimated time remaining

#### Scenario: Client receives and validates chunks
- **WHEN** client receives model_file_chunk messages
- **THEN** the client SHALL reassemble chunks into complete files
- **AND** the client SHALL write to temporary directory under ~/.sleap-rtc/models/
- **AND** the client SHALL validate checksums after each file completes
- **AND** if checksum mismatch, the client SHALL request retransmission
- **AND** the client SHALL acknowledge successful file completion

#### Scenario: Complete model pull
- **WHEN** all files transferred successfully
- **THEN** the client SHALL move files from temp to final location
- **AND** the client SHALL use directory naming: ~/.sleap-rtc/models/{model_type}_{model_id}/
- **AND** the client SHALL register model in client registry with source="worker-pull"
- **AND** the client SHALL set on_worker=true and worker_path
- **AND** the client SHALL send acknowledgment to worker
- **AND** the client SHALL display success message with local path

#### Scenario: Pull failure mid-transfer
- **WHEN** transfer fails due to network error or cancellation
- **THEN** the client SHALL clean up partial files from temporary directory
- **AND** the client SHALL NOT register incomplete model in registry
- **AND** the client SHALL log error and offer retry option
- **AND** the worker SHALL clean up any temporary state

### Requirement: Transfer Resumption
The system SHALL support resuming interrupted transfers to avoid re-transferring completed data.

#### Scenario: Track completed chunks
- **WHEN** transfer is in progress
- **THEN** both sender and receiver SHALL track which chunks completed
- **AND** the receiver SHALL maintain a bitmap of received chunks
- **AND** the receiver SHALL persist chunk tracking to disk periodically

#### Scenario: Resume interrupted transfer
- **WHEN** transfer is interrupted and user retries
- **THEN** the receiver SHALL load chunk tracking from disk
- **AND** the receiver SHALL send resume message with completed chunk indices
- **AND** the sender SHALL skip already-transferred chunks
- **AND** the sender SHALL resume from first missing chunk
- **AND** progress bar SHALL reflect already-completed portion

#### Scenario: Stale resume state
- **WHEN** resuming transfer but source files modified
- **THEN** the system SHALL detect checksum mismatch
- **AND** the system SHALL invalidate resume state
- **AND** the system SHALL restart transfer from beginning
- **AND** the system SHALL notify user of restart reason

### Requirement: Transfer Performance and Reliability
The system SHALL optimize transfers for performance while maintaining reliability.

#### Scenario: Adaptive chunk sizing
- **WHEN** beginning a transfer
- **THEN** the system SHALL start with default CHUNK_SIZE of 64KB
- **AND** the system SHALL monitor transfer rate and latency
- **AND** if latency is low (<50ms), the system MAY increase chunk size up to 256KB
- **AND** if packet loss detected, the system SHALL decrease chunk size to 32KB
- **AND** adjustments SHALL be logged for diagnostics

#### Scenario: Progress reporting
- **WHEN** transfer is in progress
- **THEN** the system SHALL update progress bar at least once per second
- **AND** the progress bar SHALL show: percentage, bytes transferred, total bytes, transfer rate
- **AND** the system SHALL estimate time remaining based on recent transfer rate
- **AND** for large transfers (>100MB), the system SHALL show per-file progress

#### Scenario: Bandwidth throttling
- **WHEN** user specifies --limit flag with transfer command
- **THEN** the system SHALL limit transfer rate to specified bytes per second
- **AND** the system SHALL use token bucket algorithm for smooth rate limiting
- **AND** the system SHALL pause between chunks to achieve target rate
- **AND** throttling SHALL NOT apply to small config files (<1MB)

#### Scenario: Checksum validation
- **WHEN** file transfer completes
- **THEN** the receiver SHALL calculate MD5 checksum of received file
- **AND** the receiver SHALL compare with checksum from manifest
- **AND** if match, the receiver SHALL mark file as complete
- **AND** if mismatch, the receiver SHALL request retransmission of entire file
- **AND** the receiver SHALL retry up to 3 times before aborting

### Requirement: Model Packaging
The system SHALL package models with all required files for complete transfer.

#### Scenario: Create model package manifest
- **WHEN** preparing a model for transfer
- **THEN** the system SHALL include all checkpoint files (*.ckpt, *.h5)
- **AND** the system SHALL include training_config.yaml if present
- **AND** the system SHALL include model metadata from registry
- **AND** the system SHALL calculate checksums for each file
- **AND** the manifest SHALL include total size and file count

#### Scenario: Package includes required files only
- **WHEN** packaging a model
- **THEN** the system SHALL include: best.ckpt (required)
- **AND** the system SHALL include: training_config.yaml (if exists)
- **AND** the system SHALL include: last.ckpt (optional, if exists)
- **AND** the system SHALL exclude: logs, temporary files, checkpoints other than best/last
- **AND** the system SHALL validate minimum required files present

#### Scenario: Unpackage on receive
- **WHEN** receiver completes transfer
- **THEN** the system SHALL extract all files to target directory
- **AND** the system SHALL preserve relative paths from manifest
- **AND** the system SHALL set appropriate file permissions
- **AND** the system SHALL validate directory structure matches expected layout
- **AND** if any required file missing, the system SHALL mark transfer as failed

### Requirement: Transfer Security
The system SHALL ensure model transfers are secure and validated.

#### Scenario: Validate transfer source
- **WHEN** accepting a model transfer
- **THEN** the receiver SHALL validate the connection is authenticated
- **AND** the receiver SHALL check the peer ID matches expected session
- **AND** if authentication fails, the receiver SHALL reject transfer immediately
- **AND** rejection SHALL be logged with peer information

#### Scenario: Prevent malicious files
- **WHEN** receiving model files
- **THEN** the system SHALL validate file extensions match expected types
- **AND** the system SHALL reject executable files
- **AND** the system SHALL reject files with path traversal sequences (../)
- **AND** the system SHALL enforce maximum file size limits (1GB per file)
- **AND** violations SHALL be logged and transfer aborted

#### Scenario: Disk space protection
- **WHEN** preparing to receive a transfer
- **THEN** the system SHALL check available disk space
- **AND** the system SHALL require 2x the model size in free space (for temp files)
- **AND** if insufficient space, the system SHALL reject transfer before starting
- **AND** the system SHALL provide clear error message with space required

### Requirement: Error Handling and Recovery
The system SHALL handle transfer errors gracefully with clear user feedback.

#### Scenario: Network disconnection during transfer
- **WHEN** WebRTC connection drops mid-transfer
- **THEN** the system SHALL detect disconnection within 5 seconds
- **AND** the system SHALL save transfer state to disk
- **AND** the system SHALL notify user transfer was interrupted
- **AND** the system SHALL offer to retry when connection restored
- **AND** the system SHALL clean up temporary files if user cancels

#### Scenario: Checksum validation failure
- **WHEN** checksum validation fails for a file
- **THEN** the system SHALL log the failure with file name and expected vs actual checksum
- **AND** the system SHALL attempt to retransmit the file
- **AND** the system SHALL retry up to 3 times
- **AND** if all retries fail, the system SHALL abort transfer with error
- **AND** the system SHALL preserve any successfully transferred files for debugging

#### Scenario: Timeout during transfer
- **WHEN** no chunks received for 30 seconds during active transfer
- **THEN** the system SHALL display warning: "Transfer stalled, waiting for data..."
- **AND** the system SHALL wait up to 2 minutes total
- **AND** if timeout expires, the system SHALL abort transfer
- **AND** the system SHALL offer retry option
- **AND** the system SHALL save state for resume capability

#### Scenario: User cancellation
- **WHEN** user interrupts transfer (Ctrl+C or cancel button)
- **THEN** the system SHALL send cancellation message to peer
- **AND** the system SHALL clean up temporary files
- **AND** the system SHALL save transfer state for potential resume
- **AND** the system SHALL display: "Transfer cancelled. Run command again to resume."
- **AND** the system SHALL NOT register partial model in registry
