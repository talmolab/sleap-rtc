# Design: Shared Filesystem Transfer

## Context

Currently, sleap-RTC transfers all training packages and results over WebRTC data channels using a chunked protocol (64KB chunks). For large files (5-9GB), this takes 15-30 minutes and consumes significant network bandwidth. Many deployment environments (Vast.ai, RunAI, Kubernetes, HPC clusters) provide shared filesystem access (NFS, CephFS, etc.) where Client and Worker can access the same physical storage, albeit at different mount points.

### Constraints
- Client runs on user's laptop (macOS): `/Volumes/talmo/amick`
- Worker runs in RunAI/Vast.ai container (Linux): `/home/jovyan/vast/amick`
- Same physical files, different absolute paths
- Must maintain backward compatibility for environments without shared storage
- Security: Must prevent path traversal attacks

### Stakeholders
- End users: Faster training job submission
- Infrastructure: Reduced network load
- Developers: Cleaner separation of transport mechanisms

## Goals / Non-Goals

### Goals
- Enable instant file sharing when shared storage is available
- Reduce 5GB transfer time from ~20 minutes to <1 minute
- Maintain backward compatibility with RTC transfer
- Support multiple shared filesystem types (NFS, Ceph, local volumes)
- Abstract filesystem operations using fsspec for future extensibility
- Provide clear error messages when paths are inaccessible

### Non-Goals
- Not replacing RTC transfer entirely (still needed for non-shared environments)
- Not implementing S3/cloud storage backends in this change (fsspec enables future extension)
- Not modifying existing message protocol for RTC transfer (runs in parallel)
- Not handling file synchronization/locking (assume filesystem handles it)

## Decisions

### Decision 1: Use Relative Paths for Cross-Platform Compatibility

**What**: Send relative paths over RTC instead of absolute paths.

**Why**: Client and Worker mount shared storage at different locations:
- Client: `/Volumes/talmo/amick/jobs/job_123/data.zip`
- Worker: `/home/jovyan/vast/amick/jobs/job_123/data.zip`

Sending absolute paths would fail. Instead, send `jobs/job_123/data.zip` and each side resolves against their mount point.

**Alternatives considered**:
- Send absolute paths + path mapping config: More complex, error-prone
- Use symbolic path like `//shared/`: Adds abstraction layer without benefit

**Implementation**:
```python
# Client sends
relative_path = file_path.relative_to(shared_root)
send(f"SHARED_INPUT_PATH::{relative_path}")

# Worker receives
absolute_path = worker_shared_root / relative_path
```

### Decision 2: Integrate fsspec for Filesystem Abstraction

**What**: Use fsspec library to abstract filesystem operations.

**Why**:
- Unified interface for local, NFS, S3, GCS, Azure, etc.
- Enables future cloud storage backends without code changes
- Better path handling and error messages
- Supports async operations for large files

**Alternatives considered**:
- Pure pathlib: Lacks abstraction, harder to extend
- Custom abstraction: Reinventing the wheel
- boto3/cloud SDKs directly: Couples to specific backend

**Implementation**:
```python
import fsspec

# Auto-detect filesystem type
fs = fsspec.filesystem('file')  # Local/NFS
# Future: fs = fsspec.filesystem('s3') for cloud

# Uniform operations
fs.exists(path)
fs.copy(src, dst)
fs.rm(path, recursive=True)
```

### Decision 3: Auto-Detection with Environment Variable Override

**What**: Automatically detect shared storage mount point, allow manual override.

**Why**:
- Zero configuration for common setups (Vast.ai, RunAI)
- Flexibility for custom deployments
- Fail-safe fallback to RTC transfer

**Priority**:
1. `SHARED_STORAGE_ROOT` environment variable (explicit)
2. Auto-detect from known mount points (Vast.ai, K8s patterns)
3. Fallback to RTC transfer if no shared storage found

**Implementation**:
```python
shared_root = os.getenv("SHARED_STORAGE_ROOT") or auto_detect() or None
if shared_root:
    use_shared_storage_transfer()
else:
    use_rtc_transfer()
```

### Decision 4: New Message Protocol for Path Sharing

**What**: Add new message types alongside existing RTC transfer protocol.

**Why**:
- Clean separation of concerns
- Backward compatible
- Easy to debug (text-based paths vs binary chunks)

**Message types**:
- `SHARED_INPUT_PATH::<relative_path>` - Client → Worker: Input file location
- `SHARED_OUTPUT_PATH::<relative_path>` - Client → Worker: Where to write results
- `PATH_VALIDATED::input|output` - Worker → Client: Path accessible
- `PATH_ERROR::<message>` - Worker → Client: Path issue

**Fallback protocol**:
If Worker responds with `PATH_ERROR`, Client falls back to RTC transfer automatically.

### Decision 5: Security - Validate Paths Within Shared Root

**What**: All paths must resolve within the shared storage root directory.

**Why**: Prevent path traversal attacks (`../../etc/passwd`).

**Implementation**:
```python
def validate_path(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
        return True
    except ValueError:
        raise SecurityError(f"Path {path} outside shared root {root}")
```

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ Client (MacBook)                                             │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ RTCClient                                                │ │
│ │ ┌──────────────────┐  ┌────────────────────────────────┐│ │
│ │ │ File Management  │  │ SharedStorageConfig            ││ │
│ │ │ - Detect mount   │  │ - Auto-detect mount point      ││ │
│ │ │ - Copy to shared │  │ - Path translation             ││ │
│ │ │ - Send rel path  │  │ - Validation                   ││ │
│ │ └────────┬─────────┘  └────────────┬───────────────────┘│ │
│ │          │                         │                     │ │
│ │          └─────────────┬───────────┘                     │ │
│ │                        │                                 │ │
│ │                ┌───────▼──────────┐                      │ │
│ │                │ FilesystemAdapter│                      │ │
│ │                │ (fsspec wrapper) │                      │ │
│ │                └───────┬──────────┘                      │ │
│ └────────────────────────┼───────────────────────────────┘ │
│                          │                                  │
└──────────────────────────┼──────────────────────────────────┘
                           │
                  Shared Filesystem
            (NFS, CephFS, Local Volume)
                           │
┌──────────────────────────┼──────────────────────────────────┐
│ Worker (RunAI Container) │                                  │
│ ┌────────────────────────┼───────────────────────────────┐ │
│ │ RTCWorkerClient        │                                │ │
│ │                ┌───────▼──────────┐                     │ │
│ │                │ FilesystemAdapter│                     │ │
│ │                │ (fsspec wrapper) │                     │ │
│ │                └───────┬──────────┘                     │ │
│ │                        │                                │ │
│ │          ┌─────────────┴───────────┐                    │ │
│ │          │                         │                    │ │
│ │ ┌────────▼─────────┐  ┌────────────▼───────────────┐   │ │
│ │ │ Path Receiver    │  │ SharedStorageConfig        │   │ │
│ │ │ - Receive path   │  │ - Resolve to abs path      │   │ │
│ │ │ - Validate       │  │ - Security checks          │   │ │
│ │ │ - Read direct    │  │                            │   │ │
│ │ └──────────────────┘  └────────────────────────────┘   │ │
│ └──────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. Client writes file to shared storage
   /Volumes/talmo/amick/jobs/job_123/training.zip

2. Client sends relative path via RTC
   "SHARED_INPUT_PATH::jobs/job_123/training.zip"

3. Worker resolves to absolute path
   /home/jovyan/vast/amick/jobs/job_123/training.zip

4. Worker validates path exists and is within root
   ✓ Path valid

5. Worker sends confirmation
   "PATH_VALIDATED::input"

6. Worker reads file directly (instant!)
   process_file(/home/jovyan/vast/amick/jobs/job_123/training.zip)

7. Worker writes results to shared storage
   /home/jovyan/vast/amick/jobs/job_123/output/model.zip

8. Worker sends relative output path
   "JOB_COMPLETE::jobs/job_123/output"

9. Client reads results directly
   /Volumes/talmo/amick/jobs/job_123/output/model.zip
```

### File Structure

```
sleap_rtc/
├── config.py              # Add SharedStorageConfig class
├── filesystem.py          # NEW: fsspec wrapper and utilities
├── client/
│   └── client_class.py    # Modify: Add shared storage detection
└── worker/
    └── worker_class.py    # Modify: Add path validation and reading
```

## fsspec Integration Details

### Why fsspec?

fsspec (Filesystem Spec) provides:
1. **Unified interface** across local, NFS, S3, GCS, Azure, etc.
2. **Path handling** that works across platforms
3. **Caching** for remote filesystems
4. **Async support** for I/O-bound operations
5. **Future-proof** for cloud storage backends

### Implementation Pattern

```python
# filesystem.py
import fsspec
from pathlib import Path
from typing import Optional

class FilesystemAdapter:
    """Unified filesystem interface using fsspec."""

    def __init__(self, protocol: str = "file", **kwargs):
        """
        Initialize filesystem adapter.

        Args:
            protocol: Filesystem type ('file', 's3', 'gcs', etc.)
            **kwargs: Protocol-specific options
        """
        self.fs = fsspec.filesystem(protocol, **kwargs)
        self.protocol = protocol

    def exists(self, path: str | Path) -> bool:
        """Check if path exists."""
        return self.fs.exists(str(path))

    def copy(self, src: str | Path, dst: str | Path) -> None:
        """Copy file with progress tracking."""
        self.fs.copy(str(src), str(dst))

    def mkdir(self, path: str | Path, create_parents: bool = True) -> None:
        """Create directory."""
        self.fs.makedirs(str(path), exist_ok=True)

    def rm(self, path: str | Path, recursive: bool = False) -> None:
        """Remove file or directory."""
        self.fs.rm(str(path), recursive=recursive)

    def info(self, path: str | Path) -> dict:
        """Get file metadata (size, mtime, etc.)."""
        return self.fs.info(str(path))

    def ls(self, path: str | Path, detail: bool = False) -> list:
        """List directory contents."""
        return self.fs.ls(str(path), detail=detail)

    @classmethod
    def from_path(cls, path: str | Path) -> "FilesystemAdapter":
        """
        Auto-detect filesystem type from path.

        Examples:
            /path/to/file -> file://
            s3://bucket/key -> s3://
        """
        path_str = str(path)
        if "://" in path_str:
            protocol = path_str.split("://")[0]
        else:
            protocol = "file"

        return cls(protocol=protocol)
```

### Usage in Client/Worker

```python
# Client
from sleap_rtc.filesystem import FilesystemAdapter

class RTCClient:
    def __init__(self):
        self.shared_root = Path("/Volumes/talmo/amick")
        self.fs = FilesystemAdapter(protocol="file")

    def send_file_via_shared_storage(self, local_file: Path):
        job_dir = self.shared_root / "jobs" / job_id
        self.fs.mkdir(job_dir)

        # Copy to shared storage
        shared_file = job_dir / local_file.name
        self.fs.copy(local_file, shared_file)

        # Send relative path
        relative = shared_file.relative_to(self.shared_root)
        self.send_message(f"SHARED_INPUT_PATH::{relative}")
```

## Risks / Trade-offs

### Risk: Mount Point Misconfiguration
**Mitigation**:
- Auto-detection with known patterns
- Clear error messages if detection fails
- Fallback to RTC transfer
- Test script to validate mount points

### Risk: Filesystem Permissions
**Mitigation**:
- Document required permissions (read/write)
- Validate access during initialization
- Graceful degradation to RTC transfer

### Risk: Path Traversal Attacks
**Mitigation**:
- Strict path validation (must be within shared root)
- Use `Path.resolve()` to expand symlinks
- Reject paths with `..` components

### Risk: Concurrent Access Issues
**Mitigation**:
- Use unique job IDs for directories
- Filesystem handles file locking (NFS, etc.)
- Document that shared filesystem must support concurrent access

### Trade-off: Complexity vs Performance
- **Added complexity**: Path translation, filesystem abstraction
- **Gain**: 10-20x faster transfers for large files
- **Verdict**: Worth it for significant performance improvement

### Trade-off: fsspec Dependency
- **Pro**: Industry-standard library, well-maintained
- **Pro**: Enables future cloud storage without code changes
- **Con**: Additional dependency (~500KB)
- **Verdict**: Acceptable for benefits gained

## Migration Plan

### Phase 1: Add Shared Storage Support (Non-Breaking)
1. Add `fsspec` to dependencies
2. Implement `SharedStorageConfig` with auto-detection
3. Implement `FilesystemAdapter` wrapper
4. Add new message handlers without breaking existing RTC transfer
5. Add `--shared-storage-root` CLI flag (optional)

### Phase 2: Update Client
1. Detect shared storage on initialization
2. If detected, use shared storage transfer
3. If not detected or path fails, fallback to RTC transfer
4. Log which method is being used

### Phase 3: Update Worker
1. Handle new `SHARED_INPUT_PATH` messages
2. Validate paths and send `PATH_VALIDATED` or `PATH_ERROR`
3. Read files directly from shared storage
4. Maintain compatibility with RTC transfer messages

### Phase 4: Testing & Validation
1. Unit tests for path validation
2. Integration tests with Docker volumes
3. Test with RunAI/Vast.ai environments
4. Document mount point configuration

### Rollback Strategy
- Change is additive (new message types)
- Fallback to RTC transfer if any shared storage operation fails
- Can disable via `SHARED_STORAGE_ROOT=""` environment variable
- No data loss risk (files remain on shared storage)

## Open Questions

1. **Q**: Should we implement file locking for concurrent access?
   **A**: Not in this change. Assume filesystem handles it. Add if needed in future.

2. **Q**: Should we add checksum validation for shared storage files?
   **A**: Not critical since filesystem integrity is assumed. Could add as enhancement.

3. **Q**: Should we support multiple shared storage roots?
   **A**: Not in this change. Single root is sufficient for current use cases.

4. **Q**: Should we implement cleanup of old job directories?
   **A**: Out of scope. Can be separate change for lifecycle management.

5. **Q**: How to handle mixed environments (some workers with shared storage, others without)?
   **A**: Each worker advertises capability via metadata. Client selects appropriate transfer method per worker. Enhancement for future.
