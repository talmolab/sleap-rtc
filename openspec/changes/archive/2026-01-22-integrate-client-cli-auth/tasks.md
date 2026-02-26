# Tasks

## P0 - Critical (Unblocks Browse Command)

- [x] Add auth state tracking to BrowseClient (`rtc_browse.py`)
  - Add `_authenticated`, `_auth_required` instance variables
  - Add `_auth_event` for async coordination

- [x] Import AUTH_* protocol constants in browse module
  - Import `MSG_AUTH_REQUIRED`, `MSG_AUTH_RESPONSE`, `MSG_AUTH_SUCCESS`, `MSG_AUTH_FAILURE` from protocol.py
  - Import `parse_message`, `format_message` helpers

- [x] Implement `_handle_auth_required()` method in BrowseClient
  - Prompt user for 6-digit OTP code
  - Validate code format (exactly 6 digits)
  - Send `AUTH_RESPONSE::{otp}` via data channel
  - Unlimited retries on invalid format

- [x] Implement `_handle_auth_success()` method in BrowseClient
  - Set `_authenticated = True`
  - Log success message
  - Signal any waiting operations

- [x] Implement `_handle_auth_failure()` method in BrowseClient
  - Display error message with reason
  - Prompt for OTP again (unlimited retries)

- [x] Add AUTH_* message handling to `_handle_worker_message()`
  - Handle `MSG_AUTH_REQUIRED` - call `_handle_auth_required()`
  - Handle `MSG_AUTH_SUCCESS` - call `_handle_auth_success()`
  - Handle `MSG_AUTH_FAILURE` - call `_handle_auth_failure()`

- [x] Gate FS_* commands on authentication state
  - Check `_authenticated` before sending filesystem commands
  - Return early with warning if not authenticated

- [ ] Test browse TOTP flow manually
  - Start worker with TOTP enabled
  - Connect with browse, verify OTP prompt appears
  - Verify successful auth allows FS_* commands
  - Verify failed auth blocks commands

## P1 - JWT Credential Integration

- [x] Create `get_valid_jwt()` helper in auth/credentials.py
  - Read JWT from `~/.sleap-rtc/credentials.json`
  - Check expiration, return None if expired
  - Return JWT string if valid

- [x] Add `--use-jwt` and `--no-jwt` flags to browse command
  - `--use-jwt`: require JWT auth, error if no credentials
  - `--no-jwt`: force Cognito auth

- [x] Update browse WebSocket registration to use JWT
  - If credentials exist, send `{"type": "register", "jwt": "..."}`
  - Fall back to Cognito id_token if no JWT

- [x] Add `--use-jwt` and `--no-jwt` flags to client-train command
  - Same behavior as browse

- [x] Add `--use-jwt` and `--no-jwt` flags to client-track command
  - Same behavior as browse

- [x] Update client-train WebSocket registration to use JWT
  - Replace Cognito anonymous signin with JWT when available

- [x] Update client-track WebSocket registration to use JWT
  - Replace Cognito anonymous signin with JWT when available

- [x] Add Cognito deprecation warning
  - Log warning when using anonymous signin
  - Suggest `sleap-rtc login` command

## P2 - Auto-OTP from Stored Credentials

- [x] Create `get_stored_otp_secret(room_id)` helper
  - Read otp_secret from credentials file for given room
  - Return None if not found

- [x] Create `generate_totp(secret)` helper
  - Generate current 6-digit TOTP code from secret
  - Use pyotp library (already available)

- [x] Update client-train TOTP handler to auto-generate
  - Check for stored secret before prompting
  - Auto-send OTP if secret available

- [x] Update client-track TOTP handler to auto-generate
  - Same as client-train

- [x] Update browse TOTP handler to auto-generate
  - Same as client-train

- [x] Add `--otp-secret` CLI option to all client commands
  - Accept Base32 secret string
  - Override stored secret if provided
