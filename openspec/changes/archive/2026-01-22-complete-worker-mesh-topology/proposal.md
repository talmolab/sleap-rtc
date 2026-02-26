# Complete Worker Mesh Topology

## Why

**Problem**: The room-level registry implementation (`add-room-level-registry`) is partially complete but has critical bugs and missing functionality:

### Bugs Discovered
1. **Partition status display bug**: `is_partitioned` is set AFTER `_on_partition_detected()` is called, so health logs show stale "Healthy" status during partition
2. **Missing `retry_tasks` attribute**: `self.retry_tasks` is used at `worker_class.py:924` but never initialized, causing `AttributeError`
3. **Hub-and-spoke only**: Non-admin workers only connect to admin, not to each other (TODO at `worker_class.py:1199-1200`)

### Impact
- When admin leaves, remaining workers lose ALL connections (no direct worker-worker links)
- Workers must reconnect via WebSocket signaling server instead of using existing mesh
- Partition detection logs are misleading (shows "Healthy" when partitioned)
- Reconnection attempts crash with `AttributeError`

**Solution**: Fix the bugs and complete the full mesh topology where every worker connects to every other worker via RTC data channels.

## What Changes

### Bug Fixes
- **FIX**: Set `is_partitioned` BEFORE calling `_on_partition_detected()`
- **FIX**: Initialize `self.retry_tasks = {}` in `RTCWorkerClient.__init__`
- **FIX**: Explicitly keep WebSocket open for non-admin workers (enables reconnection)

### Full Mesh Implementation
- **NEW**: Admin sends peer list to newly connected workers via data channel
- **NEW**: Workers connect to ALL other workers (not just admin) after receiving peer list
- **NEW**: Workers use existing RTC data channels for peer-to-peer signaling (no WebSocket needed)
- **NEW**: Admin verification ping after election (prevents stale admin if elected peer leaves during election)
- **MODIFIED**: When admin leaves, workers already have direct connections - no reconnection needed

### Component Changes
- `sleap_rtc/worker/worker_class.py` - Fix bugs, initialize retry_tasks
- `sleap_rtc/worker/mesh_coordinator.py` - Implement peer list broadcast and worker-to-worker connections

## Impact

### Affected Code
- `sleap_rtc/worker/worker_class.py` - ~20 lines modified (bug fixes)
- `sleap_rtc/worker/mesh_coordinator.py` - ~100 lines added (peer list, worker connections)

### Related Changes
- **EXTENDS**: `add-room-level-registry` - Completes the mesh topology implementation
- **BLOCKS**: None - Can be merged independently

### Backwards Compatibility
- Fully backwards compatible - fixes bugs without changing external behavior
- Existing 1-worker rooms continue to work unchanged
- Multi-worker rooms will form full mesh instead of hub-and-spoke

## Success Criteria

### Functional Requirements
- Workers establish direct RTC connections to ALL other workers (not just admin)
- When admin leaves, remaining workers already connected - no reconnection needed
- Partition status correctly displays "Partitioned" immediately when detected
- No `AttributeError` for `retry_tasks`

### Performance Targets
- Mesh formation: 5 workers establish 10 connections within 10 seconds
- Admin departure: Zero reconnection delay for remaining workers (already connected)
- Partition detection: Status logged correctly within same log batch

## Implementation Plan

See `tasks.md` for detailed task breakdown.

**Phases**:
1. **Bug Fixes**: Fix partition display, initialize retry_tasks, clarify WebSocket behavior
2. **Peer List Broadcast**: Admin sends peer list to new workers via data channel
3. **Worker-to-Worker Connections**: Workers connect to peers using mesh relay signaling
4. **Testing**: Verify full mesh forms and admin departure is seamless

## Risks & Mitigations

### Risk: Connection Explosion
**Impact**: N workers = N*(N-1)/2 connections (10 workers = 45 connections)
**Mitigation**: Room size limit already enforced (max 10 workers)

### Risk: Signaling Complexity
**Impact**: Workers need to relay SDP offers/answers through existing data channels
**Mitigation**: Mesh relay already partially implemented in `mesh_coordinator.py:519-573`

## Open Questions

### Q: Should non-admin workers keep WebSocket open?
**A**: Yes, keep it open. This enables:
- Reconnection to new admin if needed
- Receiving notifications about new workers joining
- Fallback signaling if mesh relay fails

### Q: What happens if worker joins during mesh formation?
**A**: New worker connects to admin first, receives peer list, then connects to others. Existing workers receive "peer joined" notification and connect to new worker.
