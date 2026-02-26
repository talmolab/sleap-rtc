# authentication Specification

## Purpose
TBD - created by archiving change add-github-oauth-auth. Update Purpose after archive.
## Requirements
### Requirement: GitHub OAuth Login

The system SHALL authenticate users via GitHub OAuth, issuing a JWT upon successful login.

#### Scenario: Successful GitHub OAuth login
- **WHEN** user completes GitHub OAuth flow with valid authorization code
- **THEN** system exchanges code for GitHub access token
- **AND** fetches user info (id, username, avatar_url)
- **AND** creates or updates user record in database
- **AND** returns JWT with 7-day expiration

#### Scenario: Invalid authorization code
- **WHEN** user provides invalid or expired authorization code
- **THEN** system returns 401 Unauthorized error
- **AND** does not create user record

---

### Requirement: JWT Verification

The system SHALL verify JWTs using RS256 asymmetric signing, allowing clients to authenticate with Bearer tokens.

#### Scenario: Valid JWT authentication
- **WHEN** request includes `Authorization: Bearer <jwt>` header
- **AND** JWT signature is valid
- **AND** JWT is not expired
- **THEN** system extracts user_id from JWT claims
- **AND** allows request to proceed

#### Scenario: Expired JWT
- **WHEN** request includes JWT that has passed its `exp` claim
- **THEN** system returns 401 Unauthorized
- **AND** error message indicates token expiration

#### Scenario: Invalid JWT signature
- **WHEN** request includes JWT with tampered or invalid signature
- **THEN** system returns 401 Unauthorized

---

### Requirement: Worker Token Generation

The system SHALL allow authenticated users to generate API keys for workers, scoped to specific rooms.

#### Scenario: Create worker token
- **WHEN** authenticated user requests new token for room they have access to
- **AND** provides worker_name and optional expiry duration
- **THEN** system generates API key with `slp_` prefix
- **AND** stores token record in database
- **AND** returns api_key, room_id, expires_at

#### Scenario: Create token for unauthorized room
- **WHEN** authenticated user requests token for room they do not have access to
- **THEN** system returns 403 Forbidden

#### Scenario: List user tokens
- **WHEN** authenticated user requests token list
- **THEN** system returns all tokens owned by user

#### Scenario: Revoke token
- **WHEN** authenticated user revokes a token they own
- **THEN** system sets revoked_at timestamp
- **AND** token is immediately invalid for new connections

### Requirement: Worker API Key Authentication

The system SHALL authenticate workers using API keys, extracting room authorization from the token record.

#### Scenario: Worker connects with valid API key
- **WHEN** worker sends WebSocket register message with `api_key` field
- **AND** API key exists in database
- **AND** API key is not expired or revoked
- **THEN** system extracts room_id from token record
- **AND** allows worker to join that room

#### Scenario: Worker connects with revoked API key
- **WHEN** worker sends register message with revoked API key
- **THEN** system returns error "Token revoked"
- **AND** closes WebSocket connection

#### Scenario: Worker connects with expired API key
- **WHEN** worker sends register message with expired API key
- **THEN** system returns error "Token expired"
- **AND** closes WebSocket connection

---

### Requirement: Room Membership Management

The system SHALL track user membership in rooms, supporting owner and member roles.

#### Scenario: Room creator becomes owner
- **WHEN** authenticated user creates a new room
- **THEN** system creates room_membership record with role "owner"

#### Scenario: Generate room invite
- **WHEN** room owner requests invite code
- **THEN** system generates short-lived invite code (1 hour default)
- **AND** returns invite code and expiration

#### Scenario: Join room with invite
- **WHEN** authenticated user provides valid invite code
- **THEN** system creates room_membership record with role "member"
- **AND** returns room info

#### Scenario: List user rooms
- **WHEN** authenticated user requests room list
- **THEN** system returns all rooms user is member of
- **AND** includes role and joined_at for each

---

### Requirement: CLI Authentication Commands

The CLI SHALL provide commands for user authentication and credential management.

#### Scenario: CLI login
- **WHEN** user runs `sleap-rtc login`
- **THEN** CLI opens browser to GitHub OAuth URL
- **AND** receives callback with authorization code
- **AND** exchanges code for JWT via signaling server
- **AND** saves JWT to `~/.sleap-rtc/credentials.json`

#### Scenario: CLI logout
- **WHEN** user runs `sleap-rtc logout`
- **THEN** CLI removes credentials file

#### Scenario: CLI whoami
- **WHEN** user runs `sleap-rtc whoami`
- **AND** credentials file exists with valid JWT
- **THEN** CLI displays username and user_id

---

### Requirement: CLI Token Commands

The CLI SHALL provide commands for worker token management.

#### Scenario: Create token via CLI
- **WHEN** user runs `sleap-rtc token create --room <id> --name <name>`
- **AND** user is authenticated
- **THEN** CLI creates token via API
- **AND** displays API key
- **AND** shows example Docker/CLI commands

#### Scenario: List tokens via CLI
- **WHEN** user runs `sleap-rtc token list`
- **AND** user is authenticated
- **THEN** CLI displays table of tokens with name, room, expiry, status

#### Scenario: Revoke token via CLI
- **WHEN** user runs `sleap-rtc token revoke <token_id>`
- **AND** user is authenticated
- **THEN** CLI revokes token via API
- **AND** confirms revocation

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

### Requirement: Worker Token Environment Variables

Workers SHALL support authentication via environment variables for Docker deployments.

#### Scenario: Worker auth via environment
- **WHEN** worker starts with `SLEAP_RTC_TOKEN` environment variable set
- **THEN** worker uses that API key for signaling server authentication

#### Scenario: Environment overrides credential file
- **WHEN** both environment variable and credential file contain tokens
- **THEN** environment variable takes precedence

### Requirement: Client Command JWT Authentication

All client CLI commands (browse, client-train, client-track, resolve-paths) SHALL require authentication with stored JWT credentials.

#### Scenario: Client train with stored credentials
- **WHEN** user runs `sleap-rtc client-train --room-id ROOM --token TOKEN --pkg-path PATH`
- **AND** credentials file exists at `~/.sleap-rtc/credentials.json`
- **AND** JWT is not expired
- **THEN** client uses JWT for signaling server registration
- **AND** client sends `{"type": "register", "jwt": "<token>", ...}` message

#### Scenario: Client track with stored credentials
- **WHEN** user runs `sleap-rtc client-track --room-id ROOM --token TOKEN --data-path PATH --model-paths M1 M2`
- **AND** credentials file exists with valid JWT
- **THEN** client uses JWT for signaling server registration

#### Scenario: Client without credentials
- **WHEN** user runs any client command
- **AND** no credentials file exists or JWT is expired
- **THEN** client returns error indicating login required
- **AND** error message suggests running `sleap-rtc login`

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

