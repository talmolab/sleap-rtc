## ADDED Requirements

### Requirement: Room Secret Generation

The system SHALL allow users to generate cryptographically secure room secrets for P2P authentication, without the secret ever touching the signaling server.

#### Scenario: Generate secret via dashboard
- **WHEN** user clicks "Generate Secret" in dashboard room settings
- **THEN** browser generates 256-bit random secret using Web Crypto API
- **AND** displays secret as base64 string (44 characters)
- **AND** stores secret in browser localStorage keyed by room_id
- **AND** secret is never sent to server

#### Scenario: Re-display secret in dashboard
- **WHEN** user views room settings for a room with stored secret
- **THEN** dashboard retrieves secret from localStorage
- **AND** displays secret with copy button

#### Scenario: Generate secret via CLI
- **WHEN** user runs `sleap-rtc room create-secret`
- **THEN** CLI generates 256-bit random secret using `secrets` module
- **AND** displays secret as base64 string
- **AND** optionally saves to credentials file with `--save` flag

#### Scenario: Secret format
- **WHEN** secret is generated
- **THEN** secret is exactly 32 bytes (256 bits) of cryptographic random data
- **AND** encoded as URL-safe base64 (no padding)

---

### Requirement: P2P Challenge-Response Authentication

Workers SHALL challenge clients to prove knowledge of the room secret before accepting commands, using HMAC-SHA256.

#### Scenario: Worker challenges client
- **WHEN** WebRTC data channel opens between worker and client
- **AND** worker has room secret configured
- **THEN** worker generates 32-byte random nonce
- **AND** worker sends `AUTH_CHALLENGE::{base64_nonce}` message

#### Scenario: Client responds to challenge
- **WHEN** client receives `AUTH_CHALLENGE::{nonce}` message
- **AND** client has room secret available
- **THEN** client computes `HMAC-SHA256(secret, base64_decode(nonce))`
- **AND** client sends `AUTH_RESPONSE::{base64_hmac}` message

#### Scenario: Successful authentication
- **WHEN** worker receives `AUTH_RESPONSE::{hmac}` message
- **AND** HMAC matches expected value
- **THEN** worker sends `AUTH_SUCCESS` message
- **AND** worker accepts subsequent commands from client

#### Scenario: Failed authentication
- **WHEN** worker receives `AUTH_RESPONSE::{hmac}` message
- **AND** HMAC does not match expected value
- **THEN** worker sends `AUTH_FAILURE::invalid` message
- **AND** worker closes data channel
- **AND** no retry is allowed

#### Scenario: Client missing secret
- **WHEN** client receives `AUTH_CHALLENGE` message
- **AND** client has no room secret available
- **THEN** client sends `AUTH_RESPONSE::missing`
- **AND** worker sends `AUTH_FAILURE::missing`
- **AND** worker closes data channel

#### Scenario: Challenge timeout
- **WHEN** worker sends `AUTH_CHALLENGE` message
- **AND** no `AUTH_RESPONSE` received within 10 seconds
- **THEN** worker sends `AUTH_FAILURE::timeout`
- **AND** worker closes data channel

#### Scenario: Worker without secret (legacy mode)
- **WHEN** WebRTC data channel opens
- **AND** worker has no room secret configured
- **THEN** worker does not send `AUTH_CHALLENGE`
- **AND** worker accepts commands immediately (backward compatible)

#### Scenario: Commands before authentication
- **WHEN** client sends command before authentication completes
- **AND** worker has room secret configured
- **THEN** worker ignores command
- **AND** worker does not send error response

---

### Requirement: Room Secret Storage

The CLI SHALL store room secrets in the credentials file for persistent access across sessions.

#### Scenario: Save secret to credentials
- **WHEN** user runs `sleap-rtc room create-secret --save`
- **OR** user provides secret that successfully authenticates
- **THEN** secret is saved to `~/.sleap-rtc/credentials.json`
- **AND** stored under `room_secrets.<room_id>` key

#### Scenario: Credential file structure with secrets
- **WHEN** secrets are stored
- **THEN** credentials file contains `room_secrets` object
- **AND** keys are room IDs
- **AND** values are base64-encoded secrets

#### Scenario: Secret file permissions
- **WHEN** secrets are saved to credentials file
- **THEN** file permissions remain 600 (owner read/write only)

---

### Requirement: Room Secret Lookup

Clients SHALL look up room secrets from multiple sources in priority order.

#### Scenario: Secret from CLI flag
- **WHEN** user provides `--room-secret` CLI flag
- **THEN** client uses that secret for authentication
- **AND** other sources are not checked

#### Scenario: Secret from environment variable
- **WHEN** `SLEAP_ROOM_SECRET` environment variable is set
- **AND** no `--room-secret` CLI flag provided
- **THEN** client uses environment variable value for authentication

#### Scenario: Secret from shared filesystem
- **WHEN** no CLI flag or environment variable provided
- **AND** file exists at secret path `{base_path}/<room_id>`
- **THEN** client reads secret from file

#### Scenario: Configurable secret base path
- **WHEN** `SLEAP_SECRET_PATH` environment variable is set
- **THEN** system uses that path as base for filesystem secret lookup
- **WHEN** `SLEAP_SECRET_PATH` is not set
- **THEN** system uses default `~/.sleap-rtc/room-secrets/`

#### Scenario: Secret from credentials file
- **WHEN** no CLI flag, environment variable, or filesystem secret found
- **AND** credentials file contains `room_secrets.<room_id>`
- **THEN** client uses stored secret for authentication

#### Scenario: No secret available
- **WHEN** no secret found in any source
- **AND** worker requires authentication
- **THEN** client authentication fails with `AUTH_FAILURE::missing`

---

### Requirement: Worker Secret Configuration

Workers SHALL load room secrets from configuration sources for P2P authentication.

#### Scenario: Worker secret from CLI flag
- **WHEN** worker starts with `--room-secret` flag
- **THEN** worker uses that secret for client authentication

#### Scenario: Worker secret from environment variable
- **WHEN** `SLEAP_ROOM_SECRET` environment variable is set
- **AND** no `--room-secret` CLI flag provided
- **THEN** worker uses environment variable value

#### Scenario: Worker secret from config file
- **WHEN** no CLI flag or environment variable provided
- **AND** worker config file contains `room_secret` key
- **THEN** worker uses config file value

#### Scenario: Worker without secret
- **WHEN** no secret configured from any source
- **THEN** worker operates in legacy mode (no P2P authentication)
- **AND** logs warning about missing secret

---

## MODIFIED Requirements

### Requirement: Credential File Storage

The CLI SHALL store credentials in a protected file with restricted permissions.

#### Scenario: Credential file creation
- **WHEN** CLI saves credentials
- **THEN** file is created at `~/.sleap-rtc/credentials.json`
- **AND** file permissions are set to 600 (owner read/write only)

#### Scenario: Credential file structure
- **WHEN** credentials are stored
- **THEN** file contains JSON with jwt, user object, tokens map, and room_secrets map
- **AND** tokens map keys are room_ids
- **AND** tokens map values contain api_key
- **AND** room_secrets map keys are room_ids
- **AND** room_secrets map values are base64-encoded secrets
