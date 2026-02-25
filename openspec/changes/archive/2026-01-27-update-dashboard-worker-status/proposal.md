## Why

The current dashboard provides basic room and worker token management but has several UX issues:
1. Dates display incorrectly due to timezone handling (rooms created yesterday show as today)
2. Tokens show raw room IDs instead of human-readable room names
3. Users cannot see if any workers are connected to their tokens

This proposal makes targeted improvements while keeping the dashboard focused on **management** (rooms, tokens, access control). Detailed worker monitoring and operations are deferred to the future TUI/GUI, which can connect via WebRTC for real-time data without burdening the signaling server.

## What Changes

### Dashboard UI Fixes
- **Relative time display**: Replace `toLocaleDateString()` with relative time ("2 hours ago") with tooltip showing exact datetime - fixes timezone issues
- **Room name in tokens**: Display room name alongside room ID (format: "Room Name (abc123...)")
- **Connected worker count**: Show "N workers connected" badge on each token card
- **Worker names under tokens**: Show list of connected worker hostnames under each token (collapsed by default)

### Minimal API Enhancement
- **Endpoint**: `GET /api/auth/tokens` response includes `room_name` (JOIN with rooms table)
- **Endpoint**: `GET /api/auth/tokens/{token_id}/workers` returns list of connected worker peer_ids
  - This queries the signaling server's existing WebSocket connection state (no new state management)
  - Returns only: `[{peer_id, connected_at}]` - minimal data already tracked

### Modern UI Refresh
- Update styling with cleaner RunAI/W&B-inspired design
- Sidebar navigation for better organization
- Demo at `dashboard/demo-modern-ui.html`

## Out of Scope (Deferred to TUI/GUI)

The following features require real-time data and are better served by direct WebRTC connections in TUI/GUI:
- Detailed worker status (available/busy)
- GPU information and utilization
- Current job details
- File browsing
- Job management

**Rationale**: The signaling server should remain a lightweight message relay. Real-time worker monitoring via WebRTC in TUI/GUI offloads this burden entirely.

## Impact

- **Affected specs**: New `dashboard` capability (no existing spec)
- **Affected code**:
  - `dashboard/app.js` - Relative time formatting, room name display, worker count badges
  - `dashboard/index.html` - Minor structural updates
  - `dashboard/styles.css` - Modern styling refresh
  - Signaling server - Add `room_name` to tokens response, add worker count endpoint
