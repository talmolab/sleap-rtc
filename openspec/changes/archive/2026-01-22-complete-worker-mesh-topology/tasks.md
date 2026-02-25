# Implementation Tasks: Complete Worker Mesh Topology

## Overview

This document breaks down the implementation into phases with specific, actionable tasks.

**Dependencies**: None - Can start immediately

**Estimated Effort**: 2-3 days

---

## Phase 1: Bug Fixes

**Goal**: Fix critical bugs in current mesh implementation

### 1.1 Fix Partition Status Display Bug
- [ ] In `worker_class.py:_check_partition_status()`, set `self.is_partitioned = is_now_partitioned` BEFORE calling handlers
- [ ] Verify `_log_connection_health()` shows correct partition status in logs

**File**: `sleap_rtc/worker/worker_class.py` (~5 lines)

**Before** (buggy):
```python
async def _check_partition_status(self):
    was_partitioned = self.is_partitioned
    is_now_partitioned = self._detect_partition()
    if was_partitioned != is_now_partitioned:
        if is_now_partitioned:
            await self._on_partition_detected()  # logs health with OLD value
    self.is_partitioned = is_now_partitioned  # set AFTER handler
```

**After** (fixed):
```python
async def _check_partition_status(self):
    was_partitioned = self.is_partitioned
    is_now_partitioned = self._detect_partition()
    self.is_partitioned = is_now_partitioned  # set BEFORE handler
    if was_partitioned != is_now_partitioned:
        if is_now_partitioned:
            await self._on_partition_detected()  # logs correct value
```

**Acceptance**: Logs show "Partition status: ✗ PARTITIONED" immediately when partition detected

### 1.2 Initialize retry_tasks Attribute
- [ ] Add `self.retry_tasks: Dict[str, asyncio.Task] = {}` in `RTCWorkerClient.__init__`
- [ ] Verify no `AttributeError` when reconnection attempts start

**File**: `sleap_rtc/worker/worker_class.py` (~1 line)

**Acceptance**: No `AttributeError: 'RTCWorkerClient' object has no attribute 'retry_tasks'` in logs

### 1.3 Clarify WebSocket Behavior for Non-Admin Workers
- [ ] Document that non-admin workers keep WebSocket open (intentional, enables reconnection)
- [ ] Update comment at `worker_class.py:1194` to reflect actual behavior
- [ ] Optionally add explicit `# WebSocket kept open for reconnection` comment

**File**: `sleap_rtc/worker/worker_class.py` (~3 lines - comments only)

**Acceptance**: Code comments accurately describe WebSocket behavior

---

## Phase 2: Peer List Broadcast

**Goal**: Admin sends peer list to newly connected workers

### 2.1 Create Peer List Message Type
- [ ] Add `MSG_MESH_PEER_LIST = "mesh_peer_list"` constant (already exists at `mesh_coordinator.py:47`)
- [ ] Define peer list message format with peer_ids and metadata

**Message Format**:
```json
{
  "type": "mesh_peer_list",
  "peer_ids": ["worker-2", "worker-3", "worker-4"],
  "peer_metadata": {
    "worker-2": {"gpu_memory_mb": 16000, "status": "available"},
    "worker-3": {"gpu_memory_mb": 24000, "status": "busy"}
  }
}
```

**Acceptance**: Message type defined and documented

### 2.2 Admin Sends Peer List on New Connection
- [ ] In `mesh_coordinator.py:_handle_signaling_offer()`, after connection established:
  - Get list of connected peers from `self.connected_peers`
  - Get metadata from CRDT state
  - Send `mesh_peer_list` message to newly connected worker via data channel
- [ ] Log peer list sent

**File**: `sleap_rtc/worker/mesh_coordinator.py` (~20 lines)

**Acceptance**: New worker receives peer list within 1 second of connecting to admin

### 2.3 Worker Handles Peer List Message
- [ ] Implement `_handle_peer_list()` handler (partially exists at `mesh_coordinator.py:802`)
- [ ] Parse peer_ids from message
- [ ] Filter out self and admin (already connected)
- [ ] Trigger connections to remaining peers

**File**: `sleap_rtc/worker/mesh_coordinator.py` (~15 lines)

**Acceptance**: Worker receives peer list and initiates connections to all listed peers

---

## Phase 3: Worker-to-Worker Connections

**Goal**: Non-admin workers connect to each other via mesh relay

### 3.1 Implement Mesh Relay for SDP Offers
- [ ] In `_connect_to_worker()`, send SDP offer via admin's data channel (not WebSocket)
- [ ] Include `to_peer_id` in message for routing
- [ ] Admin relays message to target worker

**Message Format** (worker -> admin -> target worker):
```json
{
  "type": "mesh_offer",
  "from_peer_id": "worker-3",
  "to_peer_id": "worker-2",
  "offer": {"sdp": "...", "type": "offer"}
}
```

**File**: `sleap_rtc/worker/mesh_coordinator.py` (~30 lines)

**Acceptance**: Worker can send SDP offer to another worker via admin relay

### 3.2 Admin Relays Mesh Messages
- [ ] Implement `_relay_mesh_message()` (partially exists at `mesh_coordinator.py:519-573`)
- [ ] Route messages based on `to_peer_id` field
- [ ] Forward to target worker's data channel
- [ ] Handle case where target worker not connected

**File**: `sleap_rtc/worker/mesh_coordinator.py` (~25 lines)

**Acceptance**: Admin successfully relays SDP offer from worker-3 to worker-2

### 3.3 Target Worker Handles Relayed Offer
- [ ] Handle `mesh_offer` message in `_handle_mesh_message()`
- [ ] Create peer connection for offering worker
- [ ] Generate and send answer back via admin relay
- [ ] Exchange ICE candidates via admin relay

**File**: `sleap_rtc/worker/mesh_coordinator.py` (~40 lines)

**Acceptance**: Two workers establish direct RTC connection via admin relay

### 3.4 Trigger Mesh Formation After Admin Connection
- [ ] After receiving peer list, call `connect_to_workers_batched()` for all peers
- [ ] Track mesh formation progress
- [ ] Log mesh formation complete when all connections established

**File**: `sleap_rtc/worker/mesh_coordinator.py` (~10 lines)

**Acceptance**: 5 workers form full mesh (10 connections) within 10 seconds

---

## Phase 4: Admin Verification & Departure Handling

**Goal**: Verify elected admin is alive and handle seamless admin departure

### 4.1 Implement Admin Verification Ping
- [ ] Add `MSG_ADMIN_VERIFY = "admin_verify"` and `MSG_ADMIN_VERIFY_ACK = "admin_verify_ack"` message types
- [ ] In `run_election()`, after computing winner:
  - If elected admin is NOT self, send `admin_verify` ping via data channel
  - Wait up to 2 seconds for `admin_verify_ack` response
  - If no response, remove elected peer from CRDT and re-run election
- [ ] Implement `_handle_admin_verify()` - respond with `admin_verify_ack`
- [ ] Implement `_verify_admin_alive(peer_id, timeout=2.0)` helper

**File**: `sleap_rtc/worker/admin_controller.py` (~40 lines)

**Message Protocol**:
```json
// Non-admin -> Elected admin
{"type": "admin_verify", "from_peer_id": "ba43..."}

// Elected admin -> Non-admin
{"type": "admin_verify_ack", "from_peer_id": "36ba..."}
```

**Acceptance**: If elected admin doesn't respond within 2s, re-election runs without them

### 4.2 Verify No Reconnection Needed (Full Mesh)
- [ ] Test scenario: 3 workers ("62" admin, "36", "ba") in full mesh
- [ ] Admin "62" leaves
- [ ] Verify "36" and "ba" still connected via direct RTC link
- [ ] Verify re-election happens without connection loss

**Acceptance**: When admin leaves, remaining workers maintain direct connection - no reconnection attempts

### 4.3 Update admin_peer_id Without Reconnection
- [ ] In `_handle_admin_disconnect()`, after re-election:
  - Update `self.admin_peer_id` to new admin
  - Skip reconnection if already connected to new admin
- [ ] Log "Already connected to new admin" instead of starting reconnection

**File**: `sleap_rtc/worker/worker_class.py` (~5 lines)

**Acceptance**: No reconnection attempts when already connected to new admin

### 4.4 New Admin Opens WebSocket for Discovery
- [ ] Verify `on_admin_promotion()` opens WebSocket correctly
- [ ] New admin accepts connections from future workers
- [ ] Existing mesh remains intact

**Acceptance**: New admin ready to accept new workers while mesh continues operating

---

## Phase 5: Testing & Validation

**Goal**: Comprehensive testing of full mesh implementation

### 5.1 Unit Tests for Bug Fixes
- [ ] Test partition status set before handler called
- [ ] Test retry_tasks initialized correctly
- [ ] Test WebSocket remains open for non-admin

**Files Created**: `tests/worker/test_mesh_bug_fixes.py` (~50 lines)

### 5.2 Integration Test: Full Mesh Formation
- [ ] Test 3 workers form full mesh (3 connections)
- [ ] Test 5 workers form full mesh (10 connections)
- [ ] Verify all workers can send messages to all others

**Files Created**: `tests/integration/test_full_mesh.py` (~100 lines)

### 5.3 Integration Test: Admin Departure
- [ ] Test admin leaves, workers maintain connections
- [ ] Test re-election happens correctly
- [ ] Test new admin accepts new workers
- [ ] Verify no "reconnecting" logs for existing connections

**Files Created**: `tests/integration/test_admin_departure.py` (~80 lines)

### 5.4 Manual Testing Checklist
- [ ] Start 3 workers in same room
- [ ] Verify all 3 connections established (full mesh)
- [ ] Stop admin worker
- [ ] Verify remaining 2 workers still connected
- [ ] Verify correct partition status logging
- [ ] Start new worker, verify joins mesh

**Acceptance**: All manual tests pass

---

## Summary

**Total Tasks**: 20 tasks across 5 phases
**Estimated Effort**: 2-3 days
**Critical Path**: Phase 1 (bugs) → Phase 2 (peer list) → Phase 3 (connections) → Phase 4 (departure)

**Success Criteria**:
- No `AttributeError` for retry_tasks
- Partition status logged correctly
- Workers connect to ALL other workers (full mesh)
- Admin departure causes zero reconnection (already connected)

**Next Step**: Begin Phase 1 (Bug Fixes) immediately.
