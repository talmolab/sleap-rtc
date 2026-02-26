# Hybrid Transport Architecture: Design Document

## WebRTC Chunking vs S3 Multipart Upload: Key Differences

### Current Architecture: WebRTC Chunking

**How it works currently:**

```
Client (has 5 GB dataset)
    ↓
Split into 64 KB chunks (78,125 chunks)
    ↓
Establish WebRTC connection to Worker
    ↓
Send chunk 1 over DataChannel → Worker receives → Acknowledge
Send chunk 2 over DataChannel → Worker receives → Acknowledge
Send chunk 3 over DataChannel → Worker receives → Acknowledge
...
[Connection drops at chunk 50,000]
    ↓
❌ START OVER FROM CHUNK 1
```

**Characteristics:**
- **Streaming protocol**: Chunks sent sequentially over persistent connection
- **Stateful**: Connection maintains transfer state
- **Memory-bound**: Chunks buffer in DataChannel if sender outpaces receiver
- **No checkpointing**: No saved progress if connection fails
- **Real-time**: Very low latency (good for interactive data)
- **P2P**: Direct connection between peers (when NAT traversal succeeds)

---

### Proposed Architecture: S3 Multipart Upload

**How S3 multipart works:**

```
Client (has 5 GB dataset)
    ↓
Request upload session from Backend
    ← Backend returns presigned URLs for each part
    ↓
Split into 100 MB parts (50 parts)
    ↓
Upload part 1 to S3 (HTTP PUT) → S3 stores → Returns ETag
Upload part 2 to S3 (HTTP PUT) → S3 stores → Returns ETag
Upload part 3 to S3 (HTTP PUT) → S3 stores → Returns ETag
...
Upload part 30 to S3 (HTTP PUT) → S3 stores → Returns ETag
[Connection drops]
    ↓
Client checks: What parts are uploaded?
    ← S3 responds: Parts 1-30 are complete
    ↓
✅ RESUME FROM PART 31 (not from beginning!)
```

**Characteristics:**
- **Stateless protocol**: Each part is independent HTTP request
- **Server-side checkpointing**: S3 remembers which parts completed
- **No memory pressure**: HTTP client doesn't buffer entire file
- **Resumable**: Can restart from last successful part
- **Higher latency**: HTTP overhead per request (but acceptable for large files)
- **Client-to-Server**: Centralized storage (no P2P)

---

## Detailed Comparison

### 1. Failure Recovery

**WebRTC Chunking (Current):**
```
Chunk Size: 64 KB
File Size: 5 GB = 5,000,000 KB
Total Chunks: 78,125 chunks

Transfer progress: [████████████░░░░░░░░░░] 60% (chunk 46,875)
Connection fails ❌

To resume:
- Client must re-establish WebRTC connection
- Client must resend chunks 1-78,125 from scratch
- 3 GB of progress lost
- User waits another 30 minutes

Probability of success decreases with transfer duration:
- 5 min transfer: ~95% success
- 15 min transfer: ~70% success (NAT timeout risk)
- 30 min transfer: ~40% success (high failure rate)
```

**S3 Multipart (Proposed):**
```
Part Size: 100 MB (configurable, can be 5 MB - 5 GB)
File Size: 5 GB
Total Parts: 50 parts

Transfer progress: [████████████░░░░░░░░░░] 60% (part 30/50)
Connection fails ❌

To resume:
- Client queries S3: "What parts are uploaded?"
- S3 responds: "Parts 1-30 complete (ETags: xyz...)"
- Client resumes from part 31
- Only 2 GB remaining (not 5 GB)
- User waits 12 minutes (not 30 minutes)

Probability of eventual success: ~99.9%
- Each part is independent
- Retry indefinitely until success
- NAT timeout doesn't matter (each part uploads in < 1 minute)
```

---

### 2. Memory Management

**WebRTC Chunking (Current):**
```javascript
// Sender side
for (let i = 0; i < chunks.length; i++) {
    dataChannel.send(chunks[i]);  // 64 KB chunk

    // Problem: If sender sends faster than network can transmit,
    // chunks buffer in DataChannel's internal queue
    // This queue lives in RAM!
}

// What happens with 5 GB file:
// - Chunks generated in memory
// - DataChannel buffers chunks if network slow
// - Can accumulate hundreds of MB in RAM
// - Potential out-of-memory on sender
// - Potential out-of-memory on receiver

// Need manual backpressure:
if (dataChannel.bufferedAmount > threshold) {
    await sleep(100);  // Wait for buffer to drain
}
```

**S3 Multipart (Proposed):**
```python
# Sender side
with open(file_path, 'rb') as f:
    for part_num in range(1, total_parts + 1):
        # Read 100 MB chunk from disk
        data = f.read(100 * 1024 * 1024)

        # Upload via HTTP (streaming)
        response = requests.put(
            presigned_url,
            data=data  # Sent as streaming request body
        )

        # Chunk immediately garbage collected after upload
        # Memory usage: ~100 MB peak (one part at a time)

# What happens with 5 GB file:
# - Only one 100 MB part in RAM at once
# - HTTP client handles flow control automatically
# - No manual backpressure needed
# - Predictable memory usage regardless of file size
```

---

### 3. Parallelization

**WebRTC Chunking (Current):**
```
WebRTC DataChannel = Single ordered stream

Chunks must be sent sequentially:
Chunk 1 → Chunk 2 → Chunk 3 → ... → Chunk 78,125
    ↓         ↓         ↓              ↓
Single TCP-like stream (SCTP over DTLS)

Cannot parallelize:
- Chunks must arrive in order
- Sender waits for receiver acknowledgment
- Single bottleneck

Transfer speed limited by:
- Single connection bandwidth
- Round-trip latency
- Receiver processing speed
```

**S3 Multipart (Proposed):**
```
S3 Parts = Independent uploads

Parts can be uploaded in parallel:
Part 1 ──┐
Part 2 ──┤
Part 3 ──┼──> S3 (handles concurrency)
Part 4 ──┤
Part 5 ──┘

Each part:
- Independent HTTP connection
- Can upload simultaneously (limited by CPU/bandwidth)
- No ordering requirement
- S3 reassembles on completion

Transfer speed benefits:
- 10 concurrent parts = ~10x faster (in ideal conditions)
- Better utilization of available bandwidth
- Tolerant of individual part failures
- Can adjust concurrency based on network conditions

Example:
Sequential: 5 GB ÷ 10 MB/s = 500 seconds (8.3 minutes)
Parallel (10x): 5 GB ÷ 100 MB/s = 50 seconds (0.8 minutes)
```

---

### 4. Checkpointing and Resume

**WebRTC Chunking (Current):**
```
No built-in checkpointing mechanism

To add resume capability, would need to implement:
1. Sender tracks: "Sent chunks 1-50,000"
2. Receiver tracks: "Received chunks 1-50,000"
3. On disconnect:
   a. Receiver saves state to disk
   b. Sender saves state to disk
4. On reconnect:
   a. Establish new WebRTC connection
   b. Exchange checkpoint info
   c. Resume from chunk 50,001

Challenges:
- WebRTC connections are ephemeral (can't persist)
- Worker might be different instance (RunAI pod)
- Receiver state might be lost (ephemeral storage)
- Complex state synchronization
- NAT timeout still kills long transfers
```

**S3 Multipart (Proposed):**
```
Built-in checkpointing by design

S3 tracks upload state server-side:
1. Client initiates multipart upload → Gets upload_id
2. Client uploads parts → S3 stores each part independently
3. On disconnect:
   - S3 retains all completed parts (keyed by upload_id)
   - No client/worker state needed
4. On reconnect:
   - Client queries S3: "List parts for upload_id"
   - S3 responds with completed parts
   - Client uploads only missing parts
5. When all parts uploaded:
   - Client calls "Complete multipart upload"
   - S3 atomically assembles final file

Benefits:
- Server-side state (reliable)
- Works across client restarts
- Works across worker changes
- No custom checkpoint logic needed
- Industry-standard, battle-tested
```

---

### 5. Network Efficiency

**WebRTC Chunking (Current):**
```
Overhead per chunk:
- Chunk data: 64 KB
- SCTP header: ~12 bytes
- DTLS encryption overhead: ~13-29 bytes
- UDP/IP headers: 28 bytes
- Total overhead: ~41-69 bytes per chunk

For 5 GB transfer:
- Chunks: 78,125
- Data overhead: 78,125 × 60 bytes ≈ 4.5 MB
- Percentage overhead: 0.09% (negligible)

BUT: Reliability overhead matters more
- Retransmit entire transfer on failure
- No compression (send raw data)
- Potential TURN relay costs ($0.40/GB if used)

Real-world overhead:
- Failed transfer at 60% = wasted 3 GB bandwidth
- Average 1.5 retries = 7.5 GB transferred for 5 GB file
- Effective overhead: 50%!
```

**S3 Multipart (Proposed):**
```
Overhead per part:
- Part data: 100 MB
- HTTP headers: ~1 KB
- TLS encryption overhead: ~1 KB per SSL record
- TCP/IP headers: minimal
- Total overhead: ~0.002% (negligible)

For 5 GB transfer:
- Parts: 50
- Data overhead: 50 × 2 KB ≈ 100 KB
- Percentage overhead: 0.002% (negligible)

Efficiency benefits:
- Retry only failed parts (not entire file)
- Built-in gzip compression option
- No TURN relay needed (direct to S3)

Real-world efficiency:
- Failed part retransmitted: 100 MB (not 5 GB)
- Compression: 30-50% reduction on text data
- Effective overhead: ~5% (vs 50% for WebRTC)
```

---

### 6. Latency Characteristics

**WebRTC Chunking (Current):**
```
Best for: Real-time, low-latency streaming
- P2P direct connection: 10-50ms latency
- Immediate data availability
- Good for: Live video, interactive apps, progress updates

Not optimal for: Large bulk transfers
- Latency advantage wasted (not real-time sensitive)
- Connection fragility matters more
- Lack of resume capability critical issue
```

**S3 Multipart (Proposed):**
```
Optimized for: Reliable bulk transfer
- HTTP connection: 50-200ms latency
- Higher per-request overhead
- Good for: Large files, batch processing, archives

Not optimal for: Real-time data
- Too much overhead for small messages
- Not suitable for streaming
- Overkill for < 10 MB files
```

---

## Why Both Are Needed (Hybrid Approach)

### Use Case Matrix

| Data Type | Size | Frequency | Best Transport | Why |
|-----------|------|-----------|----------------|-----|
| Training dataset | 1-10 GB | Once per job | **S3** | Resumable, reliable, can take time |
| Model checkpoint | 100 MB - 7 GB | Once per training | **S3** | Persistence critical, large |
| Training config | < 1 MB | Once per job | **WebRTC** | Small, immediate, low overhead |
| Progress update | < 1 KB | Every 10 seconds | **WebRTC** | Real-time, low latency critical |
| Batch progress | < 1 KB | Every second | **WebRTC** | Very frequent, real-time |
| Sample visualization | 50-500 KB | Every 5 epochs | **WebRTC** | Semi-frequent, nice-to-have |
| User command (pause) | < 100 bytes | On-demand | **WebRTC** | Interactive, immediate |
| Inference frames | 1-10 MB | Continuous | **WebRTC** | Real-time, streaming |
| Inference results | 10-100 KB | Continuous | **WebRTC** | Real-time, streaming |

### Architecture Decision Rules

```python
def choose_transport(data_size, data_type, realtime_required):
    """Select optimal transport method."""

    # Rule 1: Real-time data always uses WebRTC
    if realtime_required:
        return "WebRTC"

    # Rule 2: Very small data uses WebRTC (setup overhead not worth it)
    if data_size < 10_000_000:  # < 10 MB
        return "WebRTC"

    # Rule 3: Large data uses S3 (reliability critical)
    if data_size > 100_000_000:  # > 100 MB
        return "S3"

    # Rule 4: Medium data depends on context
    if 10_000_000 < data_size < 100_000_000:
        if data_type in ["model", "dataset"]:
            return "S3"  # Persistence matters
        else:
            return "WebRTC"  # Convenience matters

    return "WebRTC"  # Default for small/unknown
```

---

## Technical Architecture

### Data Flow: Training Job Submission

```
┌──────────────────────────────────────────────────────────────┐
│ PHASE 1: Upload Dataset (S3 Multipart)                      │
└──────────────────────────────────────────────────────────────┘

Client
  ├─> Request presigned URLs from Backend
  │     POST /api/request-upload {file_size: 5GB, room_id}
  │     ← {upload_id, presigned_urls[1..50]}
  │
  ├─> Upload parts to S3 (parallel, resumable)
  │     PUT s3://bucket/upload123/part1 (100 MB)
  │     PUT s3://bucket/upload123/part2 (100 MB)
  │     ...
  │     PUT s3://bucket/upload123/part50 (100 MB)
  │
  └─> Complete multipart upload
        POST /api/complete-upload {upload_id, parts[]}
        ← {s3_path: "s3://bucket/upload123/dataset.zip"}


┌──────────────────────────────────────────────────────────────┐
│ PHASE 2: Submit Job (Signaling Server)                      │
└──────────────────────────────────────────────────────────────┘

Client
  └─> Send job request via signaling (peer_message)
        {
          "app_message_type": "job_request",
          "dataset": {"type": "s3", "path": "s3://..."},
          "config": {...},
          "room_id": "lab-mice-2025"
        }
        │
        │ Signaling Server routes to Worker
        ↓
      Worker


┌──────────────────────────────────────────────────────────────┐
│ PHASE 3: Worker Processing (S3 Download + WebRTC Progress)  │
└──────────────────────────────────────────────────────────────┘

Worker
  ├─> Download dataset from S3
  │     GET s3://bucket/upload123/dataset.zip
  │     (automatic retry, resume if needed)
  │
  ├─> Establish WebRTC DataChannel with Client
  │     (for real-time progress streaming)
  │
  ├─> Train model
  │     ├─> Send progress via WebRTC
  │     │     {"epoch": 1, "loss": 0.523} → Client
  │     │     {"epoch": 2, "loss": 0.412} → Client
  │     │     ...
  │     └─> User can interact via WebRTC
  │           ← {"command": "pause"} from Client
  │
  ├─> Upload trained model to S3 room storage
  │     PUT s3://sleap-rtc-rooms/room123/models/a3f5e8c9/
  │
  ├─> Update room manifest
  │     (S3 optimistic locking)
  │
  └─> Notify client via WebRTC
        {"model_id": "a3f5e8c9", "status": "complete"} → Client
```

---

## Summary: Key Differences

### WebRTC Chunking (64 KB chunks)

**Strengths:**
- ✅ Low latency (10-50ms)
- ✅ P2P direct connection (when NAT succeeds)
- ✅ Real-time streaming
- ✅ Good for interactive data
- ✅ Good for small files (< 10 MB)

**Weaknesses:**
- ❌ No resume capability (start over on failure)
- ❌ Memory pressure (buffering issues)
- ❌ NAT timeout risk (> 15 min transfers fail)
- ❌ Sequential only (no parallelization)
- ❌ Poor for large files (> 100 MB)
- ❌ Reliability decreases with duration

**Use Cases:**
- Real-time progress updates
- Interactive commands
- Small configs and messages
- Live inference (frames + predictions)

---

### S3 Multipart (100 MB parts)

**Strengths:**
- ✅ Resumable (server-side checkpointing)
- ✅ Parallelizable (concurrent parts)
- ✅ No memory pressure (streaming)
- ✅ No NAT timeout issues
- ✅ Excellent for large files (GB scale)
- ✅ Reliability increases with duration

**Weaknesses:**
- ❌ Higher latency (50-200ms)
- ❌ Centralized (not P2P)
- ❌ Requires infrastructure (S3, backend)
- ❌ Overkill for small files (< 10 MB)

**Use Cases:**
- Training datasets (GB)
- Model checkpoints (100 MB - 7 GB)
- Final artifacts
- Any large file requiring reliability

---

## Conclusion

Both chunking approaches use chunks/parts, but the **key differences** are:

1. **Resume Capability**: S3 has server-side checkpointing, WebRTC doesn't
2. **Parallelization**: S3 parts are independent, WebRTC chunks are sequential
3. **Memory Management**: S3 streams one part at a time, WebRTC buffers many chunks
4. **Reliability**: S3 designed for bulk transfer, WebRTC for real-time streaming
5. **Infrastructure**: S3 needs backend/storage, WebRTC needs only signaling

**The hybrid approach uses each for what it's best at**, resulting in a robust, efficient, and user-friendly system.
