# cli

## ADDED Requirements

### Requirement: Browse Command TOTP Authentication

The `browse` command SHALL implement P2P TOTP authentication to authenticate with workers before sending filesystem commands.

#### Scenario: Browse receives AUTH_REQUIRED
- **WHEN** browse establishes WebRTC DataChannel with worker
- **AND** worker sends `AUTH_REQUIRED::{worker_id}` message
- **THEN** browse prompts user for 6-digit OTP code
- **AND** browse tracks authentication state (pending)

#### Scenario: Browse sends AUTH_RESPONSE
- **WHEN** user enters 6-digit OTP code
- **THEN** browse validates code format (exactly 6 digits)
- **AND** browse sends `AUTH_RESPONSE::{otp}` to worker
- **AND** browse waits for authentication result

#### Scenario: Browse handles AUTH_SUCCESS
- **WHEN** browse receives `AUTH_SUCCESS` from worker
- **THEN** browse sets authenticated state to true
- **AND** browse proceeds with filesystem operations
- **AND** browse logs successful authentication

#### Scenario: Browse handles AUTH_FAILURE
- **WHEN** browse receives `AUTH_FAILURE::{reason}` from worker
- **THEN** browse displays error message with reason
- **AND** browse prompts for OTP again (unlimited retries)

#### Scenario: Browse commands blocked before auth
- **WHEN** browse attempts to send FS_* command
- **AND** authenticated state is false
- **THEN** browse queues command until authenticated
- **OR** browse logs error if auth failed

---

### Requirement: Browse Command JWT Authentication Option

The `browse` command SHALL support authentication with stored JWT credentials as an alternative to Cognito anonymous signin.

#### Scenario: Browse with --use-jwt flag
- **WHEN** user runs `sleap-rtc browse --room-id ROOM --token TOKEN --use-jwt`
- **AND** credentials file exists with valid JWT
- **THEN** browse uses JWT for signaling server authentication
- **AND** browse sends JWT in WebSocket register message

#### Scenario: Browse auto-detects stored credentials
- **WHEN** user runs `sleap-rtc browse --room-id ROOM --token TOKEN`
- **AND** credentials file exists with valid JWT
- **THEN** browse uses JWT for signaling server authentication
- **AND** browse logs "Using stored credentials"

#### Scenario: Browse falls back to Cognito
- **WHEN** user runs browse command
- **AND** no credentials file exists
- **THEN** browse uses Cognito anonymous signin
- **AND** browse logs deprecation warning for Cognito auth
