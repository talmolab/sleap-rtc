# Worker Connection Management Specification

## ADDED Requirements

### Requirement: WebSocket Message Handling

The connection manager SHALL handle incoming WebSocket messages from signaling server and route to appropriate handlers.

#### Scenario: Receive offer from client

- **WHEN** signaling server forwards "offer" message from client
- **THEN** connection manager SHALL extract sender peer_id
- **AND** check worker status before accepting
- **AND** set remote description from offer SDP
- **AND** create and send answer SDP back to client

#### Scenario: Reject offer when busy

- **WHEN** offer received but worker status is "busy" or "reserved"
- **THEN** connection manager SHALL send "error" response to client
- **AND** include reason="worker_busy" and current status
- **AND** NOT create answer or update peer connection

#### Scenario: Accept offer when available

- **WHEN** offer received and worker status is "available"
- **THEN** connection manager SHALL update status to "reserved"
- **AND** set remote description and create answer
- **AND** send answer to client via signaling server

### Requirement: ICE Connection State Management

The connection manager SHALL monitor ICE connection state and handle reconnection or reset.

#### Scenario: Connection established

- **WHEN** ICE connection state transitions to "connected" or "completed"
- **THEN** connection manager SHALL log success
- **AND** connection is ready for data transfer

#### Scenario: Connection closed by client

- **WHEN** ICE connection state transitions to "closed"
- **THEN** connection manager SHALL close old peer connection
- **AND** create new RTCPeerConnection with event handlers
- **AND** clear current job state
- **AND** re-register worker with signaling server
- **AND** update status to "available"

#### Scenario: Connection failed

- **WHEN** ICE connection state transitions to "failed"
- **THEN** connection manager SHALL reset peer connection
- **AND** re-register worker for new connections

#### Scenario: Connection disconnected

- **WHEN** ICE connection state is "disconnected"
- **THEN** connection manager SHALL wait up to 90 seconds for recovery
- **AND** check every second if state returns to "connected"
- **AND** reset connection if timeout expires

### Requirement: Data Channel Management

The connection manager SHALL handle data channel lifecycle and delegate message routing.

#### Scenario: Data channel created by client

- **WHEN** client creates data channel during connection
- **THEN** connection manager SHALL register "open" and "message" handlers
- **AND** log "channel created by remote party"

#### Scenario: Data channel open

- **WHEN** data channel state transitions to "open"
- **THEN** connection manager SHALL start keep-alive task
- **AND** log "channel is open"

#### Scenario: Route datachannel messages

- **WHEN** message received on data channel
- **THEN** connection manager SHALL parse message type
- **AND** delegate to file manager for FILE_META, SHARED_INPUT_PATH messages
- **AND** delegate to job executor for PACKAGE_TYPE, END_OF_FILE messages
- **AND** delegate to job coordinator for job-related messages

### Requirement: Keep-Alive Mechanism

The connection manager SHALL send periodic keep-alive messages to maintain ICE connection.

#### Scenario: Send keep-alive when channel open

- **WHEN** data channel is open
- **THEN** connection manager SHALL send b"KEEP_ALIVE" every 15 seconds
- **AND** continue until channel closes

#### Scenario: Receive keep-alive

- **WHEN** keep-alive message received
- **THEN** connection manager SHALL log receipt
- **AND** NOT process as data message

### Requirement: Clean Exit

The connection manager SHALL cleanly shutdown all resources during worker exit.

#### Scenario: Graceful shutdown

- **WHEN** worker receives shutdown signal
- **THEN** connection manager SHALL set shutting_down flag
- **AND** close RTCPeerConnection
- **AND** close WebSocket connection
- **AND** request peer/room deletion from signaling server
- **AND** log "Client shutdown complete"

#### Scenario: Shutdown during ICE state change

- **WHEN** ICE state change occurs during shutdown
- **THEN** connection manager SHALL ignore state change
- **AND** NOT attempt reconnection

### Requirement: Worker Lifecycle Management

The connection manager SHALL orchestrate worker startup, operation, and shutdown.

#### Scenario: Worker startup

- **WHEN** run_worker() called
- **THEN** connection manager SHALL register event handlers
- **AND** obtain Cognito ID token
- **AND** create or join room
- **AND** register with signaling server
- **AND** begin listening for client connections

#### Scenario: Keyboard interrupt during startup

- **WHEN** Ctrl+C pressed before connection established
- **THEN** connection manager SHALL call clean_exit()
- **AND** NOT leave orphaned resources

#### Scenario: Keyboard interrupt during operation

- **WHEN** Ctrl+C pressed while processing job
- **THEN** connection manager SHALL interrupt message handling
- **AND** call clean_exit() to cleanup

### Requirement: Registered Authentication

The connection manager SHALL handle registration confirmation from signaling server.

#### Scenario: Registration confirmed

- **WHEN** "registered_auth" message received from server
- **THEN** connection manager SHALL extract room_id, token, peer_id
- **AND** generate session string for direct connection
- **AND** log session string and room credentials
- **AND** display both session string and room-based discovery options
