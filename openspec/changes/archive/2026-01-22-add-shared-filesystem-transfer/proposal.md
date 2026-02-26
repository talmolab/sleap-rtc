# Proposal: Add Shared Filesystem Transfer

## Why

Current WebRTC data channel file transfers are inefficient for large training packages (5-9GB), taking 15-30 minutes to upload and download. When Client and Worker have access to a shared filesystem (e.g., Vast.ai NFS, Kubernetes PVC), transferring files over RTC is unnecessary. Instead, the Client can write files to shared storage and send just the path to the Worker, enabling instant access to large files.

This change eliminates the network bottleneck for large file transfers while maintaining backward compatibility with the existing RTC transfer mechanism for environments without shared storage.

## What Changes

- Add shared filesystem support as the primary file transfer method when available
- **BREAKING**: Modify Client and Worker to detect and use shared storage mounts
- Add path translation layer to handle different mount points (Client: `/Volumes/talmo/amick`, Worker: `/home/jovyan/vast/amick`)
- Integrate fsspec library for uniform filesystem abstraction across local, NFS, and cloud storage
- Add new RTC message types for sharing file paths instead of binary data:
  - `SHARED_INPUT_PATH::` - Send input file location
  - `SHARED_OUTPUT_PATH::` - Send output directory location
  - `PATH_VALIDATED::` - Confirm path accessibility
  - `PATH_ERROR::` - Report path issues
- Add configuration layer for mount point detection and path resolution
- Maintain fallback to existing RTC chunked transfer for environments without shared storage
- Add validation and security checks for path traversal prevention

## Impact

- **Affected specs**: file-transfer (new), client (modified), worker (modified)
- **Affected code**:
  - `sleap_rtc/client/client_class.py` - Add shared storage detection and path sending
  - `sleap_rtc/worker/worker_class.py` - Add path reception and validation
  - `sleap_rtc/config.py` - Add SharedStorageConfig class
  - `sleap_rtc/cli.py` - Add optional `--shared-storage-root` flag
  - New: `sleap_rtc/filesystem.py` - fsspec integration and path utilities
- **Performance impact**: Reduces 5GB file transfer from ~15-30 minutes to <1 minute (local copy + path send)
- **User experience**: Users on Vast.ai or similar platforms with shared storage see immediate speed improvements
- **Deployment**: No infrastructure changes required; automatically detects and uses shared storage when available
- **Testing**: Requires integration tests with mounted volumes to validate cross-container access
