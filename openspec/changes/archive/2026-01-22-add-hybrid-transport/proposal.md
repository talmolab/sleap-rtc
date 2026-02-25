# Hybrid Transport Architecture for Large File Transfers

**Status:** Proposed
**Created:** 2025-11-12
**Author:** System Architecture Review

## Problem Statement

The current architecture uses WebRTC data channels for all data transfer, including large training datasets and model files. This approach has several limitations:

### Current Limitations

1. **No Native Resumption**: If a WebRTC connection drops during a 5 GB dataset transfer at 60% completion, the entire transfer must restart from 0%. WebRTC has no built-in resume capability.

2. **Memory Pressure**: Sending large files through WebRTC data channels can cause memory issues:
   - Chunks buffer in RAM if sent too fast
   - Can lead to out-of-memory errors
   - Requires careful backpressure handling

3. **NAT/Firewall Timeouts**: Long transfers (>15 minutes) exceed typical NAT timeout windows:
   - Consumer routers: 5-15 min NAT timeout
   - University firewalls: 10-30 min timeout
   - Large transfers are fragile and frequently fail

4. **No Built-in Compression**: WebRTC sends raw data by default, wasting bandwidth on compressible training data (JSON/CSV labels, configs).

5. **Variable File Sizes**: Training packages range from a few MB to several GB (models can be 100 MB - 7 GB), making one-size-fits-all transport inefficient.

6. **Worker Type Heterogeneity**:
   - **RunAI workers**: Ephemeral pods with no persistent storage (models lost on pod termination)
   - **Desktop workers**: Persistent storage but variable availability
   - Need centralized storage that works for both

### Impact

- Users experience frequent transfer failures on large datasets
- Workers must be available throughout entire transfer (no fire-and-forget)
- Bandwidth costs high (TURN relay usage for failed direct connections)
- Poor user experience (no progress preservation on failure)

## Proposed Solution

Implement a **hybrid transport architecture** that separates control plane from data plane:

### Architecture Overview

```
CONTROL PLANE (WebRTC + Signaling Server)
├─ Job coordination and routing
├─ Worker discovery
├─ Real-time training progress updates
├─ Interactive commands (pause, stop, adjust)
└─ Small messages (< 1 MB)

DATA PLANE (S3 + HTTP)
├─ Training datasets (GB scale)
├─ Model files (100 MB - 7 GB)
├─ Final artifacts and checkpoints
└─ Room-level model registry
```

### Key Components

#### 1. Three-Tier Storage Strategy

**Tier 1: Temporary Upload Storage**
- S3 bucket for client uploads (24-hour TTL)
- Presigned URLs for secure, credential-free uploads
- Automatic cleanup to save costs

**Tier 2: Room Storage (Permanent)**
- Per-room model registries in S3
- Trained models persist beyond room lifecycle
- Accessible to all room members
- Manifest tracks model metadata and availability

**Tier 3: Worker Cache (Local, Optional)**
- Desktop workers: Persistent cache (enables P2P sharing)
- RunAI workers: Ephemeral session cache
- LRU eviction strategy

#### 2. Adaptive Transport Selection

Automatic transport selection based on file size:

- **< 100 MB**: WebRTC (fast, low latency, P2P)
- **> 100 MB**: S3 HTTP (resumable, reliable, scalable)

#### 3. Presigned URL Workflow

1. Client requests upload URL from backend
2. Backend generates presigned S3 URLs (time-limited, location-specific)
3. Client uploads directly to S3 (no AWS credentials needed)
4. Client submits job via signaling server (small message with S3 reference)
5. Worker downloads from S3 using presigned URLs or IAM role

#### 4. Real-Time Progress Streaming

WebRTC data channels still used for:
- Training progress updates (epoch, loss, metrics)
- Batch-level progress (within-epoch updates)
- Sample visualizations (compressed images)
- Interactive commands (pause, resume, stop)
- GPU/system metrics

### Room-Level Model Registry

Each room has a centralized manifest in S3:

```
s3://sleap-rtc-rooms/{room_id}/
├── manifest.json          # Room registry (metadata)
└── models/
    ├── centroid_a3f5e8c9/
    │   ├── best.ckpt
    │   ├── training_config.json
    │   └── initial_config.json
    └── topdown_b4f6d2e1/
        └── ...
```

**Manifest tracks:**
- Model metadata (ID, alias, type, trained_by, trained_at)
- Storage locations (S3 paths)
- Availability (which workers have cached copies)
- Tags and notes for organization

### Worker Type Handling

**RunAI Workers (Ephemeral):**
- Must upload to S3 immediately after training (before pod termination)
- Don't advertise as P2P sources (unreliable)
- Use session cache only (no persistence)
- Room storage is single source of truth

**Desktop Workers (Persistent):**
- Upload to S3 (backup + sharing)
- Cache locally (persistent across restarts)
- Can advertise as P2P sources (if online)
- Reduce bandwidth costs via P2P sharing

## Benefits

### Reliability
- ✅ **Resumable uploads**: S3 multipart upload with resume capability
- ✅ **No size limits**: Can handle TBs if needed
- ✅ **No NAT timeouts**: HTTP keep-alive handles long transfers
- ✅ **Guaranteed model persistence**: Survives worker disconnects

### Performance
- ✅ **Parallel chunk uploads**: Faster than sequential WebRTC
- ✅ **Built-in compression**: gzip encoding for HTTP
- ✅ **Progress tracking**: Byte-level upload progress
- ✅ **Client-side checksums**: Data integrity verification

### Cost Efficiency
- ✅ **Reduced TURN relay usage**: Large files bypass WebRTC relay
- ✅ **P2P optimization**: Desktop workers provide "free CDN"
- ✅ **In-region transfers**: Free when worker/S3 in same region
- ✅ **Bandwidth savings**: ~40-70% cost reduction

### User Experience
- ✅ **Real-time feedback**: WebRTC progress streaming
- ✅ **Fire-and-forget**: Client can disconnect during training
- ✅ **Model persistence**: Access models across sessions
- ✅ **Team collaboration**: Shared room registries
- ✅ **Interactive control**: Pause, stop, adjust via WebRTC

## Trade-offs

### Complexity
- ⚠️ More moving parts (S3, presigned URLs, backend API)
- ⚠️ Need backend service for URL generation
- ⚠️ More failure modes to handle

### Infrastructure
- ⚠️ Requires S3 buckets and IAM configuration
- ⚠️ Backend service for presigned URL generation
- ⚠️ Additional monitoring and logging needed

### Cost
- ⚠️ S3 storage costs (~$0.023/GB/month)
- ⚠️ S3 egress costs (~$0.09/GB for internet, free in-region)
- ⚠️ Backend service hosting (minimal)

**However**: Total costs still lower than current TURN relay usage and bandwidth waste from failed transfers.

## Success Criteria

1. **Reliability**: > 99% success rate for large file transfers (> 1 GB)
2. **Resumability**: Failed uploads can resume from last checkpoint
3. **Performance**: Large uploads complete 2-3x faster than current WebRTC approach
4. **Cost**: 40-70% reduction in bandwidth costs
5. **User Experience**: Real-time progress updates maintain low latency (< 500ms)
6. **Model Persistence**: 100% of trained models survive worker disconnects

## Alternatives Considered

### Alternative 1: Improve WebRTC Chunking with Resume
- Add checkpoint/resume capability to WebRTC transfers
- **Rejected**: Still vulnerable to NAT timeouts, doesn't solve fundamental reliability issues

### Alternative 2: Fully Decentralized (IPFS/BitTorrent)
- Pure P2P with no central storage
- **Rejected**: Too complex, no guaranteed availability, difficult to manage

### Alternative 3: User-Managed Storage (Bring Your Own Bucket)
- Users store in their own S3, share references only
- **Deferred**: Good for Phase 2, but adds user complexity initially

### Alternative 4: Keep WebRTC-Only
- Status quo
- **Rejected**: Doesn't solve fundamental problems with large file transfers

## Implementation Phases

### Phase 1: Core Infrastructure (Weeks 1-2)
- Set up S3 buckets with lifecycle policies
- Implement backend API for presigned URL generation
- Basic upload/download workflows
- Validate with small-scale testing

### Phase 2: Client Integration (Weeks 3-4)
- Adaptive transport selection in client
- S3 upload with progress tracking
- Job submission with S3 references
- Error handling and retries

### Phase 3: Worker Integration (Weeks 5-6)
- Worker S3 download capability
- Room manifest updates after training
- Worker type detection (RunAI vs Desktop)
- Model caching strategies

### Phase 4: Optimization (Weeks 7-8)
- P2P sharing for desktop workers
- Compression and deduplication
- Regional proxy caching
- Performance tuning

## Open Questions

1. **S3 Bucket Configuration**: Single bucket vs multiple buckets per region?
2. **IAM Strategy**: Workers use IAM roles or presigned URLs for downloads?
3. **Model Retention**: Default lifecycle policy for models (90 days? 1 year? User-managed)?
4. **Room Expiry**: What happens to models when room expires (2-hour TTL)?
5. **Backend Hosting**: Deploy as Lambda functions or dedicated service?
6. **Cost Allocation**: Who pays egress costs for cross-region transfers?

## Dependencies

- AWS S3 access (buckets, IAM roles)
- Backend service for presigned URL generation (new component)
- boto3 library (already in dependencies)
- Updates to signaling server protocol (minor, job references only)

## Risks

1. **Migration Complexity**: Existing users must transition workflows
   - **Mitigation**: Maintain backward compatibility, gradual rollout

2. **AWS Dependency**: Tight coupling to AWS services
   - **Mitigation**: Abstract storage backend, plan for alternative providers

3. **Cost Overruns**: S3 egress costs could be higher than expected
   - **Mitigation**: Monitor usage, implement caching strategies, cost alerts

4. **Backend Service Reliability**: New single point of failure
   - **Mitigation**: Redundant deployment, fallback to direct S3 access for workers

## Related Changes

- `add-client-model-registry`: Provides local caching infrastructure
- `add-client-room-connection`: Room-based coordination foundation
- Future: `add-model-versioning`: Track model lineage in registry
- Future: `add-wandb-integration`: Optional W&B artifact storage

## References

- [AWS S3 Multipart Upload Documentation](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html)
- [WebRTC Data Channel Limitations](https://webrtc.org/getting-started/data-channels)
- Project discussion: `/docs/ARCHITECTURE_DIAGRAM.md`
- Project discussion: `/docs/MODEL_REGISTRY_ARCHITECTURE_DISCUSSION.md`
