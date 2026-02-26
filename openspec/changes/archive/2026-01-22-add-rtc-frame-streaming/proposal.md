## Why

SLEAP-RTC currently supports batch file transfer for training and inference jobs, where entire video files or training packages are transferred before processing. However, for real-time applications like live animal tracking, streaming inference, or interactive annotation feedback, we need the ability to stream individual video frames over WebRTC for immediate processing. This enables:

1. **Real-time inference**: Process frames as they're captured without waiting for full video transfer
2. **Interactive workflows**: Get pose predictions while recording or reviewing video
3. **Reduced latency**: Start inference immediately rather than waiting for file transfers
4. **Memory efficiency**: Process frames incrementally without loading entire videos into memory
5. **Live camera support**: Stream directly from webcams for real-time pose tracking

## What Changes

- **Worker**: Add frame streaming receiver capability alongside existing training/inference modes
  - Accept incoming frame streams over DataChannel using a binary frame protocol
  - Support both raw numpy arrays and JPEG-compressed frames
  - Process frames through SLEAP-NN inference pipeline
  - Return predictions back to client over the same channel
  - Support batched frame processing for efficiency
  - Multiple verification modes: stats-only, display window, sampled saving

- **Client**: Add CLI option to stream frames from video files or live webcam
  - New `--stream` mode for streaming inference instead of batch file transfer
  - **Webcam support**: `--webcam <device_id>` for live camera streaming
  - Frame extraction from video files (MP4, AVI, etc.) using OpenCV
  - Frame selection options: ranges, sampling rate, batch size, max frames
  - **Compression options**:
    - `--resize WxH` to downscale frames before transmission
    - `--jpeg-quality N` for JPEG compression (30-60x bandwidth reduction)
  - Real-time prediction display/collection

- **Protocol**: Define frame streaming message format (builds on existing DataChannel infrastructure)
  - Frame metadata messages (dimensions, dtype, frame ID, encoding)
  - Binary frame data transfer with chunking (64KB chunks)
  - Support for raw and JPEG-encoded frame data
  - Batch start/end markers for grouped processing
  - Stream start/end and acknowledgment messages
  - Prediction response messages

## Impact

- Affected specs: worker, client (new capabilities, not modifying existing)
- Affected code:
  - `sleap_rtc/worker/worker_class.py` - Add frame stream handler
  - `sleap_rtc/client/client_class.py` - Add streaming mode
  - `sleap_rtc/cli.py` - Add `--stream` CLI options
  - `sleap_rtc/protocol.py` - Add frame streaming message types
- Backward compatibility: Fully backward compatible - streaming is opt-in via CLI flag
- Dependencies: OpenCV (cv2) already available in project
