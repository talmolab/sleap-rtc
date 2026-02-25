## ADDED Requirements

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
