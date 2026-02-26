# Worker Mesh Topology

## ADDED Requirements

### Requirement: Full Mesh Connection Formation

Workers in a room MUST establish direct WebRTC data channel connections to ALL other workers, not just the admin.

#### Scenario: Three workers form full mesh

**Given** workers "A", "B", and "C" join the same room
**And** worker "A" is elected admin
**When** mesh formation completes
**Then** there are 3 direct RTC connections: A↔B, A↔C, B↔C
**And** each worker can send messages directly to any other worker

#### Scenario: New worker joins existing mesh

**Given** workers "A" (admin), "B", and "C" are in a full mesh
**When** worker "D" joins the room
**Then** worker "D" connects to admin "A" via signaling server
**And** admin "A" sends peer list ["B", "C"] to worker "D"
**And** worker "D" establishes direct connections to "B" and "C" via mesh relay
**And** the mesh now has 6 connections: A↔B, A↔C, A↔D, B↔C, B↔D, C↔D

### Requirement: Mesh Relay Signaling

Admin MUST relay SDP offers/answers and ICE candidates between non-admin workers via data channels.

#### Scenario: Worker-to-worker connection via mesh relay

**Given** worker "B" is connected to admin "A"
**And** worker "C" is connected to admin "A"
**When** worker "B" wants to connect to worker "C"
**Then** worker "B" sends mesh_offer to admin "A" with to_peer_id="C"
**And** admin "A" relays mesh_offer to worker "C"
**And** worker "C" sends mesh_answer back via admin "A"
**And** ICE candidates are exchanged via admin "A"
**And** direct B↔C connection is established

### Requirement: Seamless Admin Departure

When admin worker departs, remaining workers MUST maintain their existing direct connections without reconnection.

#### Scenario: Admin leaves full mesh

**Given** workers "A" (admin), "B", and "C" are in a full mesh (3 connections)
**When** admin "A" leaves the room
**Then** workers "B" and "C" still have direct B↔C connection
**And** re-election elects new admin (e.g., "B")
**And** NO reconnection attempts occur between "B" and "C"
**And** new admin "B" opens WebSocket for future worker discovery

### Requirement: Admin Verification After Election

After election, non-admin workers MUST verify the elected admin is reachable before accepting the election result.

#### Scenario: Elected admin is alive and responds

**Given** workers "A" (admin), "B", and "C" are in a room
**And** admin "A" leaves
**When** re-election elects "B" as new admin
**And** worker "C" sends admin_verify ping to "B"
**Then** worker "B" responds with admin_verify_ack within 2 seconds
**And** worker "C" accepts "B" as admin

#### Scenario: Elected admin left during election

**Given** workers "A" (admin), "B", and "C" are in a room
**And** admin "A" leaves
**And** worker "B" also leaves immediately after
**When** re-election elects "B" as new admin
**And** worker "C" sends admin_verify ping to "B"
**And** no response received within 2 seconds
**Then** worker "C" removes "B" from CRDT
**And** worker "C" re-runs election
**And** worker "C" elects itself as admin (only remaining worker)

## MODIFIED Requirements

### Requirement: Partition Detection Status Accuracy

Partition status MUST be updated BEFORE calling partition handlers to ensure accurate logging.

#### Scenario: Partition detected and logged correctly

**Given** worker "B" is connected to admin "A" only (no mesh to other workers)
**When** admin "A" connection is lost
**And** partition is detected (admin lost, connectivity < 50%)
**Then** `is_partitioned` is set to `True` BEFORE `_on_partition_detected()` is called
**And** health log shows "Partition status: ✗ PARTITIONED"
**And** log does NOT show "Partition status: ✓ Healthy" during partition

### Requirement: Retry Tasks Initialization

Worker client MUST initialize `retry_tasks` dictionary to track reconnection attempts.

#### Scenario: Reconnection attempts tracked without error

**Given** worker "B" loses connection to admin "A"
**When** partition is detected and reconnection attempts start
**Then** reconnection tasks are stored in `self.retry_tasks` dict
**And** NO `AttributeError: 'RTCWorkerClient' object has no attribute 'retry_tasks'` occurs

### Requirement: WebSocket Persistence for Non-Admin Workers

Non-admin workers MUST keep their WebSocket connection open to enable reconnection and notifications.

#### Scenario: Non-admin worker retains WebSocket

**Given** worker "B" connects to admin "A" via signaling server
**When** initial WebRTC connection to admin is established
**Then** worker "B" keeps WebSocket connection open
**And** WebSocket can be used for reconnection if needed
**And** WebSocket receives notifications about new workers joining
