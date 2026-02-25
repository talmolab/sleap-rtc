## Context

SLEAP-RTC currently transfers complete files (training packages, videos) over WebRTC DataChannels before processing. For real-time inference scenarios, we need frame-by-frame streaming. This design builds on the proven DataChannel infrastructure while adding streaming-specific protocol messages.

**Stakeholders**: Users requiring real-time pose estimation, developers integrating live camera feeds

**Constraints**:
- Must work alongside existing file transfer mode (not replace it)
- Must use existing WebRTC DataChannel infrastructure
- Frame data must fit within DataChannel message limits (chunking required)
- Worker must support both GPU inference and streaming simultaneously
- Must handle webcam initialization quirks on different platforms (especially macOS)

## Goals / Non-Goals

**Goals**:
- Stream video frames from client to worker over WebRTC
- Support both video files and live webcam sources
- Provide compression options for bandwidth-constrained networks
- Return inference predictions back to client in real-time
- Support frame batching for efficient GPU utilization
- Maintain backward compatibility with existing training/inference workflows
- Zero storage footprint by default (frames processed in memory)

**Non-Goals**:
- WebRTC MediaTrack video streaming (using DataChannel for consistency and control)
- Multi-worker frame distribution (single worker per stream for now)
- Video encoding/compression over RTC beyond JPEG (raw frames for ML compatibility)
- Audio streaming

## Decisions

### Decision 1: Use DataChannel for frame streaming (not MediaTrack)

**What**: Stream frames as binary data over RTCDataChannel rather than using WebRTC's MediaTrack API.

**Why**:
- Consistent with existing file transfer architecture
- Full control over frame format (raw numpy arrays needed for ML)
- No codec overhead or quality loss for raw mode
- Easier to implement batching and metadata
- JPEG compression available when bandwidth is limited

**Alternatives considered**:
- MediaTrack: Would require decoding frames from video codec, adds latency and quality loss
- Custom TCP/UDP: Would bypass WebRTC's NAT traversal and ICE infrastructure

### Decision 2: Frame protocol message format

**What**: Use string-prefixed messages for metadata, raw binary for frame data.

```
FRAME_META::{frame_id}:{height}:{width}:{channels}:{dtype}:{nbytes}
[binary chunks - 64KB each]
FRAME_END::{frame_id}
```

Where `dtype` is either a numpy dtype string (e.g., "uint8") or "jpeg" for compressed frames.

**Why**:
- Matches existing file transfer pattern (FILE_META, chunks, FILE_COMPLETE)
- String prefixes allow easy routing in message handlers
- Binary chunks avoid base64 encoding overhead
- Frame ID enables out-of-order handling if needed
- dtype field supports both raw and compressed formats

### Decision 3: JPEG compression for bandwidth optimization

**What**: Optional JPEG compression via `--jpeg-quality N` (1-100).

**Size comparison (1920x1080 RGB frame)**:
| Mode | Size per frame | Reduction |
|------|---------------|-----------|
| Raw RGB | ~6 MB | baseline |
| Resize 640x480 | ~900 KB | ~7x |
| JPEG quality 80 | ~100-200 KB | ~30-60x |
| Resize + JPEG | ~30-50 KB | ~100-200x |

**Why**:
- Webcam streaming at 1080p without compression is too slow
- JPEG is fast to encode/decode (OpenCV optimized)
- Quality 80 provides good visual quality with huge bandwidth savings
- User controls trade-off via CLI flag

**Trade-offs**:
- JPEG is lossy - some detail lost (acceptable for pose estimation)
- Additional CPU overhead for encode/decode (minimal with OpenCV)
- Not suitable for grayscale scientific imaging (use raw mode)

### Decision 4: Webcam support with platform handling

**What**: Support webcam input via `--webcam <device_id>` with platform-specific initialization.

**macOS handling**:
```python
# Webcams need warmup time on macOS
await asyncio.sleep(1.0)
for _ in range(5):
    cap.read()  # Discard initial frames
```

**Why**:
- Live camera feed is key use case for real-time tracking
- OpenCV provides cross-platform webcam access
- macOS requires warmup period before stable frame capture
- Device index (0, 1, ...) is standard across platforms

### Decision 5: Batch processing support

**What**: Allow grouping frames with BATCH_START/BATCH_END markers.

**Why**:
- GPU inference is more efficient with batched inputs
- Reduces per-frame overhead
- Client controls batch size based on latency requirements

### Decision 6: Worker verification modes

**What**: Three modes for handling received frames:

| Mode | Flag | Storage | Use Case |
|------|------|---------|----------|
| Stats only | (default) | 0 bytes | Production, bandwidth testing |
| Display | `--display` | 0 bytes | Visual verification, demos |
| Save sampled | `--save-every N` | N frames | Debugging, quality checks |

**Why**:
- Default mode uses zero storage (frames discarded after processing)
- Display mode provides instant visual feedback
- Sampled saving allows verification without filling disk
- User explicitly opts into any storage usage

### Decision 7: Predictions returned over same DataChannel

**What**: Send predictions back as JSON messages on the same DataChannel.

```json
{
  "type": "PREDICTION",
  "frame_id": 42,
  "instances": [...],
  "confidence": [...]
}
```

**Why**:
- Bidirectional DataChannel already exists
- JSON allows flexible prediction format
- Easy to extend for different model outputs

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Large frames may cause backpressure | Monitor bufferedAmount, pause sending when buffer full |
| Memory usage for frame buffers | Clear buffers after processing, limit max concurrent frames |
| Inference slower than frame rate | Client rate limiting (--fps), batch accumulation |
| Network latency spikes | Timeout handling, reconnection logic |
| Webcam initialization failures | Warmup delay, retry logic, clear error messages |
| JPEG quality too low | Recommend quality 80, allow user override |

## Migration Plan

No migration needed - this is additive functionality:

1. Deploy worker with streaming capability
2. Workers advertise `streaming: true` in capabilities
3. Clients use `--stream` or `--webcam` flag to opt into streaming mode
4. Existing training/inference workflows unchanged

**Rollback**: Remove streaming flags; workers ignore streaming messages if handler not present.

## Open Questions

1. ~~Should predictions be streamed per-frame or batched?~~
   - **Resolved**: Per-frame for lowest latency, batch optionally for efficiency

2. ~~How to handle slow inference (frames arriving faster than processing)?~~
   - **Resolved**: Client-side rate limiting (--fps), worker can send backpressure signal

3. Support for multiple concurrent streams to same worker?
   - **Proposed**: Single stream per worker initially, extend later if needed

4. Should we support other compression formats (WebP, PNG)?
   - **Proposed**: JPEG only for now, add others if needed
