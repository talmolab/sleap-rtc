# client Specification

## Purpose
TBD - created by archiving change add-rtc-frame-streaming. Update Purpose after archive.
## Requirements
### Requirement: Frame Stream Transmission

The Client SHALL support streaming video frames to Workers over WebRTC DataChannel for real-time inference.

#### Scenario: Client initiates frame stream from video file
- **WHEN** Client starts streaming mode with a video file path
- **THEN** Client SHALL send `STREAM_START` message with video metadata
- **AND** Client SHALL wait for `STREAM_ACK` before sending frames

#### Scenario: Client initiates frame stream from webcam
- **WHEN** Client starts streaming mode with `--webcam <device_id>`
- **THEN** Client SHALL initialize the webcam with appropriate warmup delay
- **AND** Client SHALL send `STREAM_START` message with webcam metadata
- **AND** Client SHALL wait for `STREAM_ACK` before sending frames

#### Scenario: Client sends individual frames
- **WHEN** Client extracts a frame from video source
- **THEN** Client SHALL send `FRAME_META` with frame dimensions, dtype/encoding, and size
- **AND** Client SHALL send frame data in 64KB binary chunks
- **AND** Client SHALL send `FRAME_END` when frame transmission is complete

#### Scenario: Client sends batched frames
- **WHEN** Client is configured with batch_size > 1
- **THEN** Client SHALL send `BATCH_START::{count}` before the batch
- **AND** Client SHALL send each frame with its metadata
- **AND** Client SHALL send `BATCH_END::{count}` after all batch frames

#### Scenario: Client completes stream
- **WHEN** all selected frames have been transmitted or max_frames reached
- **THEN** Client SHALL send `STREAM_END` message with statistics
- **AND** Client SHALL wait for `STREAM_COMPLETE` response

### Requirement: Webcam Support

The Client SHALL support streaming frames directly from webcam devices.

#### Scenario: Open webcam by device index
- **WHEN** Client specifies `--webcam 0`
- **THEN** Client SHALL open the webcam device at index 0
- **AND** Client SHALL apply platform-specific initialization (e.g., macOS warmup)

#### Scenario: Webcam initialization with warmup
- **WHEN** Client opens a webcam on macOS
- **THEN** Client SHALL wait for camera initialization (1 second delay)
- **AND** Client SHALL discard initial frames to ensure stable capture

#### Scenario: Webcam stream limiting
- **WHEN** Client specifies `--max-frames N`
- **THEN** Client SHALL stop streaming after N frames are sent
- **AND** Client SHALL send `STREAM_END` message

#### Scenario: Indefinite webcam streaming
- **WHEN** Client streams from webcam without `--max-frames`
- **THEN** Client SHALL stream indefinitely until interrupted (Ctrl+C)

### Requirement: Frame Compression Options

The Client SHALL support frame compression to reduce bandwidth usage.

#### Scenario: Resize frames before transmission
- **WHEN** Client specifies `--resize 640x480`
- **THEN** Client SHALL resize all frames to 640x480 before sending
- **AND** Client SHALL report resized dimensions in `STREAM_START` metadata

#### Scenario: JPEG compression
- **WHEN** Client specifies `--jpeg-quality 80`
- **THEN** Client SHALL encode frames as JPEG with quality 80
- **AND** Client SHALL set dtype to "jpeg" in `FRAME_META`
- **AND** Client SHALL send JPEG-encoded bytes instead of raw numpy array

#### Scenario: Combined resize and compression
- **WHEN** Client specifies both `--resize` and `--jpeg-quality`
- **THEN** Client SHALL first resize the frame
- **AND** Client SHALL then apply JPEG compression to resized frame

### Requirement: Frame Selection Options

The Client SHALL support flexible frame selection from video sources.

#### Scenario: Stream all frames
- **WHEN** Client streams without frame selection options
- **THEN** Client SHALL stream all frames from the video file

#### Scenario: Stream frame ranges
- **WHEN** Client specifies `--frames 0-100,200-300`
- **THEN** Client SHALL stream only frames within specified ranges

#### Scenario: Stream sampled frames
- **WHEN** Client specifies `--sample-rate N`
- **THEN** Client SHALL stream every Nth frame from the selection

#### Scenario: Rate-limited streaming
- **WHEN** Client specifies `--fps N`
- **THEN** Client SHALL limit frame transmission to N frames per second

### Requirement: Streaming CLI Interface

The Client SHALL provide CLI options for streaming mode configuration.

#### Scenario: Stream from video file
- **WHEN** Client is invoked with a video file path
- **THEN** Client SHALL stream frames from the specified video file

#### Scenario: Stream from webcam
- **WHEN** Client is invoked with `--webcam <device_id>`
- **THEN** Client SHALL stream frames from the specified webcam device

#### Scenario: Configure compression
- **WHEN** Client specifies `--resize WxH` and/or `--jpeg-quality N`
- **THEN** Client SHALL apply specified compression before transmission

### Requirement: Prediction Collection

The Client SHALL receive and process inference predictions from the Worker.

#### Scenario: Client receives predictions
- **WHEN** Worker sends `PREDICTION` message for a frame
- **THEN** Client SHALL parse the prediction data
- **AND** Client SHALL associate prediction with correct frame_id

#### Scenario: Client handles prediction errors
- **WHEN** Worker sends `ERROR` message for a frame
- **THEN** Client SHALL log the error with frame_id
- **AND** Client SHALL continue receiving subsequent predictions

#### Scenario: Client aggregates results
- **WHEN** stream is complete
- **THEN** Client SHALL have collected predictions for all successfully processed frames
- **AND** Client SHALL report summary statistics (frames sent, predictions received, FPS)

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

