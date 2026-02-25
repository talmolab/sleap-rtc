# Design: Simplify Worker I/O Paths

## Overview

This design replaces the complex storage backend abstraction with a simple worker I/O path model. Each worker configures where it reads inputs and writes outputs, and advertises these paths to clients.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CONFIGURATION                                │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  sleap-rtc.toml (Worker)                                            │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ [worker.io]                                                  │    │
│  │ input_path = "/mnt/shared/inputs"                           │    │
│  │ output_path = "/mnt/shared/outputs"                         │    │
│  │ filesystem = "vast"  # Human-readable label                 │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         WORKER STARTUP                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. Load WorkerIOConfig from config                                  │
│  2. Validate paths exist and are accessible                          │
│  3. Add to WorkerCapabilities metadata                               │
│  4. Advertise in registration message                                │
│                                                                      │
│  Registration Metadata:                                              │
│  {                                                                   │
│    "gpu_model": "NVIDIA A100",                                       │
│    "gpu_memory_mb": 40960,                                           │
│    "io_paths": {                                                     │
│      "input": "/mnt/shared/inputs",                                  │
│      "output": "/mnt/shared/outputs",                                │
│      "filesystem": "vast"                                            │
│    }                                                                 │
│  }                                                                   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT WORKFLOW                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. User runs: sleap-rtc client-train --pkg_path training.zip       │
│                                                                      │
│  2. Client discovers workers and displays:                           │
│     ┌─────────────────────────────────────────────────────────┐     │
│     │ Available Workers:                                       │     │
│     │                                                          │     │
│     │ 1. worker-abc (A100, 40GB)                              │     │
│     │    Filesystem: vast                                      │     │
│     │    Input:  /mnt/shared/inputs  <- Put your file here    │     │
│     │    Output: /mnt/shared/outputs                          │     │
│     └─────────────────────────────────────────────────────────┘     │
│                                                                      │
│  3. User copies file to input path (manual step)                     │
│     $ cp training.zip /mnt/shared/inputs/                           │
│                                                                      │
│  4. User selects worker                                              │
│                                                                      │
│  5. Client sends: INPUT_FILE::training.zip                          │
│                                                                      │
│  6. Worker validates: /mnt/shared/inputs/training.zip exists        │
│                                                                      │
│  7. Worker responds: FILE_EXISTS::training.zip                      │
│                                                                      │
│  8. Training proceeds...                                             │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         JOB OUTPUT                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  /mnt/shared/outputs/                                                │
│  └── jobs/                                                           │
│      └── job_abc123/                                                 │
│          ├── models/                                                 │
│          │   ├── centroid/                                          │
│          │   │   └── best_model.pt                                  │
│          │   └── centered_instance/                                 │
│          │       └── best_model.pt                                  │
│          └── logs/                                                   │
│              └── training.log                                        │
│                                                                      │
│  Job completion message includes output path so user knows          │
│  where to find results.                                              │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Protocol Messages

### New Messages

| Message | Direction | Purpose |
|---------|-----------|---------|
| `INPUT_FILE::{filename}` | Client → Worker | Specify input file (filename only) |
| `FILE_EXISTS::{filename}` | Worker → Client | Confirm file found in input path |
| `FILE_NOT_FOUND::{filename}::{reason}` | Worker → Client | File not found or not accessible |
| `JOB_OUTPUT::{job_id}::{path}` | Worker → Client | Report output location on completion |

### Removed Messages (from complex proposal)

| Message | Reason for Removal |
|---------|-------------------|
| `STORAGE_BACKEND::` | No longer needed - single I/O path per worker |
| `USER_SUBDIR::` | No longer needed - user places file directly |
| `BACKEND_NOT_AVAILABLE::` | No longer needed - no backend selection |

## Configuration

### Worker Configuration

```toml
# sleap-rtc.toml

[worker.io]
# Required: Where worker looks for input files
input_path = "/mnt/shared/inputs"

# Required: Where worker writes job outputs
output_path = "/mnt/shared/outputs"

# Optional: Human-readable filesystem label for display
filesystem = "vast"
```

### CLI Overrides

```bash
# Override config with CLI flags
sleap-rtc worker --input-path /custom/inputs --output-path /custom/outputs
```

## Transfer Modes (Two Options Only)

This change implements a **clean cutover** - no dual support with the old `SHARED_STORAGE_ROOT` system.

### Mode 1: Worker I/O Paths (Primary)
When worker has I/O paths configured:
1. Worker registers with `io_paths` in metadata
2. Client displays paths to user
3. User places file in worker's input path
4. Client sends filename only
5. Worker resolves and validates

### Mode 2: RTC Transfer (Fallback)
When worker has NO I/O paths configured:
1. Worker registers without `io_paths` in metadata
2. Client detects missing I/O paths
3. Client uses RTC chunked file transfer (existing behavior)
4. File is transferred directly over WebRTC data channel

### Removed: SHARED_STORAGE_ROOT
The old `SHARED_STORAGE_ROOT` auto-copy behavior is **completely removed**:
- No `SHARED_STORAGE_ROOT` environment variable
- No `--shared-storage-root` CLI flag
- No `send_file_via_shared_storage()` method
- No `SHARED_INPUT_PATH::` / `SHARED_OUTPUT_PATH::` messages

## Security Considerations

1. **Path Validation**: Worker validates that resolved path is within `input_path`
   - Prevents path traversal: `INPUT_FILE::../../../etc/passwd` → rejected

2. **No User Input in Paths**: Worker constructs full path internally
   - User sends filename only, not full path
   - Worker: `resolved = input_path / filename`

3. **Permission Checks**: Worker validates read permission before confirming file exists

## Trade-offs

### Pros
- **Simplicity**: Two paths vs. complex backend abstraction
- **User Control**: User explicitly places files, no magic
- **Transparency**: User sees exactly where files go
- **Debuggability**: Easy to verify file placement manually

### Cons
- **Manual Step**: User must copy file to input path
- **No Automatic Detection**: Client doesn't know if user has access to filesystem
- **Single Path**: One input/output location per worker (not multiple backends)

### Why This Trade-off is Acceptable

1. **Target Users**: Power users who understand their infrastructure
2. **Realistic Assumption**: Most setups have ONE shared filesystem, not many
3. **Failure Mode**: If file isn't there, clear error message tells user what to do
4. **Future Extension**: Can add optional auto-copy if needed later

## Migration Path

**This is a breaking change.** Users must update their configuration.

### Before (Old Config)
```toml
# Environment variable or config
SHARED_STORAGE_ROOT=/mnt/shared/amick

# Or complex storage backends
[storage.vast]
base_path = "/mnt/vast"
```

### After (New Config)
```toml
[worker.io]
input_path = "/mnt/shared/inputs"
output_path = "/mnt/shared/outputs"
filesystem = "vast"
```

### Migration Steps
1. Update worker config to use `[worker.io]` section
2. Remove `SHARED_STORAGE_ROOT` environment variable
3. Deploy updated workers
4. Users place files directly in worker's input_path
5. Archive/close `add-storage-backend-abstraction` and `add-shared-filesystem-transfer` proposals
