# Design: Resolve SLP Video Paths

## Context

### Problem
SLP files embed absolute video paths that become invalid when the file moves between machines. Example:
- Client path: `/Users/amickl/Google Drive/project/exp1/video1.mp4`
- Worker path: `/mnt/vast/datasets/project/exp1/video1.mp4`

### Constraints
- Videos are on shared storage accessible to both Client and Worker (different mount points)
- Cannot embed video frames - `pkg.slp` doesn't scale for multi-hour experiments
- Must preserve original SLP file (create new corrected copy)
- Worker must have `sleap-io` available for SLP manipulation

### Prior Art
- **SLP Viewer** (vibes.tlab.sh): Uses filename-based directory scanning
  - User clicks "Load Directory"
  - System scans directory for files matching video filenames
  - Simple and effective for typical use cases

## Goals / Non-Goals

### Goals
- Automatically detect missing videos after SLP path resolution
- Provide web UI for resolving video paths (similar to SLP Viewer)
- Scan directories for matching filenames when user selects a video
- Reuse existing filesystem browser infrastructure
- Write corrected SLP using sleap-io

### Non-Goals
- Video file transfer (assumes shared storage)
- TUI-based resolution (deferred)
- Complex prefix inference algorithms (use simple directory scanning instead)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ Training Flow with Auto-Detection                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  client-train                         Worker                                │
│      │                                   │                                  │
│      ├── Resolve SLP path ──────────────►│                                  │
│      │                                   ├── Load SLP with sleap-io         │
│      │                                   ├── Check each video.filename      │
│      │◄── FS_CHECK_VIDEOS_RESPONSE ──────┤   exists on filesystem           │
│      │    {missing: ["video1.mp4", ...]} │                                  │
│      │                                   │                                  │
│  [If missing videos detected]            │                                  │
│      │                                   │                                  │
│      ├── Launch /resolve UI              │                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ Resolution UI Flow (SLP Viewer Style)                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Browser (/resolve)                   Worker                                │
│      │                                   │                                  │
│      │  ┌─────────────────────────────┐  │                                  │
│      │  │ Missing Videos              │  │                                  │
│      │  │ ❌ video1.mp4               │  │                                  │
│      │  │ ❌ video2.mp4               │  │                                  │
│      │  │ ❌ video3.mp4               │  │                                  │
│      │  └─────────────────────────────┘  │                                  │
│      │                                   │                                  │
│      │  User browses filesystem,         │                                  │
│      │  selects video1.mp4 at:           │                                  │
│      │  /mnt/vast/datasets/project/      │                                  │
│      │                                   │                                  │
│      ├── FS_SCAN_DIR ───────────────────►│                                  │
│      │   {dir: "/mnt/vast/.../project/", │                                  │
│      │    filenames: ["video2.mp4",      │                                  │
│      │                "video3.mp4"]}     │                                  │
│      │                                   ├── Scan directory for filenames   │
│      │◄── FS_SCAN_DIR_RESPONSE ──────────┤                                  │
│      │   {found: {"video2.mp4": "/mnt/...", │                               │
│      │            "video3.mp4": null}}   │  (null = not found)              │
│      │                                   │                                  │
│      │  ┌─────────────────────────────┐  │                                  │
│      │  │ Missing Videos              │  │                                  │
│      │  │ ✅ video1.mp4 (resolved)    │  │                                  │
│      │  │ ✅ video2.mp4 (auto-found)  │  │                                  │
│      │  │ ❌ video3.mp4 (not in dir)  │  │                                  │
│      │  └─────────────────────────────┘  │                                  │
│      │                                   │                                  │
│      │  User resolves remaining videos   │                                  │
│      │  manually via browser...          │                                  │
│      │                                   │                                  │
│      ├── FS_WRITE_SLP ──────────────────►│                                  │
│      │   {slp_path: "/mnt/.../labels.slp", │                                │
│      │    output_dir: "/mnt/.../project/", │                                │
│      │    filename_map: {                │                                  │
│      │      "/old/video1.mp4": "/new/video1.mp4", │                         │
│      │      ...                          │                                  │
│      │    }}                             ├── sleap-io rewrite               │
│      │                                   │                                  │
│      │◄── FS_WRITE_SLP_OK ───────────────┤                                  │
│      │   {path: "resolved_20260113_labels.slp"} │                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Decisions

### Decision 1: Directory Scanning (SLP Viewer Style)

**Choice**: When user resolves a video, scan that video's directory for other missing filenames.

**Algorithm**:
```python
def scan_directory_for_videos(directory: Path, filenames: list[str]) -> dict[str, str | None]:
    """Scan directory for files matching the given filenames."""
    results = {}
    for filename in filenames:
        candidate = directory / filename
        if candidate.exists():
            results[filename] = str(candidate)
        else:
            results[filename] = None
    return results
```

**Why this over prefix inference**:
- Simpler to implement and understand
- Matches SLP Viewer behavior (familiar to SLEAP users)
- Works even when directory structure differs between machines
- No complex suffix-matching algorithms needed

### Decision 2: Automatic Detection After SLP Resolution

**Choice**: Worker automatically checks video accessibility after resolving/receiving SLP path, reports missing videos to Client.

**Flow**:
1. Client sends SLP path to Worker (existing path resolution flow)
2. Worker loads SLP with `sio.load_file(slp_path, open_videos=False)`
3. Worker checks if each `video.filename` exists on filesystem
4. If any missing, Worker sends `FS_CHECK_VIDEOS_RESPONSE` with list of missing filenames
5. Client automatically launches resolution UI

**Why automatic**:
- No extra flag needed (`--resolve-videos` removed)
- Detection happens at the right time (after SLP is located)
- Seamless user experience - resolution UI only appears when needed

### Decision 3: Use sleap-io for All SLP Operations

**Choice**: Use `sleap-io` Python API on Worker for loading, checking, and rewriting SLP.

**Methods used**:
- `sio.load_file(path, open_videos=False)` - Load without trying to open videos
- `labels.videos` - Access video list to check paths
- `labels.replace_filenames(filename_map={...})` - Apply path mappings
- `labels.save(output_path)` - Save corrected SLP

**Why**:
- Well-tested library (part of SLEAP ecosystem)
- Handles HDF5 format edge cases
- Already a transitive dependency
- `open_videos=False` allows checking paths without actual video I/O

### Decision 4: Reuse Existing Filesystem Browser

**Choice**: Embed existing filesystem browser from `fs_viewer.html` in resolution UI.

**Implementation**:
- `/resolve` route serves `fs_resolve.html`
- Left panel: missing videos list with status
- Right panel: iframe or embedded browser component
- Same WebSocket connection, same browse messages

## Message Protocol

### New Message: FS_CHECK_VIDEOS

Triggered automatically after SLP path resolution.

```
Worker → Client: FS_CHECK_VIDEOS_RESPONSE::{json}
  {
    "slp_path": "/mnt/vast/project/labels.slp",
    "total_videos": 5,
    "missing": [
      {"filename": "video1.mp4", "original_path": "/Users/amickl/GDrive/video1.mp4"},
      {"filename": "video2.mp4", "original_path": "/Users/amickl/GDrive/video2.mp4"}
    ],
    "accessible": 3
  }
```

### New Message: FS_SCAN_DIR

Scan a directory for specific filenames.

```
Client → Worker: FS_SCAN_DIR::{json}
  {
    "directory": "/mnt/vast/datasets/project/",
    "filenames": ["video2.mp4", "video3.mp4"]
  }

Worker → Client: FS_SCAN_DIR_RESPONSE::{json}
  {
    "directory": "/mnt/vast/datasets/project/",
    "found": {
      "video2.mp4": "/mnt/vast/datasets/project/video2.mp4",
      "video3.mp4": null
    }
  }
```

### New Message: FS_WRITE_SLP

Write corrected SLP to Worker filesystem.

```
Client → Worker: FS_WRITE_SLP::{json}
  {
    "slp_path": "/mnt/vast/project/labels.slp",
    "output_dir": "/mnt/vast/project/",
    "filename_map": {
      "/Users/amickl/GDrive/video1.mp4": "/mnt/vast/datasets/project/video1.mp4",
      "/Users/amickl/GDrive/video2.mp4": "/mnt/vast/datasets/project/video2.mp4"
    }
  }

Worker → Client: FS_WRITE_SLP_OK::{json}
  {
    "output_path": "/mnt/vast/project/resolved_20260113_labels.slp",
    "videos_updated": 2
  }

Worker → Client: FS_WRITE_SLP_ERROR::{json}
  {
    "error": "Permission denied writing to /mnt/vast/project/"
  }
```

## Risks / Trade-offs

### Risk: Videos in Different Directories
- **Scenario**: Videos scattered across multiple directories
- **Mitigation**: User resolves one video per directory; each triggers a scan of that directory

### Risk: Duplicate Filenames
- **Scenario**: Same filename exists in multiple directories
- **Mitigation**: User explicitly selects which file to use; no automatic guessing

### Risk: Large Number of Videos
- **Scenario**: SLP with 100+ video references
- **Mitigation**: Directory scanning is fast (just file existence checks); UI shows progress

## Open Questions

1. **Should we support recursive directory scanning?**
   - Current: Only scan the immediate directory
   - Alternative: Scan subdirectories too (could be slow for deep trees)
   - Recommendation: Start with immediate directory only

2. **What happens if user cancels resolution?**
   - Training cannot proceed with missing videos
   - Options: (a) Cancel training, (b) Allow partial resolution with warning
