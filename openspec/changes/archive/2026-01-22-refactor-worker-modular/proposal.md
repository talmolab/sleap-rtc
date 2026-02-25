# Refactor Worker into Modular Components

## Why

The `RTCWorkerClient` class in `sleap_rtc/worker/worker_class.py` has grown to ~2200 lines with too many responsibilities, making it difficult to maintain, test, and extend. This monolithic structure creates challenges for implementing the upcoming room-level registry feature with worker-to-worker mesh networking, as the class already handles 7+ distinct concerns in a single file.

## What Changes

- **BREAKING**: Refactor `RTCWorkerClient` into 7 specialized modules with single responsibilities
- Extract GPU detection and job compatibility logic to `WorkerCapabilities`
- Extract training/inference execution to `JobExecutor`
- Extract file transfer logic to `FileManager`
- Extract peer messaging logic to `JobCoordinator`
- Extract worker state and registration to `StateManager`
- Extract ZMQ progress reporting to `ProgressReporter`
- Retain WebRTC connection management in `RTCWorkerClient` as the orchestrator
- Maintain backward compatibility for public API (constructor args, `run_worker()` method)
- Update imports in client code and CLI entry points

## Impact

### Affected Specs
- **NEW**: `worker-capabilities` - GPU detection, job compatibility checking
- **NEW**: `worker-job-execution` - Training and inference workflow execution
- **NEW**: `worker-file-transfer` - File send/receive, compression, shared storage
- **NEW**: `worker-peer-messaging` - Peer-to-peer job coordination (v2.0 feature)
- **NEW**: `worker-state-management` - Status updates, room registration
- **NEW**: `worker-connection` - WebRTC connection lifecycle (existing logic, now documented)
- **NEW**: `worker-progress-reporting` - ZMQ-based progress streaming

### Affected Code
- `sleap_rtc/worker/worker_class.py` - Refactored into 7 modules (lines: 2200 → ~300)
- `sleap_rtc/worker/capabilities.py` - New module (~250 lines)
- `sleap_rtc/worker/job_executor.py` - New module (~700 lines)
- `sleap_rtc/worker/file_manager.py` - New module (~350 lines)
- `sleap_rtc/worker/job_coordinator.py` - New module (~450 lines)
- `sleap_rtc/worker/state_manager.py` - New module (~250 lines)
- `sleap_rtc/worker/progress_reporter.py` - New module (~150 lines)
- `sleap_rtc/cli/worker.py` - Update imports (minimal change)

### Migration Path
- Existing code using `from sleap_rtc.worker.worker_class import RTCWorkerClient` continues to work unchanged
- Internal implementation becomes modular, but public interface remains stable
- No changes required for client code or CLI usage
