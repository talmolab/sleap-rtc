# Design: Storage Backend Abstraction

## Context

The current shared filesystem implementation uses a single `SHARED_STORAGE_ROOT` per machine. This works for simple cases but fails in multi-user environments where:

1. **Different users have different storage paths**: Sam uses `/Volumes/talmo/sam`, Tom uses `/Volumes/talmo/tom`
2. **Different machines have different mount points**: Mac mounts at `/Volumes/talmo`, Run:AI mounts at `/home/jovyan/vast`
3. **Multiple storage backends exist**: Institutional VAST, personal Google Drive, local scratch

### The Core Problem

```
Current: Workers are user-specific
┌─────────────────┐      ┌─────────────────┐
│ Worker 1        │      │ Worker 2        │
│ ROOT=/vast/sam  │      │ ROOT=/vast/tom  │
│ Can only serve  │      │ Can only serve  │
│ Sam's jobs      │      │ Tom's jobs      │
└─────────────────┘      └─────────────────┘

Desired: Workers are anonymous compute
┌─────────────────┐      ┌─────────────────┐
│ Worker 1        │      │ Worker 2        │
│ BASE=/vast      │      │ BASE=/vast      │
│ Can serve ANY   │      │ Can serve ANY   │
│ user's jobs     │      │ user's jobs     │
└─────────────────┘      └─────────────────┘
```

### Stakeholders

- **End users**: Can use any available worker, not just "their" worker
- **Lab administrators**: Better resource utilization across worker pool
- **Developers**: Cleaner separation between storage and compute

## Goals / Non-Goals

### Goals

- Enable anonymous compute: any worker can serve any user's job
- Support multiple storage backends per machine (vast, gdrive, scratch)
- Handle different mount points across platforms (Mac, Linux, containers)
- Maintain backward compatibility with single `SHARED_STORAGE_ROOT` config
- Enable job routing based on storage backend availability

### Non-Goals

- Not implementing cloud storage protocols (S3, GCS) in this change
- Not implementing storage quotas or usage tracking
- Not handling storage authentication (assume pre-configured mounts)
- Not implementing file synchronization between backends

## Decisions

### Decision 1: Logical Backend Names with Per-Machine Path Mapping

**What**: Use logical names (`vast`, `gdrive`, `scratch`) that map to different local paths on each machine.

**Why**: The same physical storage appears at different paths on different machines:
- Mac: `vast` → `/Volumes/talmo`
- Linux worker: `vast` → `/mnt/vast`
- Run:AI container: `vast` → `/home/jovyan/vast`

Using logical names decouples the application from filesystem specifics.

**Alternatives considered**:
- Absolute paths in job requests: Fails across different mount points
- Path translation tables: More complex, error-prone
- Standardize mount points everywhere: Not always possible (containers, etc.)

**Implementation**:
```toml
# Mac client config
[storage.vast]
base_path = "/Volumes/talmo"

# Run:AI worker config
[storage.vast]
base_path = "/home/jovyan/vast"
```

```python
# Client sends logical reference
job = {
    "storage_backend": "vast",
    "user_subdir": "amick",
    "input_file": "project/labels.slp"
}

# Worker resolves to local path
# /home/jovyan/vast + /amick + /project/labels.slp
```

### Decision 2: User Subdirectory in Job Request (Not Worker Config)

**What**: The job request specifies which user's subdirectory to use, not the worker configuration.

**Why**: This is the key change that enables anonymous compute. Workers configure the base mount; jobs specify the user context.

**Current approach** (problematic):
```python
# Worker config includes user path - ties worker to user
SHARED_STORAGE_ROOT = "/Volumes/talmo/sam"
```

**New approach**:
```python
# Worker config is user-agnostic
storage.vast.base_path = "/Volumes/talmo"

# Job specifies user
job.user_subdir = "sam"

# Path constructed dynamically
path = f"{storage.vast.base_path}/{job.user_subdir}/{job.relative_path}"
```

### Decision 3: Worker Capability Advertisement

**What**: Workers announce which storage backends they have access to when they connect.

**Why**: Enables intelligent job routing - jobs requiring `vast` storage go to workers that have `vast` configured.

**Implementation**:
```python
# Worker announces on connection
{
    "type": "worker_announce",
    "worker_id": "gpu-worker-1",
    "capabilities": {
        "gpu": "A100",
        "storage_backends": ["vast", "scratch"]
    }
}

# Job request includes required storage
{
    "required_storage": "vast",
    ...
}

# Signaling server / room admin routes accordingly
```

### Decision 4: Graceful Fallback Chain

**What**: If shared storage is unavailable, fall back gracefully.

**Priority order**:
1. Use requested storage backend if both client and worker have it
2. If worker lacks backend, fall back to RTC transfer
3. If RTC transfer fails, report error

**Why**: Maintains compatibility with environments without shared storage.

```python
if worker.has_backend(job.storage_backend):
    # Use shared storage (fast)
    path = worker.resolve_path(job.storage_backend, job.user_subdir, job.input_file)
    data = read_file(path)
else:
    # Fall back to RTC transfer (slow but works everywhere)
    await request_rtc_transfer(job.input_file)
```

### Decision 5: Backward Compatibility with SHARED_STORAGE_ROOT

**What**: The existing `SHARED_STORAGE_ROOT` environment variable continues to work.

**Why**: Don't break existing deployments.

**Behavior**:
- If `SHARED_STORAGE_ROOT` is set and no `[storage.*]` config exists, create a default backend named `default`
- Jobs without explicit `storage_backend` use `default`
- Existing code paths continue to work

```python
# Legacy environment variable
SHARED_STORAGE_ROOT="/Volumes/talmo/amick"

# Equivalent to:
[storage.default]
base_path = "/Volumes/talmo/amick"
# Note: user_subdir would be empty for legacy mode
```

## Architecture

### Configuration Schema

```toml
# sleap-rtc.toml

# Multiple storage backends
[storage.vast]
type = "nfs"                          # Optional: nfs, local, google_drive
base_path = "/home/jovyan/vast"       # Required: where it's mounted
description = "Institutional VAST storage"  # Optional: for UI/logs

[storage.scratch]
type = "local"
base_path = "/scratch"
description = "Fast local SSD"

[storage.gdrive]
type = "google_shared_drive"
base_path = "/mnt/gdrive-lab"
description = "Lab shared Google Drive"
```

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT (Mac)                                │
│                                                                     │
│  ┌─────────────────┐    ┌──────────────────────────────────────┐   │
│  │ Job Request     │    │ StorageConfig                        │   │
│  │                 │    │                                      │   │
│  │ storage_backend │    │ backends:                            │   │
│  │ user_subdir     │───▶│   vast: /Volumes/talmo               │   │
│  │ input_file      │    │   gdrive: ~/Google Drive/Lab         │   │
│  └─────────────────┘    └──────────────────────────────────────┘   │
│           │                              │                          │
│           │              ┌───────────────┘                          │
│           │              ▼                                          │
│           │     ┌────────────────────┐                              │
│           │     │ StorageResolver    │                              │
│           │     │ vast + amick +     │                              │
│           │     │ project/data.slp   │                              │
│           │     │ = /Volumes/talmo/  │                              │
│           │     │   amick/project/   │                              │
│           │     │   data.slp         │                              │
│           │     └────────────────────┘                              │
│           │                                                         │
└───────────┼─────────────────────────────────────────────────────────┘
            │
            │ RTC Message:
            │ {
            │   "storage_backend": "vast",
            │   "user_subdir": "amick",
            │   "input_file": "project/data.slp"
            │ }
            │
            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     WORKER (Run:AI Container)                       │
│                                                                     │
│  ┌─────────────────┐    ┌──────────────────────────────────────┐   │
│  │ Receive Job     │    │ StorageConfig                        │   │
│  │                 │    │                                      │   │
│  │ storage_backend │    │ backends:                            │   │
│  │ user_subdir     │───▶│   vast: /home/jovyan/vast            │   │
│  │ input_file      │    │   scratch: /scratch                  │   │
│  └─────────────────┘    └──────────────────────────────────────┘   │
│           │                              │                          │
│           │              ┌───────────────┘                          │
│           │              ▼                                          │
│           │     ┌────────────────────┐                              │
│           │     │ StorageResolver    │                              │
│           │     │ vast + amick +     │                              │
│           │     │ project/data.slp   │                              │
│           │     │ = /home/jovyan/    │                              │
│           │     │   vast/amick/      │                              │
│           │     │   project/data.slp │                              │
│           │     └────────────────────┘                              │
│           │              │                                          │
│           │              ▼                                          │
│           │     ┌────────────────────┐                              │
│           │     │ File Access        │                              │
│           │     │ Read/Write same    │                              │
│           │     │ physical files!    │                              │
│           │     └────────────────────┘                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow: Job Submission

```
1. Client prepares job
   - Copies files to shared storage (if needed)
   - Determines: backend=vast, user=amick, file=project/labels.slp
   - Client's resolved path: /Volumes/talmo/amick/project/labels.slp

2. Client sends job request via RTC
   {
     "type": "JOB_REQUEST",
     "storage_backend": "vast",
     "user_subdir": "amick",
     "input_file": "project/labels.slp",
     "output_dir": "project/models"
   }

3. Worker receives job
   - Checks: do I have "vast" backend? YES
   - Resolves: /home/jovyan/vast + amick + project/labels.slp
   - Worker's path: /home/jovyan/vast/amick/project/labels.slp

4. Worker validates path
   - File exists? YES
   - Within base_path? YES (security check)
   - Sends: PATH_VALIDATED

5. Worker runs training
   - Reads from: /home/jovyan/vast/amick/project/labels.slp
   - Writes to: /home/jovyan/vast/amick/project/models/

6. Worker sends completion
   {
     "type": "JOB_COMPLETE",
     "output_path": "project/models/best_model.pt"
   }

7. Client accesses results
   - Resolves: /Volumes/talmo/amick/project/models/best_model.pt
   - File already there (same physical storage)!
```

### Class Design

```python
# sleap_rtc/config.py

@dataclass
class StorageBackend:
    """Configuration for a single storage backend."""
    name: str                    # Logical name: "vast", "gdrive", etc.
    base_path: Path              # Local mount point
    type: str = "local"          # nfs, local, google_drive, etc.
    description: str = ""        # Human-readable description

    def resolve_path(self, user_subdir: str, relative_path: str) -> Path:
        """Resolve a logical path to absolute local path."""
        return self.base_path / user_subdir / relative_path


class StorageConfig:
    """Manages multiple storage backends."""

    backends: Dict[str, StorageBackend]

    @classmethod
    def from_toml(cls, config_data: dict) -> "StorageConfig":
        """Load from TOML config data."""
        backends = {}
        for name, settings in config_data.get("storage", {}).items():
            backends[name] = StorageBackend(
                name=name,
                base_path=Path(settings["base_path"]),
                type=settings.get("type", "local"),
                description=settings.get("description", "")
            )
        return cls(backends=backends)

    def has_backend(self, name: str) -> bool:
        """Check if backend is configured."""
        return name in self.backends

    def resolve_path(
        self,
        backend_name: str,
        user_subdir: str,
        relative_path: str
    ) -> Path:
        """Resolve logical path to absolute local path."""
        if backend_name not in self.backends:
            raise StorageBackendNotFound(f"Backend '{backend_name}' not configured")
        return self.backends[backend_name].resolve_path(user_subdir, relative_path)

    def list_backends(self) -> List[str]:
        """List available backend names."""
        return list(self.backends.keys())
```

## Risks / Trade-offs

### Risk: Inconsistent Backend Naming Across Machines

**Problem**: The same physical storage is configured with different names on different machines (client calls it `vast`, worker calls it `institutional-storage`).

**Why this is low risk**: Clients select backends from the worker's advertised list. If names don't match, the client simply won't see that backend as available - it will fall back to RTC transfer or choose a different worker.

**Mitigation**:
- Document standard backend names for common setups (e.g., "vast" for institutional VAST storage)
- Provide example configurations for common environments
- Clear logging when a backend is configured: "Registered storage backend 'vast' at /home/jovyan/vast"

### Risk: User Subdirectory Doesn't Exist

**Problem**: Job specifies `user_subdir=amick` but `/home/jovyan/vast/amick` doesn't exist on worker.

**Mitigation**:
- Path validation before job execution
- Clear error: "User directory 'amick' not found in backend 'vast'"
- Option to create user directory on first job (configurable)

### Risk: Security - Path Traversal

**Problem**: Malicious job sends `user_subdir=../../../etc` to escape base_path.

**Mitigation**:
- Strict path validation using `resolve()` and `relative_to()`
- Reject paths containing `..`
- All resolved paths must be within `base_path`

```python
def validate_path(self, resolved: Path) -> None:
    try:
        resolved.resolve().relative_to(self.base_path.resolve())
    except ValueError:
        raise SecurityError(f"Path escapes base directory")
```

### Risk: Complexity Increase

**Trade-off**: More configuration options vs. flexibility.

**Mitigation**:
- Backward compatibility: single `SHARED_STORAGE_ROOT` still works
- Sensible defaults: if no storage configured, use RTC transfer
- Clear documentation with examples for common setups

### Trade-off: Logical Names vs. Direct Paths

**Pro logical names**:
- Platform-independent job definitions
- Easier debugging ("job uses vast" vs. "/home/jovyan/vast")
- Enables backend capabilities matching

**Con logical names**:
- Additional configuration layer
- Names must match between client and worker

**Verdict**: Logical names are worth it for multi-platform support.

## Migration Plan

### Phase 1: Add Storage Backend Configuration (Non-Breaking)

1. Add `StorageBackend` and `StorageConfig` classes to `config.py`
2. Add `[storage.*]` section parsing to TOML loader
3. Maintain support for existing `SHARED_STORAGE_ROOT` as `default` backend
4. No changes to protocol or client/worker behavior yet

### Phase 2: Add Worker Capability Advertisement

1. Worker sends available backends in registration message
2. Signaling server tracks worker storage capabilities
3. No changes to job routing yet (preparation for Phase 4)

### Phase 3: Add Storage Fields to Job Protocol

1. Add `storage_backend`, `user_subdir` to job request messages
2. Worker resolves paths using new config
3. Backward compatibility: if fields missing, use legacy behavior

### Phase 4: Add Job Routing by Storage

1. Client specifies required storage backend
2. Signaling server / room admin routes to capable workers
3. Fallback to RTC transfer if no worker has required backend

### Rollback Strategy

- Each phase is independently revertable
- Legacy `SHARED_STORAGE_ROOT` behavior preserved
- Jobs without new fields use existing code paths
- Feature flags can disable new behavior

## Open Questions

1. **Q**: Should we support wildcards in backend matching (e.g., job requests "any-nfs" matches "vast", "lab-nfs")?
   **A**: Not in initial implementation. Exact matching is clearer. Can add later if needed.

2. **Q**: Should workers auto-discover storage backends from mount points?
   **A**: No. Explicit configuration is more reliable and secure. Users know what storage they have.

3. **Q**: How to handle storage backends that require authentication (Google Drive personal)?
   **A**: Out of scope for this change. Assume storage is pre-authenticated/mounted. Document that personal drives have limitations.

4. **Q**: Should we add storage health checks (is backend responsive)?
   **A**: Good enhancement for future. Initial implementation assumes mounts are working.
