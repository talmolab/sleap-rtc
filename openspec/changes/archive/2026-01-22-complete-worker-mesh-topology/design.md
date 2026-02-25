# Design: Complete Worker Mesh Topology

## Current Architecture (Hub-and-Spoke)

```
                    ┌─────────────────┐
                    │  Signaling      │
                    │  Server (WS)    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
         ┌─────────►│  Admin Worker   │◄─────────┐
         │          │     ("62")      │          │
         │          └────────┬────────┘          │
         │                   │                   │
    ┌────┴────┐         WebRTC            ┌────┴────┐
    │ Worker  │          Only             │ Worker  │
    │  ("36") │◄─────────────────────────►│  ("ba") │
    └─────────┘     NO CONNECTION!        └─────────┘
```

**Problem**: When admin "62" leaves, workers "36" and "ba" lose ALL connections and must reconnect via WebSocket.

## Target Architecture (Full Mesh)

```
                    ┌─────────────────┐
                    │  Signaling      │
                    │  Server (WS)    │
                    └────────┬────────┘
                             │ (discovery only)
                    ┌────────▼────────┐
         ┌─────────►│  Admin Worker   │◄─────────┐
         │          │     ("62")      │          │
         │          └────────┬────────┘          │
         │                   │                   │
    ┌────┴────┐         WebRTC             ┌────┴────┐
    │ Worker  │◄══════════════════════════►│ Worker  │
    │  ("36") │      DIRECT CONNECTION     │  ("ba") │
    └─────────┘                            └─────────┘
```

**Benefit**: When admin "62" leaves, workers "36" and "ba" remain connected. One becomes new admin, no reconnection needed.

## Connection Flow

### Phase 1: Initial Connection (via WebSocket)

```
Worker "ba"                Signaling Server              Admin "62"
    │                            │                           │
    │──── register ─────────────►│                           │
    │                            │                           │
    │◄─── registered_auth ───────│                           │
    │     (admin_peer_id="62")   │                           │
    │                            │                           │
    │──── mesh_connect ─────────►│──── mesh_offer ──────────►│
    │     (SDP offer)            │                           │
    │                            │                           │
    │◄─── mesh_answer ───────────│◄─── mesh_answer ──────────│
    │                            │     (SDP answer)          │
    │                            │                           │
    │◄═══════════ ICE negotiation ═══════════════════════════│
    │                            │                           │
    │◄══════════ WebRTC Data Channel Established ════════════│
```

### Phase 2: Mesh Formation (via Data Channel)

```
Worker "ba"              Admin "62"                    Worker "36"
    │                        │                             │
    │◄── mesh_peer_list ─────│                             │
    │    (peers: ["36"])     │                             │
    │                        │                             │
    │──── mesh_offer ───────►│──── relay ─────────────────►│
    │    (to: "36")          │                             │
    │                        │                             │
    │◄─── mesh_answer ───────│◄─── relay ──────────────────│
    │                        │    (from: "36")             │
    │                        │                             │
    │◄═════════════════ ICE negotiation ═══════════════════│
    │                        │                             │
    │◄═══════════ Direct WebRTC Data Channel ══════════════│
```

### Phase 3: Admin Departure (No Reconnection)

```
Before:                              After:

    "62" (admin)                     "36" (new admin)
     /    \                               │
    /      \                              │
  "36"     "ba"                          "ba"
    \      /                      (already connected!)
     \    /
     (mesh)
```

## Message Protocol

### mesh_peer_list (Admin → New Worker)

Sent immediately after admin accepts connection from new worker.

```json
{
  "type": "mesh_peer_list",
  "peer_ids": ["36ba382f-...", "other-worker-..."],
  "peer_metadata": {
    "36ba382f-...": {
      "gpu_memory_mb": 16000,
      "status": "available"
    }
  }
}
```

### mesh_offer (Worker → Admin → Target Worker)

Relayed through admin's data channel.

```json
{
  "type": "mesh_offer",
  "from_peer_id": "ba43640f-...",
  "to_peer_id": "36ba382f-...",
  "offer": {
    "sdp": "v=0\r\no=- ...",
    "type": "offer"
  }
}
```

### mesh_answer (Target Worker → Admin → Worker)

```json
{
  "type": "mesh_answer",
  "from_peer_id": "36ba382f-...",
  "to_peer_id": "ba43640f-...",
  "answer": {
    "sdp": "v=0\r\no=- ...",
    "type": "answer"
  }
}
```

### mesh_ice_candidate (Bidirectional via Admin)

```json
{
  "type": "mesh_ice_candidate",
  "from_peer_id": "ba43640f-...",
  "to_peer_id": "36ba382f-...",
  "candidate": {
    "candidate": "candidate:...",
    "sdpMLineIndex": 0,
    "sdpMid": "0"
  }
}
```

## Design Decisions

### D1: Keep WebSocket Open for Non-Admin Workers

**Decision**: Non-admin workers keep their WebSocket connection open.

**Rationale**:
- Enables reconnection to new admin if current admin fails
- Allows receiving notifications about new workers joining
- Provides fallback if mesh relay fails
- Current code accidentally does this (no explicit close) - making it intentional

**Trade-off**: Slightly higher resource usage on signaling server, but enables resilience.

### D2: Admin Relays Mesh Signaling

**Decision**: All worker-to-worker SDP/ICE exchange goes through admin's data channel.

**Rationale**:
- Signaling server not involved after initial connection (reduces load)
- Admin already has data channels to all workers
- Consistent with existing mesh relay code (`mesh_coordinator.py:519-573`)

**Alternative Considered**: Use signaling server for all mesh signaling
- Rejected: Would increase signaling server load (defeats purpose of mesh)

### D3: Peer List Sent via Data Channel

**Decision**: Admin sends peer list via data channel after connection established.

**Rationale**:
- Data channel already open (guaranteed delivery)
- Includes live metadata from CRDT
- No additional signaling server API needed

**Alternative Considered**: Include peer list in signaling server's `registered_auth` response
- Rejected: Would require signaling server to track live worker metadata

### D4: Full Mesh Topology

**Decision**: Every worker connects to every other worker (N*(N-1)/2 connections).

**Rationale**:
- Maximum resilience (any worker can leave without breaking mesh)
- Enables direct worker-to-worker communication (future: job coordination)
- Room size limit (10 workers) keeps connection count manageable (max 45)

**Alternative Considered**: Hierarchical topology (admin + subgroups)
- Rejected: Overkill for current scale, adds complexity

## Connection Limits

| Workers | Total Connections | Per Worker |
|---------|-------------------|------------|
| 2       | 1                 | 1          |
| 3       | 3                 | 2          |
| 5       | 10                | 4          |
| 8       | 28                | 7          |
| 10      | 45                | 9          |

Room limit of 10 workers ensures max 45 connections total, 9 per worker.

## Error Handling

### Mesh Relay Failure

If admin can't relay message to target worker:
1. Log error with source/target peer_ids
2. Return error message to source worker
3. Source worker can retry or fall back to WebSocket signaling

### ICE Connection Failure

If worker-to-worker ICE negotiation fails:
1. Log failure with peer_ids
2. Workers remain in mesh via other connections
3. Can retry connection later (exponential backoff)

### Admin Departure During Mesh Formation

If admin leaves while new worker is connecting to peers:
1. New admin is elected
2. New admin inherits pending connections (via CRDT)
3. New worker retries mesh formation with new admin
