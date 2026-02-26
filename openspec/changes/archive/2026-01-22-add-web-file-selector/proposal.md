# Proposal: Add Web-Based File Selector for Remote Mounts

## Why

Users need an intuitive way to locate `.slp` files on shared filesystems accessible to Workers. Currently, users must know the exact path on the Worker's filesystem. This is error-prone when:
- Client and Worker have different mount paths for the same shared storage
- User doesn't know the Worker's filesystem structure
- Files are organized in deep directory hierarchies

## What Changes

This proposal introduces **two separate capabilities** for file discovery:

### Capability 1: Fuzzy Matching (Automatic Fallback)

When Client provides a path that Worker can't find, automatic fuzzy matching kicks in:

1. Client runs `client-train --pkg_path /path/to/file.slp`
2. Worker checks if exact path exists within its mounts
3. **If not found**, Worker performs lazy fuzzy search with wildcard support
4. Client displays interactive arrow-key selection UI
5. User confirms selection, training proceeds

**Key principles:**
- **Automatic**: Triggered only when path resolution fails
- **Wildcard support**: `fly_*.slp`, `*tracking*`, `exp_??.slp`
- **No auto-selection**: Always present choices via arrow picker
- **Limits**: Max 20 results, 10-second timeout

### Capability 2: Filesystem Browser (Separate Command)

A **separate CLI command** to browse Worker's filesystem and discover paths:

```bash
# Step 1: Browse Worker's filesystem (separate command)
sleap-rtc browse --room <room_id> --token <room_token>

# Opens browser at http://127.0.0.1:8765?token=abc123
# User navigates, clicks "Copy Path" on desired file
# Path copied to clipboard: /mnt/data/amick/fly_tracking.slp

# Step 2: Use the path in training (separate invocation)
sleap-rtc client-train --pkg_path /mnt/data/amick/fly_tracking.slp --room <room_id> --token <room_token>
```

**Key principles:**
- **Separate command**: `sleap-rtc browse`, not a flag on `client-train`
- **Copy-focused**: Primary action is copying Worker paths to clipboard
- **Stays open**: Browser remains open for multiple path discoveries
- **Shows worker status**: Displays which Worker is connected
- **Token auth**: WebSocket protected with URL token for headless security

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Normal Training Flow                             │
│                                                                      │
│  sleap-rtc client-train --pkg_path ~/data/fly.slp                   │
│                           │                                          │
│                           ▼                                          │
│              ┌────────────────────────┐                             │
│              │ Worker checks path     │                             │
│              └────────────────────────┘                             │
│                     │           │                                    │
│              [Found]│           │[Not Found]                        │
│                     ▼           ▼                                    │
│              ┌──────────┐  ┌──────────────────┐                     │
│              │ Proceed  │  │ Fuzzy search     │                     │
│              │ with job │  │ → Arrow selector │                     │
│              └──────────┘  └──────────────────┘                     │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     Separate Browse Command                          │
│                                                                      │
│  sleap-rtc browse --room abc123 --token xyz789                      │
│                           │                                          │
│                           ▼                                          │
│              ┌────────────────────────┐                             │
│              │ Connect to Worker      │                             │
│              │ Start local HTTP server│                             │
│              │ Open browser           │                             │
│              └────────────────────────┘                             │
│                           │                                          │
│                           ▼                                          │
│              ┌────────────────────────────────────────────────┐     │
│              │ Browser UI (dark theme)                         │     │
│              │ ┌──────────────────────────────────────────┐   │     │
│              │ │ Connected to: worker-gpu-01              │   │     │
│              │ │ [Mount: Lab Data] [Mount: Shared]        │   │     │
│              │ │                                          │   │     │
│              │ │ 📁 projects/                             │   │     │
│              │ │ 📁 archives/                             │   │     │
│              │ │ 📄 fly_tracking.slp  [Copy Path]         │   │     │
│              │ └──────────────────────────────────────────┘   │     │
│              └────────────────────────────────────────────────┘     │
│                                                                      │
│  User copies path, then runs:                                       │
│  sleap-rtc client-train --pkg_path /mnt/data/fly_tracking.slp       │
└─────────────────────────────────────────────────────────────────────┘
```

## Impact

### Worker Changes
- Add `[[worker.io.mounts]]` configuration for browsable mount points
- Add `--working-dir` CLI option to set Worker's working directory
- Implement lazy fuzzy search with wildcard support
- Handle filesystem metadata requests (read-only)
- Security: Only allow access within configured mount roots

### Client Changes
- Add `sleap-rtc browse` command (new CLI command)
- Add interactive arrow-key selection UI for fuzzy results
- Launch local HTTP server with token-protected WebSocket
- Display Worker connection status in browser

### Protocol Changes
- Add `FS_RESOLVE` / `FS_RESOLVE_RESPONSE` for fuzzy path resolution
- Add `FS_LIST_DIR` / `FS_LIST_RESPONSE` for directory listing
- Add `FS_GET_MOUNTS` / `FS_MOUNTS_RESPONSE` for mount discovery

## CLI Structure

```bash
# Worker commands
sleap-rtc worker --room <id> --working-dir /mnt/data  # New: working dir option

# Client commands
sleap-rtc client-train --pkg_path <path> --room <id> --token <token>  # Existing, with fuzzy fallback
sleap-rtc browse --room <id> --token <token>                          # NEW: separate browse command
```

## Affected Code

- `sleap_rtc/config.py` - Add `MountConfig` dataclass
- `sleap_rtc/protocol.py` - Add `MSG_FS_*` message types
- `sleap_rtc/worker/file_manager.py` - Add fuzzy search and directory listing
- `sleap_rtc/worker/worker_class.py` - Handle FS messages
- `sleap_rtc/cli.py` - Add `browse` command, add `--working-dir` to worker
- `sleap_rtc/client/file_selector.py` - Arrow selection UI (new)
- `sleap_rtc/client/fs_viewer_server.py` - Browser server with token auth (new)
- `sleap_rtc/client/static/fs_viewer.html` - Browser UI based on scratch/browser_ui.html (new)

## Security

### Mount Boundaries
- Workers MUST only expose explicitly configured mount paths
- Path traversal attacks prevented via canonicalization
- All filesystem operations are read-only

### WebSocket Token Auth
- Server generates random token on startup
- Token included in URL: `http://127.0.0.1:8765?token=<random>`
- WebSocket endpoint validates token on connection
- Prevents unauthorized access in headless/shared environments

## Considerations

### Performance
- **Lazy indexing**: Directories scanned on-demand, not pre-indexed
- **Limits**: Max 20 results for fuzzy, max 20 items per directory listing
- **Timeout**: 10-second limit on fuzzy search

### User Experience
- **Separate concerns**: Training vs browsing are different commands
- **No auto-selection**: User always confirms via arrow picker
- **Viewer stays open**: Copy multiple paths in one session
- **Worker status**: Browser shows which Worker is connected
