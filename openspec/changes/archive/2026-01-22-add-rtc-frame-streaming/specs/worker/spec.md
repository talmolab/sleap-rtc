## ADDED Requirements

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
