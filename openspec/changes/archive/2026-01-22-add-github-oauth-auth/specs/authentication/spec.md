# Authentication Capability

## ADDED Requirements

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
- **AND** generates TOTP secret (Base32, 160-bit)
- **AND** stores token record in database
- **AND** returns api_key, otp_secret, room_id, expires_at

#### Scenario: Create token for unauthorized room
- **WHEN** authenticated user requests token for room they do not have access to
- **THEN** system returns 403 Forbidden

#### Scenario: List user tokens
- **WHEN** authenticated user requests token list
- **THEN** system returns all tokens owned by user
- **AND** does not include otp_secret in response

#### Scenario: Revoke token
- **WHEN** authenticated user revokes a token they own
- **THEN** system sets revoked_at timestamp
- **AND** token is immediately invalid for new connections

---

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

### Requirement: P2P TOTP Verification

The system SHALL require clients to provide a valid TOTP code before workers accept commands, using the OTP secret associated with the worker's token.

#### Scenario: Successful TOTP authentication
- **WHEN** WebRTC DataChannel is established between client and worker
- **THEN** worker sends `AUTH_REQUIRED::{worker_id}` message
- **AND** client sends `AUTH_RESPONSE::{otp}` with 6-digit TOTP code
- **AND** worker validates OTP against stored secret with ±1 window tolerance
- **AND** if valid, worker sends `AUTH_SUCCESS`
- **AND** worker accepts subsequent commands

#### Scenario: Invalid TOTP code
- **WHEN** client sends `AUTH_RESPONSE` with invalid OTP code
- **THEN** worker sends `AUTH_FAILURE::invalid_otp`
- **AND** worker allows retry (up to 3 attempts)

#### Scenario: TOTP rate limiting
- **WHEN** client fails 3 consecutive TOTP attempts
- **THEN** worker sends `AUTH_FAILURE::rate_limited`
- **AND** worker closes DataChannel

#### Scenario: Commands before authentication
- **WHEN** client sends command before completing TOTP authentication
- **THEN** worker ignores command
- **AND** sends `AUTH_FAILURE::not_authenticated`

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
- **AND** displays API key, OTP secret, and QR code URI
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

---

### Requirement: Credential File Storage

The CLI SHALL store credentials in a protected file with restricted permissions.

#### Scenario: Credential file creation
- **WHEN** CLI saves credentials
- **THEN** file is created at `~/.sleap-rtc/credentials.json`
- **AND** file permissions are set to 600 (owner read/write only)

#### Scenario: Credential file structure
- **WHEN** credentials are stored
- **THEN** file contains JSON with jwt, user object, and tokens map
- **AND** tokens map keys are room_ids
- **AND** tokens map values contain api_key and otp_secret

---

### Requirement: Worker Token Environment Variables

Workers SHALL support authentication via environment variables for Docker deployments.

#### Scenario: Worker auth via environment
- **WHEN** worker starts with `SLEAP_RTC_TOKEN` environment variable set
- **THEN** worker uses that API key for signaling server authentication

#### Scenario: Worker OTP secret via environment
- **WHEN** worker starts with `SLEAP_RTC_OTP_SECRET` environment variable set
- **THEN** worker uses that secret for P2P TOTP validation

#### Scenario: Environment overrides credential file
- **WHEN** both environment variable and credential file contain tokens
- **THEN** environment variable takes precedence
