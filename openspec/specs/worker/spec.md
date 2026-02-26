# worker Specification

## Purpose
TBD - created by archiving change add-rtc-frame-streaming. Update Purpose after archive.
## Requirements
### Requirement: Frame Stream Reception

The Worker SHALL accept incoming video frame streams over WebRTC DataChannel for real-time inference processing.

#### Scenario: Worker receives frame stream start
- **WHEN** Worker receives a `STREAM_START` message with video metadata
- **THEN** Worker SHALL initialize a frame streaming session
- **AND** Worker SHALL respond with `STREAM_ACK` indicating readiness

#### Scenario: Worker receives individual frames (raw)
- **WHEN** Worker receives `FRAME_META` with dtype as numpy dtype (e.g., "uint8")
- **AND** Worker receives binary chunks and `FRAME_END`
- **THEN** Worker SHALL reconstruct the numpy array from binary data
- **AND** Worker SHALL validate frame dimensions match metadata

#### Scenario: Worker receives individual frames (JPEG compressed)
- **WHEN** Worker receives `FRAME_META` with dtype as "jpeg"
- **AND** Worker receives binary chunks and `FRAME_END`
- **THEN** Worker SHALL decode the JPEG data using cv2.imdecode
- **AND** Worker SHALL produce a numpy array for processing

#### Scenario: Worker processes batched frames
- **WHEN** Worker receives frames grouped between `BATCH_START` and `BATCH_END` markers
- **THEN** Worker SHALL accumulate frames until batch is complete
- **AND** Worker SHALL process the batch through inference in a single GPU call

#### Scenario: Worker handles stream completion
- **WHEN** Worker receives `STREAM_END` message
- **THEN** Worker SHALL complete any pending frame processing
- **AND** Worker SHALL send `STREAM_COMPLETE` response with statistics

### Requirement: Frame Verification Modes

The Worker SHALL support multiple modes for handling received frames to balance verification needs with storage constraints.

#### Scenario: Stats-only mode (default)
- **WHEN** Worker is started without `--display` or `--save-every` flags
- **THEN** Worker SHALL count frames and log statistics
- **AND** Worker SHALL NOT save any frames to disk
- **AND** Worker SHALL discard frame data after processing

#### Scenario: Display mode
- **WHEN** Worker is started with `--display` flag
- **THEN** Worker SHALL show received frames in an OpenCV window
- **AND** Worker SHALL overlay frame ID and count on display
- **AND** Worker SHALL NOT save any frames to disk
- **AND** Worker SHALL close display on stream end or 'q' keypress

#### Scenario: Sampled save mode
- **WHEN** Worker is started with `--save-every N` flag
- **THEN** Worker SHALL save every Nth frame to the output directory
- **AND** Worker SHALL use PNG format for saved frames
- **AND** Worker SHALL report number of frames saved in completion message

### Requirement: Frame Inference Pipeline

The Worker SHALL pass received frames through the SLEAP-NN inference pipeline and return predictions.

#### Scenario: Single frame inference
- **WHEN** Worker has a complete frame ready for inference
- **THEN** Worker SHALL run the frame through the loaded SLEAP model
- **AND** Worker SHALL send a `PREDICTION` message with pose estimates

#### Scenario: Batched inference
- **WHEN** Worker has accumulated a complete batch of frames
- **THEN** Worker SHALL run batch inference for GPU efficiency
- **AND** Worker SHALL send `PREDICTION` messages for each frame in batch

#### Scenario: Inference error handling
- **WHEN** inference fails for a frame
- **THEN** Worker SHALL send an `ERROR` message with frame_id and error details
- **AND** Worker SHALL continue processing subsequent frames

### Requirement: JPEG Frame Decoding

The Worker SHALL support decoding JPEG-compressed frames received from clients.

#### Scenario: Decode JPEG frame
- **WHEN** Worker receives a frame with dtype "jpeg"
- **THEN** Worker SHALL use cv2.imdecode to decode the JPEG bytes
- **AND** Worker SHALL produce an RGB numpy array for processing

#### Scenario: Handle JPEG decode failure
- **WHEN** JPEG decoding fails
- **THEN** Worker SHALL log an error with the frame_id
- **AND** Worker SHALL continue processing subsequent frames

### Requirement: Streaming Capability Advertisement

The Worker SHALL advertise frame streaming capability to clients during discovery.

#### Scenario: Worker advertises streaming support
- **WHEN** Worker registers with signaling server
- **THEN** Worker capabilities SHALL include `streaming: true` if streaming is enabled

#### Scenario: Client queries streaming-capable workers
- **WHEN** Client queries for workers with streaming capability
- **THEN** Only workers with `streaming: true` SHALL be returned

### Requirement: Streaming CLI Interface

The Worker SHALL provide CLI options for streaming verification configuration.

#### Scenario: Enable display mode
- **WHEN** Worker is invoked with `--display` flag
- **THEN** Worker SHALL display received frames in an OpenCV window

#### Scenario: Enable sampled saving
- **WHEN** Worker is invoked with `--save-every N` flag
- **THEN** Worker SHALL save every Nth frame to the output directory

#### Scenario: Configure output directory
- **WHEN** Worker is invoked with `--output <path>` flag
- **THEN** Worker SHALL save frames to the specified directory

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

