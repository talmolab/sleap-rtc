# worker-peer-messaging Specification

## Purpose
TBD - created by archiving change refactor-worker-modular. Update Purpose after archive.
## Requirements
### Requirement: Peer Message Sending

The job coordinator SHALL send application-level messages to peers via signaling server peer_message routing.

#### Scenario: Send job response to client

- **WHEN** worker accepts job request
- **THEN** coordinator SHALL send peer_message to client peer_id
- **AND** include app_message_type "job_response"
- **AND** include job_id, accepted status, and estimated duration

#### Scenario: WebSocket not available

- **WHEN** attempting to send peer message but websocket is None
- **THEN** coordinator SHALL log error
- **AND** NOT raise exception (graceful degradation)

### Requirement: Job Request Handling

The job coordinator SHALL evaluate incoming job requests and respond with acceptance or rejection.

#### Scenario: Accept compatible job when available

- **WHEN** job request received while worker status is "available"
- **AND** worker capabilities match job requirements
- **THEN** coordinator SHALL estimate job duration
- **AND** send job_response with accepted=True
- **AND** update worker status to "reserved" with pending_job_id

#### Scenario: Reject job when busy

- **WHEN** job request received while worker status is "busy"
- **THEN** coordinator SHALL send job_response with accepted=False
- **AND** include reason="busy"
- **AND** NOT update worker status

#### Scenario: Reject incompatible job

- **WHEN** job request received but worker lacks required GPU memory
- **THEN** coordinator SHALL send job_response with accepted=False
- **AND** include reason="incompatible"
- **AND** log incompatibility reason

### Requirement: Job Assignment Handling

The job coordinator SHALL handle job assignment from client and prepare for job execution.

#### Scenario: Store job assignment details

- **WHEN** job_assignment message received from client
- **THEN** coordinator SHALL update worker status to "busy"
- **AND** store job_id, client_id, and assigned_at timestamp in current_job
- **AND** log "Job assigned and ready for WebRTC connection"

#### Scenario: Client initiates RTC connection

- **WHEN** job assignment is stored
- **THEN** coordinator SHALL wait for client to initiate WebRTC data channel
- **AND** existing on_datachannel handler will handle data transfer

### Requirement: Job Cancellation Handling

The job coordinator SHALL handle cancellation requests and clean up job state.

#### Scenario: Cancel active job

- **WHEN** job_cancel message received for current_job
- **THEN** coordinator SHALL send job_cancelled acknowledgment to client
- **AND** include status="cancelled" and cleanup_complete=True
- **AND** clear current_job state
- **AND** update worker status to "available"

#### Scenario: Cancel non-existent job

- **WHEN** job_cancel received for job_id not matching current_job
- **THEN** coordinator SHALL log warning
- **AND** NOT send acknowledgment
- **AND** NOT change worker status

### Requirement: Peer Message Routing

The job coordinator SHALL route incoming peer messages to appropriate handlers based on message type.

#### Scenario: Route job_request message

- **WHEN** peer_message with app_message_type="job_request" received
- **THEN** coordinator SHALL call _handle_job_request handler
- **AND** pass client peer_id and payload

#### Scenario: Route job_assignment message

- **WHEN** peer_message with app_message_type="job_assignment" received
- **THEN** coordinator SHALL call _handle_job_assignment handler

#### Scenario: Route job_cancel message

- **WHEN** peer_message with app_message_type="job_cancel" received
- **THEN** coordinator SHALL call _handle_job_cancel handler

#### Scenario: Unhandled peer message type

- **WHEN** peer_message with unknown app_message_type received
- **THEN** coordinator SHALL log warning with message type
- **AND** NOT raise exception

### Requirement: Job Status Updates

The job coordinator SHALL send periodic job status updates to client during execution.

#### Scenario: Send job starting status

- **WHEN** training job begins execution
- **THEN** coordinator SHALL send job_status message to client
- **AND** include status="starting", progress=0.0, message with job name

#### Scenario: Send job completion status

- **WHEN** training job completes successfully
- **THEN** coordinator SHALL send job_status or job_complete message
- **AND** include progress=1.0, training duration, model size if available

#### Scenario: Send job failure status

- **WHEN** job execution fails with exception or non-zero exit code
- **THEN** coordinator SHALL send job_failed message
- **AND** include error code, message, and recoverable flag

