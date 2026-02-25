# Tasks: Hybrid Transport Architecture

## Phase 1: Infrastructure Setup (Foundation)

### 1.1 AWS S3 Configuration
- [ ] Create S3 bucket for temporary uploads (`sleap-rtc-uploads`)
  - Configure 24-hour lifecycle policy for auto-cleanup
  - Enable versioning
  - Configure CORS for browser uploads (if web UI planned)
- [ ] Create S3 bucket for room storage (`sleap-rtc-rooms`)
  - No lifecycle policy (permanent storage)
  - Enable encryption at rest
  - Configure access logging
- [ ] Set up IAM roles for workers
  - Read/write access to room storage
  - Read-only access to upload bucket
  - Document role assumption process
- [ ] Configure S3 bucket policies
  - Restrict direct access (presigned URLs only for clients)
  - Allow worker IAM roles
  - Set up cost alerts and monitoring

**Validation:** Manually upload/download files using AWS CLI with presigned URLs

---

### 1.2 Backend Service for Presigned URLs
- [ ] Design backend API endpoints
  - `POST /api/request-upload` - Generate upload URLs
  - `POST /api/complete-upload` - Finalize multipart upload
  - `POST /api/request-download` - Generate download URLs (for clients without IAM)
  - `GET /api/upload-status/{upload_id}` - Check upload progress
- [ ] Implement presigned URL generation
  - Multipart upload URL generation
  - Part-specific URLs with expiration (1 hour)
  - Checksum/ETag tracking
- [ ] Add authentication middleware
  - Validate Cognito tokens
  - Verify room access permissions
  - Rate limiting per user
- [ ] Deploy backend service
  - Choose deployment: Lambda functions vs dedicated service
  - Set up monitoring and logging
  - Configure auto-scaling if needed

**Validation:** Call API endpoints with curl/Postman, verify presigned URLs work

---

### 1.3 Update Configuration System
- [ ] Add S3 configuration to config schema
  - `s3_upload_bucket` setting
  - `s3_room_bucket` setting
  - `s3_region` setting
  - `backend_api_url` setting
- [ ] Add transport selection thresholds
  - `large_file_threshold` (default: 100 MB)
  - `multipart_chunk_size` (default: 100 MB)
  - `max_concurrent_parts` (default: 10)
- [ ] Update environment configuration
  - Development: Local MinIO or test S3 bucket
  - Production: Production S3 buckets
  - Document configuration in README

**Validation:** Load config in development and production modes, verify settings parse correctly

---

## Phase 2: Client Upload Implementation

### 2.1 S3 Upload Client Library
- [ ] Create `S3Uploader` class in `sleap_rtc/client/`
  - Initialize with config (backend URL, credentials)
  - Request multipart upload session
  - Split file into parts
  - Upload parts with retry logic
  - Progress callback interface
  - Complete multipart upload
- [ ] Implement resumable upload logic
  - Save upload state to local file (`.sleap-upload-state`)
  - Query S3 for completed parts on resume
  - Skip already-uploaded parts
  - Handle upload ID expiration
- [ ] Add progress tracking
  - Byte-level progress reporting
  - ETA calculation
  - Speed measurement (MB/s)
  - Integration with CLI progress bars (rich/tqdm)
- [ ] Add parallel part uploads
  - Configurable concurrency (default: 10)
  - Thread pool or asyncio for parallelization
  - Rate limiting to avoid overwhelming connection

**Validation:** Upload 1 GB test file, interrupt at 50%, resume successfully

---

### 2.2 Adaptive Transport Selection
- [ ] Create `TransportSelector` class
  - Analyze file size
  - Check data type (dataset, model, config)
  - Return recommended transport method
  - Log decision reasoning
- [ ] Update `client-train` command
  - Check dataset size before transfer
  - Use S3 upload if > threshold
  - Show user which transport will be used
  - Maintain backward compatibility (direct paths still work)
- [ ] Add `--force-transport` option
  - Allow user override (webrtc or s3)
  - Useful for testing
  - Document in help text

**Validation:** Run client-train with various dataset sizes, verify correct transport selected

---

### 2.3 Job Submission with S3 References
- [ ] Update job request message format
  - Add `dataset.type` field ("s3", "webrtc", "local")
  - Add `dataset.path` field (S3 path or local path)
  - Add `dataset.size_bytes` for worker planning
  - Add `dataset.checksum` for verification
- [ ] Update signaling server protocol (if needed)
  - Ensure peer_message can carry S3 references
  - Document new message format
  - Maintain backward compatibility
- [ ] Add job submission feedback
  - Confirm S3 upload before job submission
  - Show S3 path in CLI output
  - Handle upload failures gracefully

**Validation:** Submit job with S3 reference, verify worker receives correct S3 path

---

## Phase 3: Worker Download Implementation

### 3.1 S3 Download Worker Library
- [ ] Create `S3Downloader` class in `sleap_rtc/worker/`
  - Detect worker type (RunAI vs Desktop)
  - Download from S3 with retry logic
  - Progress reporting (for logging)
  - Checksum verification
- [ ] Implement caching strategy
  - Desktop workers: Save to `~/.sleap-rtc/cache/`
  - RunAI workers: Save to `/tmp/sleap-cache/`
  - Check cache before downloading
  - LRU eviction for desktop workers
- [ ] Add IAM role support
  - Detect IAM role availability (boto3 auto-discovery)
  - Fallback to presigned URLs if no IAM role
  - Document IAM configuration for RunAI

**Validation:** Worker downloads dataset from S3, verifies checksum, uses cached copy on second job

---

### 3.2 Update Worker Job Handler
- [ ] Modify `handle_training_job` to support S3 datasets
  - Check `dataset.type` field
  - If "s3": Download from S3
  - If "webrtc": Use existing WebRTC receive logic
  - If "local": Use local path (for testing)
- [ ] Add download progress logging
  - Log download start/completion
  - Log cache hits
  - Log errors with retry information
- [ ] Handle download failures
  - Retry with exponential backoff
  - Notify client via WebRTC if download fails
  - Clean up partial downloads

**Validation:** Worker successfully processes jobs with S3 datasets, handles network failures gracefully

---

## Phase 4: Room Storage Integration

### 4.1 Room Manifest Implementation
- [ ] Define room manifest schema (JSON)
  - `room_id`, `version`, `updated_at`
  - `models` dictionary (model_id -> metadata)
  - `aliases` dictionary (alias -> model_id)
  - Worker availability tracking
- [ ] Create `RoomStorage` class
  - Initialize with room_id and S3 backend
  - Download/parse manifest
  - Upload model files
  - Update manifest with optimistic locking (ETags)
- [ ] Implement manifest operations
  - `list_models()` - Query available models
  - `get_model(model_id)` - Get model metadata
  - `publish_model(model_id, metadata)` - Add/update model
  - `download_model(model_id)` - Download model files

**Validation:** Create room, publish model, query from different client, download model

---

### 4.2 Worker Model Upload
- [ ] Update worker training completion handler
  - Upload model files to room storage (S3)
  - Generate model metadata
  - Update room manifest
  - Handle manifest conflicts (retry with fresh ETag)
- [ ] Add worker type detection
  - Detect RunAI vs Desktop based on environment
  - RunAI: Upload immediately, don't advertise availability
  - Desktop: Upload and advertise as P2P source
- [ ] Implement upload retry logic
  - Retry on transient S3 errors
  - Validate uploaded files (checksums)
  - Clean up on failure

**Validation:** Train model on RunAI worker, verify model appears in room storage and manifest

---

### 4.3 Local Registry as Cache
- [ ] Repurpose `ClientModelRegistry` as cache
  - Add `cache_only` mode (doesn't persist)
  - Sync from room manifest periodically
  - Track last refresh time
  - Implement `refresh_from_room()` method
- [ ] Update model resolution logic
  - Check local cache first
  - Fallback to room storage query
  - Download from room storage if not in cache
  - Update cache after download

**Validation:** Client queries model, downloads from room storage, uses cache on second query

---

## Phase 5: Real-Time Progress (Maintain WebRTC)

### 5.1 Training Progress Streaming
- [ ] Verify existing WebRTC progress streaming still works
  - Epoch updates
  - Batch updates
  - GPU metrics
- [ ] Add S3 upload progress to WebRTC stream
  - Worker reports model upload progress
  - Client shows "Uploading model to room storage..."
  - Integration with existing progress UI
- [ ] Test progress streaming with S3 workflow
  - Dataset uploaded via S3
  - Progress still streams via WebRTC
  - Model upload progress visible

**Validation:** Run training job, verify real-time progress updates still work with S3 transport

---

### 5.2 Interactive Commands
- [ ] Verify interactive commands still work
  - Pause, resume, stop
  - Adjust learning rate
  - Request sample visualizations
- [ ] Add S3-specific commands (optional)
  - Check upload/download status
  - Cancel in-progress uploads
- [ ] Test command responsiveness
  - Low latency maintained (< 500ms)
  - Commands work during S3 operations

**Validation:** Pause training while dataset downloading from S3, verify pause works immediately

---

## Phase 6: Testing and Validation

### 6.1 Unit Tests
- [ ] Test `S3Uploader` class
  - Mock S3 API calls
  - Test multipart upload flow
  - Test resume logic
  - Test error handling
- [ ] Test `S3Downloader` class
  - Mock S3 downloads
  - Test caching logic
  - Test checksum verification
- [ ] Test `TransportSelector` class
  - Various file sizes
  - Edge cases (exactly at threshold)
- [ ] Test `RoomStorage` class
  - Manifest operations
  - Optimistic locking
  - Conflict resolution

**Validation:** `pytest tests/test_s3_transport.py` passes with > 90% coverage

---

### 6.2 Integration Tests
- [ ] Test end-to-end training workflow with S3
  - Client uploads dataset to S3
  - Worker downloads from S3
  - Training completes
  - Model uploaded to room storage
  - Client can query and download model
- [ ] Test resume capability
  - Interrupt upload at 50%
  - Resume successfully
  - Verify no duplicate parts uploaded
- [ ] Test failure scenarios
  - S3 service unavailable
  - Network interruption
  - Invalid credentials
  - Manifest conflicts
- [ ] Test with both worker types
  - RunAI worker (ephemeral)
  - Desktop worker (persistent)

**Validation:** All integration tests pass in CI/CD pipeline

---

### 6.3 Performance Testing
- [ ] Benchmark upload speeds
  - S3 multipart vs WebRTC chunking
  - Various file sizes (100 MB, 1 GB, 5 GB)
  - Various network conditions
- [ ] Measure reliability
  - Success rate over 100 uploads
  - Compare S3 vs WebRTC
  - Test under poor network conditions
- [ ] Measure cost efficiency
  - S3 egress vs TURN relay costs
  - P2P bandwidth savings (desktop workers)

**Validation:** Document performance improvements in benchmark report

---

## Phase 7: Documentation and Migration

### 7.1 User Documentation
- [ ] Update README with hybrid transport architecture
  - When S3 is used vs WebRTC
  - How to configure S3 buckets
  - How to set up IAM roles
- [ ] Create troubleshooting guide
  - Common S3 errors and solutions
  - Upload resume instructions
  - Credential configuration
- [ ] Add examples
  - Training with large datasets
  - Using room storage
  - Querying available models

**Validation:** New users can follow documentation to set up and use system

---

### 7.2 Migration Guide
- [ ] Document backward compatibility
  - Existing WebRTC workflows still work
  - No breaking changes to CLI
  - Optional S3 configuration
- [ ] Create migration checklist
  - Set up S3 buckets
  - Configure IAM roles
  - Update worker deployments
  - Update client configuration
- [ ] Provide rollback plan
  - How to disable S3 transport
  - Fallback to pure WebRTC mode

**Validation:** Existing users can migrate without workflow disruption

---

### 7.3 Monitoring and Observability
- [ ] Add S3 operation metrics
  - Upload success/failure rates
  - Download success/failure rates
  - Average upload/download times
  - Cost tracking (S3 API calls, storage, egress)
- [ ] Add CloudWatch/logging integration
  - Log all S3 operations
  - Alert on high error rates
  - Track unusual costs
- [ ] Create dashboard
  - Real-time transport statistics
  - Cost visualization
  - Error trends

**Validation:** Monitoring dashboard shows accurate metrics

---

## Dependencies

**Blocking dependencies:**
- Phase 2 depends on Phase 1 (need S3 infrastructure)
- Phase 3 depends on Phase 2 (need client upload working)
- Phase 4 depends on Phase 3 (need worker download working)
- Phase 5 depends on Phase 4 (need room storage working)

**Parallelizable work:**
- Phase 1.1 and 1.2 can be done in parallel (infrastructure vs backend)
- Phase 2.1 and 3.1 can be developed in parallel (client and worker)
- Phase 6.1 unit tests can be written alongside implementation

---

## Success Criteria

- [ ] Large file (> 1 GB) upload success rate > 99%
- [ ] Failed uploads can resume from checkpoint
- [ ] Real-time progress updates maintain < 500ms latency
- [ ] Bandwidth costs reduced by 40-70%
- [ ] Trained models persist after worker disconnect (100% retention)
- [ ] Both RunAI and Desktop workers work correctly
- [ ] Backward compatible with existing WebRTC workflows
- [ ] Complete documentation for users and operators

---

## Estimated Timeline

- Phase 1: 2 weeks (infrastructure setup)
- Phase 2: 2 weeks (client upload)
- Phase 3: 2 weeks (worker download)
- Phase 4: 2 weeks (room storage)
- Phase 5: 1 week (verify WebRTC integration)
- Phase 6: 2 weeks (testing)
- Phase 7: 1 week (documentation)

**Total: ~12 weeks for complete implementation**

**Minimum Viable Product (MVP): Phases 1-4 (~8 weeks)**
