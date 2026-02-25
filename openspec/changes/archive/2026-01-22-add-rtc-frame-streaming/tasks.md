## 1. Protocol Layer

- [ ] 1.1 Add frame streaming message types to `sleap_rtc/protocol.py`
  - [ ] `STREAM_START` - Stream metadata (video info, total frames, settings, compression)
  - [ ] `STREAM_ACK` - Worker acknowledgment with output info
  - [ ] `FRAME_META` - Per-frame metadata (frame_id, dimensions, dtype/encoding, nbytes)
  - [ ] `FRAME_END` - Frame transmission complete marker
  - [ ] `BATCH_START` / `BATCH_END` - Batch grouping markers
  - [ ] `STREAM_END` - Stream complete signal
  - [ ] `STREAM_COMPLETE` - Worker completion acknowledgment
  - [ ] `PREDICTION` - Inference result message
- [ ] 1.2 Add helper functions for frame protocol message parsing/formatting

## 2. Worker Frame Receiver

- [ ] 2.1 Create `sleap_rtc/worker/frame_receiver.py` module
  - [ ] `FrameReceiver` class to handle incoming frame streams
  - [ ] Frame buffer management for binary chunk reassembly
  - [ ] Numpy array reconstruction from received bytes
  - [ ] **JPEG decoding support** for compressed frames
- [ ] 2.2 Integrate frame receiver into `RTCWorkerClient`
  - [ ] Add `streaming_mode` capability flag
  - [ ] Route frame protocol messages to frame receiver
  - [ ] Handle `STREAM_START` to initialize streaming session
- [ ] 2.3 Add verification modes
  - [ ] Stats-only mode (default): count frames, log statistics, no storage
  - [ ] Display mode (`--display`): show frames in cv2.imshow window
  - [ ] Sampled save mode (`--save-every N`): save every Nth frame to disk
- [ ] 2.4 Connect frame receiver to inference pipeline
  - [ ] Pass reconstructed frames to SLEAP-NN model
  - [ ] Batch frames when batch_size > 1 for efficient GPU utilization
  - [ ] Return predictions over DataChannel

## 3. Client Frame Streamer

- [ ] 3.1 Create `sleap_rtc/client/frame_streamer.py` module
  - [ ] `FrameStreamer` class to send video frames over DataChannel
  - [ ] OpenCV video reading with frame extraction
  - [ ] **Webcam support**: capture from camera devices
  - [ ] Binary chunking (64KB chunks to match existing transfer)
  - [ ] Frame metadata generation
- [ ] 3.2 Add compression options
  - [ ] `--resize WxH` to downscale frames before transmission
  - [ ] `--jpeg-quality N` for JPEG compression (cv2.imencode)
  - [ ] Webcam warmup handling for macOS compatibility
- [ ] 3.3 Add streaming mode to `RTCClient`
  - [ ] `stream_video()` method for streaming inference
  - [ ] Frame selection support (ranges, sampling, batching)
  - [ ] `--max-frames` for webcam stream limiting
  - [ ] Prediction collection and display
- [ ] 3.4 Handle streaming responses
  - [ ] Parse incoming prediction messages
  - [ ] Collect predictions for post-processing
  - [ ] Optional real-time display/callback

## 4. CLI Integration

- [ ] 4.1 Add streaming CLI options to client
  - [ ] `--stream` flag to enable streaming mode
  - [ ] `--webcam <device>` for webcam input (0, 1, etc.)
  - [ ] `--frames` option for frame range selection (e.g., "0-100,200-300")
  - [ ] `--sample-rate` option for frame sampling (every Nth frame)
  - [ ] `--batch-size` option for batch processing
  - [ ] `--fps` option for rate limiting
  - [ ] `--max-frames` for limiting webcam streams
  - [ ] `--resize WxH` for frame resizing
  - [ ] `--jpeg-quality N` for compression (recommended: 80)
- [ ] 4.2 Add worker CLI options
  - [ ] `--display` for visual frame verification
  - [ ] `--save-every N` for sampled frame saving
  - [ ] `--output` for save directory
- [ ] 4.3 Update `sleap_rtc/cli.py` with new options
- [ ] 4.4 Add streaming mode to worker capability advertisement

## 5. Testing

- [ ] 5.1 Create unit tests for frame protocol
- [ ] 5.2 Create integration tests for frame streaming
- [ ] 5.3 Test with local signaling server
- [ ] 5.4 Test webcam streaming on macOS/Linux/Windows
- [ ] 5.5 Test compression modes (raw, JPEG, resize)
- [ ] 5.6 Performance testing with different video sizes/batch sizes
- [ ] 5.7 Test with production signaling server

## 6. Documentation

- [ ] 6.1 Update CLI help text with streaming options
- [ ] 6.2 Add streaming examples to README or docs
- [ ] 6.3 Document frame protocol in protocol.py docstrings
- [ ] 6.4 Document compression trade-offs and recommendations
