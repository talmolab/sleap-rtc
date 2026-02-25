## REMOVED Requirements

### Requirement: P2P TOTP Verification
**Reason**: OTP is redundant with JWT + room membership. The signaling server generates and stores the OTP secret, defeating zero-trust. Auto-resolve stores the secret in the same credentials file as the JWT, collapsing it to single-factor. See `scratch/2026-01-27-otp-removal-case/README.md` for full rationale.
**Migration**: Workers accept commands immediately on data channel open. JWT + room membership gate access at the signaling server. No client-side changes needed beyond removing `--otp-secret` flags.

### Requirement: Cognito Auth Deprecation Warning
**Reason**: Cognito anonymous signin is being removed entirely, not just deprecated. GitHub OAuth + JWT replaces it completely.
**Migration**: Users must run `sleap-rtc login` before using client commands. Clear error messages direct users to login.

### Requirement: OTP Code Retrieval from Credentials
**Reason**: With OTP removed, there is no need to retrieve or auto-generate TOTP codes from stored credentials.
**Migration**: The `otp_secret` field in credentials files is silently ignored. No user action needed.

## MODIFIED Requirements

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
- **AND** tokens map values contain api_key

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
