## Context

The current browse and resolve-paths commands use a localhost HTTP server (`FSViewerServer`) that:
1. Serves HTML/JS UI files
2. Relays WebSocket messages between browser and WebRTC data channel
3. Requires a browser to be available and accessible

This breaks in SSH sessions (localhost not accessible), requires context-switching to browser, and adds JavaScript dependency. The TUI eliminates these issues while preserving the existing WebRTC transport layer.

## Goals / Non-Goals

**Goals:**
- Eliminate browser dependency for file browsing and path resolution
- Work seamlessly over SSH
- Unified terminal experience
- Reuse existing WebRTC connection logic (no worker-side changes)
- Foundation for future GUI

**Non-Goals:**
- Room creation/deletion/invite management (stays in dashboard)
- Replacing the dashboard entirely
- Supporting non-terminal environments in this phase

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│  sleap-rtc tui [--room ROOM_ID --token TOKEN] [--otp-secret S]  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  JWT exists?    │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │ No                          │ Yes
              ▼                             ▼
┌─────────────────────────────┐   ┌─────────────────────────────┐
│  LoginScreen                │   │  --room flag provided?      │
│                             │   └──────────────┬──────────────┘
│  Not logged in.             │                  │
│                             │       ┌──────────┴──────────┐
│  Open this URL to login:    │       │ No                  │ Yes
│  https://...dashboard/...   │       ▼                     │
│                             │   ┌───────────────────┐     │
│  Waiting... (118s) [q quit] │   │  RoomSelectScreen │     │
└─────────────────────────────┘   │                   │     │
              │                   │  Select a room:   │     │
              │ (JWT received)    │  > lab-gpu-room   │     │
              ▼                   │    shared-cluster │     │
              └──────────────────►│    dev-testing    │     │
                                  └─────────┬─────────┘     │
                                            │               │
                                            ▼               │
                                  ┌─────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BrowserScreen (Textual)                    │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │ Worker Tabs: [ worker-1 ] [ worker-2 ] [ worker-3 ]         ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │                                                             ││
│  │   Miller Columns (file browser)                             ││
│  │   ┌──────────┬──────────┬──────────┬──────────┐            ││
│  │   │ /mnt     │ data/    │ project/ │ vid.slp  │            ││
│  │   │ /home    │ models/  │ labels/  │ ...      │            ││
│  │   │          │          │          │          │            ││
│  │   └──────────┴──────────┴──────────┴──────────┘            ││
│  ├─────────────────────────────────────────────────────────────┤│
│  │ Context Panel (shows when SLP selected):                    ││
│  │   Videos: ✓ video1.mp4  ✗ video2.mp4 (missing)             ││
│  │   [Navigate to find video2.mp4, then press 'f' to fix]     ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  Existing WebRTC Layer (reused from rtc_browse.py)              │
│  - Signaling via WebSocket                                      │
│  - P2P data channel to Worker                                   │
│  - Same message protocol (FS_LIST_DIR, etc.)                    │
└─────────────────────────────────────────────────────────────────┘
```

## Decisions

### Decision 1: Textual Framework
- **Choice:** Textual (Python TUI framework)
- **Rationale:** Native async support fits existing aiortc/aiohttp patterns, rich widget library, CSS-like styling, active maintenance
- **Alternatives considered:**
  - Rich + prompt_toolkit: More DIY, less cohesive widget system
  - urwid: Older, more verbose
  - Charm/Bubble Tea: Go-based, would require rewriting WebRTC logic or FFI

### Decision 2: Miller Columns Layout
- **Choice:** Miller columns (like macOS Finder)
- **Rationale:** Matches current web UI, familiar to SLEAP users, good for deep directory hierarchies
- **Alternatives considered:**
  - Tree view: Less horizontal space efficient
  - Dual-pane: Overkill for browsing (better for file management)

### Decision 3: Worker Tabs
- **Choice:** Tabs at top for worker switching
- **Rationale:** Simple, familiar pattern, always visible
- **Alternatives considered:**
  - Sidebar: Takes horizontal space
  - Hotkey picker: Hidden, less discoverable

### Decision 4: Inline Path Resolution
- **Choice:** Context panel appears when SLP selected, shows video status inline
- **Rationale:** No mode switching, unified experience
- **Alternatives considered:**
  - Separate resolve mode: Extra complexity
  - Modal overlay: Interrupts browsing flow

### Decision 5: JWT-Based Room Picker (Primary Flow)
- **Choice:** If logged in, show interactive room selector; `--room --token` flags optional for direct access
- **Rationale:** Simpler UX (just run `sleap-rtc tui`), matches worker's simple `--api-key` experience, reduces friction
- **Flow:**
  1. Check for valid JWT in credentials
  2. If not logged in → show LoginScreen with dashboard URL, poll for JWT
  3. If logged in → fetch rooms via `/api/auth/rooms`, show RoomSelectScreen
  4. User selects room → connect to workers
- **Fallback:** `--room ROOM --token TOKEN` flags bypass picker for scripting/automation
- **Alternatives considered:**
  - Required flags only: Less user-friendly, inconsistent with worker experience

## Component Structure

```
sleap_rtc/tui/
├── __init__.py
├── app.py              # TUIApp(App) - main application
├── widgets/
│   ├── __init__.py
│   ├── miller.py       # MillerColumns widget
│   ├── worker_tabs.py  # WorkerTabs widget
│   └── slp_panel.py    # SLPContextPanel widget
├── screens/
│   ├── __init__.py
│   ├── login.py        # LoginScreen - JWT polling with URL display
│   ├── room_select.py  # RoomSelectScreen - room picker list
│   └── browser.py      # BrowserScreen (main file browser)
└── bridge.py           # WebRTCBridge - async message handling
```

## Message Flow

```
User Input (keyboard)
       │
       ▼
MillerColumns Widget
       │
       ▼ (e.g., navigate to /data)
WebRTCBridge.send(FS_LIST_DIR::/data::0)
       │
       ▼
BrowseClient (existing) → WebRTC Data Channel → Worker
       │
       ◄───────────────────────────────────────────────
       │
WebRTCBridge.on_message(list_response)
       │
       ▼
MillerColumns.update(entries)
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Textual learning curve | Well-documented, active community |
| Terminal compatibility | Textual handles this; fallback to basic rendering |
| Large directory performance | Pagination (already in protocol), lazy loading |
| SSH latency | Same as current (WebRTC + signaling) |

## Migration Plan

1. **Phase 1:** Add TUI as new command, keep `browse`/`resolve-paths` working
2. **Phase 2:** Deprecate browser-based commands with warning
3. **Phase 3:** Remove `FSViewerServer` (optional, low priority)

## Open Questions

- Should the TUI support job submission/monitoring in v1, or defer to v2?
  - **Decision:** Defer to v2, focus on browse + resolve first
- Should we add ASCII QR code for OTP setup?
  - **Decision:** Nice-to-have, not in scope for this proposal
- Should the TUI have interactive room selection or require flags?
  - **Decision:** Interactive room selection is primary flow (JWT-based), flags are fallback for scripting
