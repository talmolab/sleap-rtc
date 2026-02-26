# Design: Web-Based File Selector

## Context

SLEAP-RTC enables remote training where Clients submit jobs to GPU Workers. Workers often have access to shared filesystems (NFS mounts, cloud drives) where users store their `.slp` training data. The challenge: Clients and Workers may have different mount paths to the same underlying storage.

### Stakeholders
- **End users**: Need to specify files without knowing Worker's exact paths
- **IT/Admins**: Configure Workers with appropriate mount points
- **Developers**: Implement secure, performant file discovery

### Constraints
- WebRTC data channel is the only communication path to Worker
- Browser cannot directly access Worker filesystem
- Must work in headless environments (SSH)
- Large shared filesystems may have millions of files

## Goals / Non-Goals

### Goals
- Enable automatic file discovery via fuzzy matching when path not found
- Provide separate `browse` command for manual path discovery
- Keep operations fast via lazy loading and depth limits
- Maintain security boundaries around configured mounts
- Secure WebSocket with token auth for headless environments

### Non-Goals
- File upload/download through the viewer (RTC handles transfer)
- Pre-indexing entire filesystems
- File editing or modification
- Auto-selection without user confirmation

## Architecture

### Two Separate Capabilities

```
┌─────────────────────────────────────────────────────────────────────┐
│              Capability 1: Fuzzy Matching (in client-train)          │
│                                                                      │
│   sleap-rtc client-train --pkg_path ~/fly.slp --room abc123         │
│                           │                                          │
│                           ▼                                          │
│   ┌───────────────────────────────────────────────────────────┐     │
│   │  Path Resolution Flow                                      │     │
│   │                                                            │     │
│   │  1. Send path to Worker                                    │     │
│   │  2. Worker checks mounts for exact match                   │     │
│   │  3. If not found → fuzzy search with wildcards            │     │
│   │  4. Return candidates to Client                            │     │
│   │  5. Display arrow selector                                 │     │
│   │     ┌───────────────────────────────────────────┐         │     │
│   │     │ Select file:                              │         │     │
│   │     │ > /mnt/data/amick/fly.slp      (125 MB)  │         │     │
│   │     │   /mnt/backup/fly.slp          (125 MB)  │         │     │
│   │     │ ↑↓ Navigate  Enter Confirm               │         │     │
│   │     └───────────────────────────────────────────┘         │     │
│   │  6. User confirms → proceed with training                  │     │
│   └───────────────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│              Capability 2: Browse Command (separate CLI)             │
│                                                                      │
│   sleap-rtc browse --room abc123                                    │
│                           │                                          │
│                           ▼                                          │
│   ┌───────────────────────────────────────────────────────────┐     │
│   │  Browse Server                                             │     │
│   │                                                            │     │
│   │  1. Connect to Worker via WebRTC                           │     │
│   │  2. Generate session token                                 │     │
│   │  3. Start HTTP server on localhost:8765                    │     │
│   │  4. Open browser to http://127.0.0.1:8765?token=xyz        │     │
│   │                                                            │     │
│   │  ┌────────────────────────────────────────────────────┐   │     │
│   │  │ Browser UI (dark theme)                             │   │     │
│   │  │ ┌────────────────────────────────────────────────┐ │   │     │
│   │  │ │ 🟢 Connected to: worker-gpu-01                 │ │   │     │
│   │  │ │ ──────────────────────────────────────────────│ │   │     │
│   │  │ │ [Lab Data]  [Shared Storage]  [Archive]       │ │   │     │
│   │  │ │                                               │ │   │     │
│   │  │ │ /mnt/data/amick/projects/                     │ │   │     │
│   │  │ │ ├── 📁 fly_courtship/                        │ │   │     │
│   │  │ │ ├── 📁 mouse_tracking/                       │ │   │     │
│   │  │ │ └── 📄 labels.slp        125 MB  [Copy Path] │ │   │     │
│   │  │ │                                               │ │   │     │
│   │  │ │ Showing 20 of 45 items                        │ │   │     │
│   │  │ └────────────────────────────────────────────────┘ │   │     │
│   │  └────────────────────────────────────────────────────┘   │     │
│   │                                                            │     │
│   │  User clicks [Copy Path] → clipboard                       │     │
│   │  Server stays open for more browsing                       │     │
│   └───────────────────────────────────────────────────────────┘     │
│                                                                      │
│   User then runs:                                                   │
│   sleap-rtc client-train --pkg_path /mnt/data/.../labels.slp       │
└─────────────────────────────────────────────────────────────────────┘
```

## Decisions

### Decision 1: Separate `browse` Command
**What**: Filesystem browsing is a separate CLI command (`sleap-rtc browse`), not a flag on `client-train`.

**Why**:
- Clear separation of concerns: discovering paths vs running training
- User can browse first, copy multiple paths, then run training later
- Browser stays open across multiple training invocations
- Simpler mental model: browse = exploration, train = execution

**Implementation**:
```bash
# Browse first (requires room credentials)
sleap-rtc browse --room abc123 --token xyz789
# → Opens browser, user explores, copies path

# Train later (path already known)
sleap-rtc client-train --pkg_path /mnt/data/fly.slp --room abc123 --token xyz789
```

### Decision 2: Token-Protected WebSocket
**What**: Generate random token on server start, require it for WebSocket connections.

**Why**:
- Headless environments expose URL to user who may copy it elsewhere
- Shared machines could have port scanning or accidental connections
- Simple protection without full auth infrastructure

**Implementation**:
```python
import secrets

class FSViewerServer:
    def __init__(self):
        self.token = secrets.token_urlsafe(16)

    def get_url(self, port: int) -> str:
        return f"http://127.0.0.1:{port}?token={self.token}"

    async def websocket_handler(self, request):
        if request.query.get('token') != self.token:
            return web.Response(status=403, text="Invalid token")
        # Proceed with WebSocket upgrade
```

### Decision 3: Worker Connection Status in Browser
**What**: Browser UI displays which Worker is connected and connection status.

**Why**:
- User needs to know which Worker's filesystem they're viewing
- Connection drops should be visible immediately
- Multiple rooms/workers possible, need disambiguation

**Display elements**:
- Worker identifier (name or peer ID)
- Connection status indicator (🟢 connected, 🔴 disconnected)
- Last update timestamp

### Decision 4: Worker `--working-dir` Option
**What**: Add `--working-dir` CLI option to Worker to set working directory.

**Why**:
- Workers may need to resolve relative paths
- Simplifies mount configuration (can use relative mounts)
- Useful for containerized deployments

**Implementation**:
```bash
sleap-rtc worker --room abc123 --working-dir /mnt/data
```

### Decision 5: Interactive Arrow-Key Selection (No Auto-Select)
**What**: Even when a single match is found, present it in an interactive CLI selector.

**Why**:
- Prevents accidental selection of wrong file
- Consistent UX regardless of result count
- Familiar pattern from Claude Code, fzf, and other modern CLIs

### Decision 6: Wildcard Support with Pattern Validation
**What**: Support glob-style wildcards with minimum complexity requirement.

**Why**:
- Users may not remember exact filename
- Pattern like `*` alone would be too broad

**Rules**:
- Support `*`, `?`, `[abc]` via `fnmatch`
- Require at least 3 non-wildcard characters
- Max 20 results, 10-second timeout

## Protocol Messages

### Fuzzy Resolution
```
Client → Worker: FS_RESOLVE::{pattern}::{file_size}::{max_depth}

Worker → Client: FS_RESOLVE_RESPONSE::{json}
{
  "candidates": [...],
  "truncated": false,
  "timeout": false,
  "search_time_ms": 234
}
```

### Directory Listing (Browser)
```
Client → Worker: FS_LIST_DIR::{path}::{offset}

Worker → Client: FS_LIST_RESPONSE::{json}
{
  "path": "/mnt/data/amick",
  "entries": [...],
  "total_count": 45,
  "has_more": true
}
```

### Worker Info (Browser Status)
```
Client → Worker: FS_GET_INFO

Worker → Client: FS_INFO_RESPONSE::{json}
{
  "worker_id": "worker-gpu-01",
  "working_dir": "/mnt/data",
  "mounts": [...]
}
```

## Risks / Trade-offs

### Risk: Token Leakage
**Issue**: User accidentally shares URL with token.
**Mitigation**:
- Token is session-scoped (new token each browse session)
- Token is 16 bytes (128 bits) of randomness
- Could add token expiry (not implemented in v1)

### Risk: Terminal Without Arrow Key Support
**Issue**: Some terminals don't support arrow keys.
**Mitigation**:
- Detect terminal capabilities
- Fallback to numbered selection
- `--non-interactive` flag for CI/scripts

### Risk: Large Mount Points
**Issue**: Mount with deep hierarchy could be slow.
**Mitigation**:
- Max 20 results per request
- 10-second timeout with partial results
- Lazy loading (no pre-indexing)

## Open Questions (Resolved)

1. ~~**Separate command vs flag?**~~ **Separate command** (`sleap-rtc browse`)
2. ~~**WebSocket security?**~~ **Token auth** via URL parameter
3. ~~**Worker status?**~~ **Show in browser** with connection indicator

## Implementation Notes

### Browser UI Base
Use `scratch/browser_ui.html` as starting point:
- Remove simulation controls
- Replace mock data with WebSocket
- Add "Copy Path" instead of "Use This Path"
- Add connection status header
- Add token validation on WebSocket connect

### Dependencies
- `prompt_toolkit` - for arrow-key selection UI
- `aiohttp` - for HTTP/WebSocket server
- `secrets` - for token generation (stdlib)
