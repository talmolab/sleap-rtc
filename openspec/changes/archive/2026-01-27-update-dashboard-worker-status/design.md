## Context

The SLEAP-RTC dashboard is a static GitHub Pages site for managing rooms and worker tokens. This proposal adds targeted UX improvements while maintaining a clear separation:

- **Dashboard** = Management plane (rooms, tokens, access control)
- **TUI/GUI** = Operations plane (worker monitoring, file browsing, job management)

**Stakeholders**: End users managing remote training infrastructure
**Constraints**:
- Dashboard is static (GitHub Pages) - no server-side rendering
- Signaling server must remain a lightweight message relay
- Real-time worker data should flow via WebRTC, not polling the server

## Goals / Non-Goals

**Goals:**
- Fix timezone-related date display issues
- Show room names instead of raw IDs in token cards
- Show basic worker connection count per token
- Modernize visual design

**Non-Goals:**
- Detailed worker status (busy/available) - deferred to TUI/GUI
- GPU information and utilization - deferred to TUI/GUI
- Job tracking and management - deferred to TUI/GUI
- Real-time updates via WebSocket - deferred to TUI/GUI
- File browsing - deferred to TUI/GUI

## Architectural Decision: Dashboard vs TUI/GUI Split

### Problem
Users want visibility into worker status, but adding this to the dashboard would:
1. Require the signaling server to track and expose worker state
2. Require polling from potentially many dashboard users
3. Turn the signaling server into a management API (scope creep)

### Decision
Keep the signaling server as a **pure message relay**. Real-time worker monitoring belongs in TUI/GUI which can:
1. Connect directly to workers via WebRTC
2. Receive real-time status updates over data channels
3. Query worker capabilities directly

### What Dashboard CAN Show (Minimal Server Burden)
The signaling server already tracks WebSocket connections. We can expose:
- Count of workers connected to a room/token
- Worker peer_ids (which contain hostname: `worker-8f3a-labgpu1`)
- Connection timestamps

This requires NO new state management - just querying existing connection state.

## Data Model

### Token Response Enhancement

```
GET /api/auth/tokens
Response tokens now include:
{
  "token_id": "slp_xxx...",
  "room_id": "abc123...",
  "room_name": "My Research Lab",  // NEW: Added via SQL JOIN
  "worker_name": "lab-gpu-1",
  "created_at": "2026-01-20T10:30:00Z",
  "expires_at": "2026-01-27T10:30:00Z",
  ...
}
```

### Connected Workers Endpoint (Minimal)

```
GET /api/auth/tokens/{token_id}/workers
Authorization: Bearer <jwt>

Response:
{
  "workers": [
    {
      "peer_id": "worker-8f3a1b2c-labgpu1",
      "connected_at": "2026-01-22T09:30:00Z"
    },
    {
      "peer_id": "worker-8f3a1b2c-labgpu2",
      "connected_at": "2026-01-22T08:15:00Z"
    }
  ],
  "count": 2
}
```

**Implementation**: Query signaling server's in-memory connection map, filter by token_id from peer metadata.

## UI Components

### Token Card with Worker Count

```
┌─────────────────────────────────────────────────────────────────┐
│ 🔑 Lab GPU Cluster                              [Copy] [Revoke] │
│    Room: My Research Lab (abc123...)                            │
│    Created 2 days ago • Expires in 5 days                       │
│                                                                 │
│    ● 2 workers connected                                        │
│                                                                 │
│ ▼ Connected Workers                                             │
│   • labgpu1 (connected 3 hours ago)                            │
│   • labgpu2 (connected 5 hours ago)                            │
└─────────────────────────────────────────────────────────────────┘
```

**Note**: Only hostname and connection time shown. No status/GPU/job info (that's for TUI/GUI).

### Relative Time Implementation

```javascript
function formatRelativeTime(isoString) {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });

  if (diffDay > 0) return rtf.format(-diffDay, 'day');
  if (diffHour > 0) return rtf.format(-diffHour, 'hour');
  if (diffMin > 0) return rtf.format(-diffMin, 'minute');
  return 'just now';
}
```

## Risks / Trade-offs

| Risk | Impact | Mitigation |
|------|--------|------------|
| Users want more worker detail in dashboard | Low | Document that TUI/GUI is for operations |
| Worker count endpoint adds some load | Low | Only queries in-memory state; no DB hit |
| Polling frequency for worker count | Low | Default to 60s; count doesn't change rapidly |

## Migration Plan

1. **Phase 1**: Relative time formatting (frontend only, no API changes)
2. **Phase 2**: Add `room_name` to tokens API response (simple SQL JOIN)
3. **Phase 3**: Add worker count endpoint (query connection state)
4. **Phase 4**: Update token cards to show worker count and names
5. **Phase 5**: Apply modern UI styling

Each phase can be deployed independently.

## Future: TUI/GUI Operations

The TUI/GUI will handle detailed worker operations by:
1. Connecting to signaling server via WebSocket
2. Establishing WebRTC connections to workers
3. Receiving real-time status over data channels
4. Querying worker capabilities directly

This keeps all real-time data flow peer-to-peer, with the signaling server only facilitating connection setup.
