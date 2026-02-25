# authentication

## ADDED Requirements

### Requirement: Client Command JWT Authentication

All client CLI commands (browse, client-train, client-track) SHALL support authentication with stored JWT credentials.

#### Scenario: Client train with stored credentials
- **WHEN** user runs `sleap-rtc client-train --room-id ROOM --token TOKEN`
- **AND** credentials file exists at `~/.sleap-rtc/credentials.json`
- **AND** JWT is not expired
- **THEN** client uses JWT for signaling server registration
- **AND** client sends `{"type": "register", "jwt": "<token>", ...}` message

#### Scenario: Client track with stored credentials
- **WHEN** user runs `sleap-rtc client-track --room-id ROOM --token TOKEN`
- **AND** credentials file exists with valid JWT
- **THEN** client uses JWT for signaling server registration

#### Scenario: Client with explicit --use-jwt flag
- **WHEN** user provides `--use-jwt` flag
- **AND** no credentials file exists
- **THEN** client returns error indicating login required
- **AND** error message suggests running `sleap-rtc login`

#### Scenario: Client with --no-jwt flag
- **WHEN** user provides `--no-jwt` flag
- **THEN** client uses Cognito anonymous signin
- **AND** client does not attempt to read credentials file

---

### Requirement: Cognito Auth Deprecation Warning

Client commands SHALL warn users when using Cognito anonymous signin, as it is deprecated in favor of GitHub OAuth.

#### Scenario: Deprecation warning on Cognito fallback
- **WHEN** client uses Cognito anonymous signin
- **THEN** client logs warning message
- **AND** warning indicates Cognito auth is deprecated
- **AND** warning suggests running `sleap-rtc login`

#### Scenario: No warning with JWT auth
- **WHEN** client authenticates with stored JWT
- **THEN** client does not show deprecation warning

---

### Requirement: OTP Code Retrieval from Credentials

Client commands SHALL retrieve OTP secrets from stored credentials to auto-generate TOTP codes when available.

#### Scenario: Auto-generate OTP from stored secret
- **WHEN** client receives AUTH_REQUIRED from worker
- **AND** credentials file contains otp_secret for current room
- **THEN** client generates TOTP code automatically
- **AND** client sends AUTH_RESPONSE without user prompt
- **AND** client logs "Auto-authenticated with stored OTP secret"

#### Scenario: Prompt for OTP when no stored secret
- **WHEN** client receives AUTH_REQUIRED from worker
- **AND** credentials file does not contain otp_secret for room
- **THEN** client prompts user for 6-digit OTP code

#### Scenario: OTP auto-generation with --otp-secret flag
- **WHEN** user provides `--otp-secret SECRET` on command line
- **AND** client receives AUTH_REQUIRED
- **THEN** client generates TOTP from provided secret
- **AND** command-line secret takes precedence over stored secret
