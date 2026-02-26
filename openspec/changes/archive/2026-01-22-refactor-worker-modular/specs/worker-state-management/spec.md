# Worker State Management Specification

## ADDED Requirements

### Requirement: Worker Status Updates

The state manager SHALL update worker status on signaling server to reflect current availability.

#### Scenario: Update status to busy

- **WHEN** worker accepts job and begins execution
- **THEN** state manager SHALL send update_metadata message to signaling server
- **AND** include status="busy" and current_job_id in properties
- **AND** set local self.status to "busy"

#### Scenario: Update status to available

- **WHEN** job completes or is cancelled
- **THEN** state manager SHALL send update_metadata with status="available"
- **AND** clear current_job_id from properties

#### Scenario: Update status to reserved

- **WHEN** worker accepts job request but hasn't started execution
- **THEN** state manager SHALL send status="reserved" with pending_job_id

#### Scenario: Status update failure

- **WHEN** websocket send fails during status update
- **THEN** state manager SHALL log error
- **AND** NOT raise exception (local state remains updated)

### Requirement: Worker Re-registration

The state manager SHALL re-register worker with signaling server to become discoverable after reset.

#### Scenario: Re-register after client disconnect

- **WHEN** client disconnects and worker resets peer connection
- **THEN** state manager SHALL send full "register" message
- **AND** include role="worker", metadata with capabilities
- **AND** use stored room_id, room_token, id_token
- **AND** log "Worker re-registered with signaling server"

#### Scenario: Re-registration failure

- **WHEN** websocket send fails during re-registration
- **THEN** state manager SHALL log error
- **AND** worker may not appear in discovery queries

### Requirement: Room Creation

The state manager SHALL create new rooms via HTTP API for worker-initiated sessions.

#### Scenario: Create room with authentication

- **WHEN** worker starts without existing room credentials
- **THEN** state manager SHALL POST to /create-room endpoint
- **AND** include Authorization header with Cognito ID token
- **AND** return room_id and token from response

#### Scenario: Room creation failure

- **WHEN** HTTP request fails with non-200 status
- **THEN** state manager SHALL log error with status and response text
- **AND** raise exception to prevent worker startup

### Requirement: Anonymous Sign-in

The state manager SHALL obtain Cognito ID tokens via anonymous sign-in for worker authentication.

#### Scenario: Request anonymous token

- **WHEN** worker starts and needs authentication
- **THEN** state manager SHALL POST to /anonymous-signin endpoint
- **AND** return id_token and username from response JSON

#### Scenario: Sign-in failure

- **WHEN** anonymous sign-in request fails
- **THEN** state manager SHALL log error
- **AND** return None (prevents worker startup)

### Requirement: Room Deletion

The state manager SHALL delete rooms and peer entries when worker shuts down.

#### Scenario: Delete peer and room on exit

- **WHEN** worker exits cleanly
- **THEN** state manager SHALL POST to /delete-peer endpoint
- **AND** include peer_id in request body
- **AND** clean up Cognito and DynamoDB entries

#### Scenario: Deletion failure

- **WHEN** HTTP request fails with non-200 status
- **THEN** state manager SHALL log error
- **AND** NOT prevent shutdown (best-effort cleanup)

### Requirement: Session String Generation

The state manager SHALL generate encoded session strings for direct worker connections.

#### Scenario: Generate session string

- **WHEN** worker successfully registers with room
- **THEN** state manager SHALL create base64-encoded JSON
- **AND** include "r" (room_id), "t" (token), "p" (peer_id)
- **AND** return string with "sleap-session:" prefix

#### Scenario: Use session string for client connection

- **WHEN** client provides session string
- **THEN** client can decode to extract room credentials
- **AND** connect directly to specific worker

### Requirement: Worker Registration Lifecycle

The state manager SHALL manage worker registration from startup through re-registration cycles.

#### Scenario: Initial registration on startup

- **WHEN** worker starts via run_worker()
- **THEN** state manager SHALL obtain anonymous ID token
- **AND** create or join room
- **AND** send register message with role="worker" and metadata
- **AND** log registration success with session string

#### Scenario: Periodic status updates during operation

- **WHEN** worker processes jobs during operation
- **THEN** state manager SHALL send update_metadata on status changes
- **AND** NOT re-send full registration

#### Scenario: Re-registration after connection reset

- **WHEN** ICE connection fails and worker resets
- **THEN** state manager SHALL send full register message again
- **AND** ensure worker appears in discovery queries
