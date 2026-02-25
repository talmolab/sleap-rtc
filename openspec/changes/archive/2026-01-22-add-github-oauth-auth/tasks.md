# Implementation Tasks

## Phase 1: Infrastructure Setup

### 1.1 DynamoDB Tables
- [ ] 1.1.1 Create `sleap_users` table with `user_id` PK and `username-index` GSI
- [ ] 1.1.2 Create `sleap_worker_tokens` table with `token_id` PK, `user_id-index` and `room_id-index` GSIs
- [ ] 1.1.3 Create `sleap_room_memberships` table with composite PK (`user_id`, `room_id`) and `room_id-index` GSI
- [ ] 1.1.4 Document table schemas in infrastructure docs

### 1.2 GitHub OAuth App
- [ ] 1.2.1 Create GitHub OAuth App in organization settings
- [ ] 1.2.2 Configure callback URL to GitHub Pages dashboard
- [ ] 1.2.3 Store Client ID and Client Secret securely
- [ ] 1.2.4 Add environment variables to signaling server EC2

### 1.3 JWT Key Pair
- [ ] 1.3.1 Generate RS256 key pair for JWT signing
- [ ] 1.3.2 Store private key securely on signaling server
- [ ] 1.3.3 Make public key available for dashboard verification
- [ ] 1.3.4 Add `SLEAP_JWT_PRIVATE_KEY` and `SLEAP_JWT_PUBLIC_KEY` env vars

## Phase 2: Signaling Server Auth Endpoints

### 2.1 JWT Utilities (webRTC-connect repo)
- [ ] 2.1.1 Create `auth/jwt.py` with `generate_jwt()` and `verify_jwt()` functions
- [ ] 2.1.2 Use RS256 algorithm with configured key pair
- [ ] 2.1.3 Add JWT claims: `sub`, `username`, `iat`, `exp`, `iss`
- [ ] 2.1.4 Default expiration: 7 days

### 2.2 GitHub OAuth Endpoint
- [ ] 2.2.1 Add `POST /api/auth/github/callback` endpoint
- [ ] 2.2.2 Exchange authorization code for GitHub access token
- [ ] 2.2.3 Fetch GitHub user info (id, username, avatar_url)
- [ ] 2.2.4 Create/update user in `sleap_users` table
- [ ] 2.2.5 Generate and return SLEAP-RTC JWT
- [ ] 2.2.6 Add tests for OAuth flow

### 2.3 Token Management Endpoints
- [ ] 2.3.1 Add `POST /api/auth/token` - create worker token
  - [ ] Validate JWT from Authorization header
  - [ ] Verify user has access to requested room
  - [ ] Generate API key (`slp_` + 32 char base64)
  - [ ] Generate OTP secret (Base32, 160-bit)
  - [ ] Store in `sleap_worker_tokens` table
  - [ ] Return token_id, otp_secret, room_id, expires_at
- [ ] 2.3.2 Add `GET /api/auth/tokens` - list user's tokens
  - [ ] Query by user_id GSI
  - [ ] Return tokens without otp_secret
- [ ] 2.3.3 Add `DELETE /api/auth/token/:token_id` - revoke token
  - [ ] Set `revoked_at` timestamp
  - [ ] Return confirmation

### 2.4 Room Management Endpoints
- [ ] 2.4.1 Add `GET /api/auth/rooms` - list user's rooms
  - [ ] Query `room_memberships` by user_id
  - [ ] Return room_id, role, joined_at
- [ ] 2.4.2 Add `POST /api/auth/rooms/:room_id/invite` - generate invite code
  - [ ] Verify user is owner of room
  - [ ] Generate short-lived invite code
  - [ ] Store invite in memory or DynamoDB
- [ ] 2.4.3 Add `POST /api/auth/rooms/join` - join room with invite code
  - [ ] Validate invite code
  - [ ] Add membership record
  - [ ] Return room info

### 2.5 WebSocket Auth Modification
- [ ] 2.5.1 Modify `handle_register()` to accept `api_key` for workers
- [ ] 2.5.2 Look up token in `sleap_worker_tokens` table
- [ ] 2.5.3 Extract `room_id` from token record
- [ ] 2.5.4 Validate token not expired or revoked
- [ ] 2.5.5 Modify `handle_register()` to accept `jwt` for clients
- [ ] 2.5.6 Replace `verify_cognito_token()` with `verify_jwt()`
- [ ] 2.5.7 Add tests for both auth paths

## Phase 3: SLEAP-RTC CLI Commands

### 3.1 Auth Module
- [ ] 3.1.1 Create `sleap_rtc/auth/__init__.py`
- [ ] 3.1.2 Create `sleap_rtc/auth/credentials.py` for credential file management
  - [ ] Load/save `~/.sleap-rtc/credentials.json`
  - [ ] File permissions: 600
  - [ ] Schema: `{jwt, user, tokens: {room_id: {api_key, otp_secret}}}`
- [ ] 3.1.3 Create `sleap_rtc/auth/github.py` for OAuth flow
  - [ ] Device flow implementation for CLI
  - [ ] Browser-based flow fallback
- [ ] 3.1.4 Create `sleap_rtc/auth/totp.py` for OTP validation
  - [ ] Use `pyotp` library
  - [ ] Validate with ±1 window tolerance

### 3.2 Login Commands
- [ ] 3.2.1 Add `sleap-rtc login` command
  - [ ] Open browser to GitHub OAuth
  - [ ] Receive callback and exchange code
  - [ ] Save JWT to credentials file
- [ ] 3.2.2 Add `sleap-rtc logout` command
  - [ ] Clear credentials file
- [ ] 3.2.3 Add `sleap-rtc whoami` command
  - [ ] Display current user info from JWT

### 3.3 Token Commands
- [ ] 3.3.1 Add `sleap-rtc token create --room <id> --name <name> [--expires <duration>]`
  - [ ] Call `POST /api/auth/token`
  - [ ] Display API key, OTP secret, QR code URI
  - [ ] Optionally save to credentials file
- [ ] 3.3.2 Add `sleap-rtc token list`
  - [ ] Call `GET /api/auth/tokens`
  - [ ] Display table: NAME, ROOM, EXPIRES, STATUS
- [ ] 3.3.3 Add `sleap-rtc token revoke <token_id>`
  - [ ] Call `DELETE /api/auth/token/:id`
  - [ ] Confirm revocation

### 3.4 Room Commands
- [ ] 3.4.1 Add `sleap-rtc room list`
  - [ ] Call `GET /api/auth/rooms`
  - [ ] Display table: ROOM_ID, ROLE, JOINED
- [ ] 3.4.2 Add `sleap-rtc room invite <room_id>`
  - [ ] Call `POST /api/auth/rooms/:id/invite`
  - [ ] Display invite code and expiry
- [ ] 3.4.3 Add `sleap-rtc room join --code <code>`
  - [ ] Call `POST /api/auth/rooms/join`
  - [ ] Confirm join

### 3.5 Worker Modification
- [ ] 3.5.1 Modify `sleap-rtc worker` to accept `--token <api_key>`
- [ ] 3.5.2 Load OTP secret from credentials file or `SLEAP_RTC_OTP_SECRET` env var
- [ ] 3.5.3 Update `state_manager.py` to use API key instead of Cognito

## Phase 4: P2P TOTP Authentication

### 4.1 Protocol Extension
- [ ] 4.1.1 Add AUTH_* message types to `protocol.py`
  - [ ] `AUTH_REQUIRED::{worker_id}`
  - [ ] `AUTH_RESPONSE::{otp}`
  - [ ] `AUTH_SUCCESS`
  - [ ] `AUTH_FAILURE::{reason}`
- [ ] 4.1.2 Document protocol in comments

### 4.2 Worker TOTP Validation
- [ ] 4.2.1 Add `_validate_otp()` method to `RTCWorkerClient`
- [ ] 4.2.2 Send `AUTH_REQUIRED` on DataChannel open
- [ ] 4.2.3 Handle `AUTH_RESPONSE` message
- [ ] 4.2.4 Validate OTP using `pyotp`
- [ ] 4.2.5 Send `AUTH_SUCCESS` or `AUTH_FAILURE`
- [ ] 4.2.6 Set `_authenticated` flag
- [ ] 4.2.7 Reject commands if not authenticated
- [ ] 4.2.8 Add rate limiting on failed attempts

### 4.3 Client OTP Entry
- [ ] 4.3.1 Handle `AUTH_REQUIRED` message in `RTCClient`
- [ ] 4.3.2 Prompt user for OTP code (CLI input)
- [ ] 4.3.3 Send `AUTH_RESPONSE` with OTP
- [ ] 4.3.4 Handle `AUTH_SUCCESS`/`AUTH_FAILURE` responses
- [ ] 4.3.5 Retry on failure (up to 3 attempts)

## Phase 5: GitHub Pages Dashboard

### 5.1 Static Site Setup
- [ ] 5.1.1 Create `dashboard/` directory in sleap-RTC repo
- [ ] 5.1.2 Create `index.html` with login UI
- [ ] 5.1.3 Create `callback.html` for OAuth redirect handling
- [ ] 5.1.4 Configure GitHub Pages deployment

### 5.2 OAuth Flow
- [ ] 5.2.1 Implement "Login with GitHub" button
- [ ] 5.2.2 Redirect to GitHub OAuth with correct params
- [ ] 5.2.3 Handle callback and exchange code via signaling server
- [ ] 5.2.4 Store JWT in localStorage
- [ ] 5.2.5 Display logged-in user info

### 5.3 Token Management UI
- [ ] 5.3.1 Token creation form (room, name, expiry)
- [ ] 5.3.2 Display generated token and OTP secret
- [ ] 5.3.3 Generate QR code for authenticator apps
- [ ] 5.3.4 Display CLI/Docker commands
- [ ] 5.3.5 Token list with revoke buttons
- [ ] 5.3.6 OTP verification tester

### 5.4 Room Management UI
- [ ] 5.4.1 Room list display
- [ ] 5.4.2 Create room button
- [ ] 5.4.3 Generate invite code UI
- [ ] 5.4.4 Join room with code UI

## Phase 6: Migration & Cleanup

### 6.1 Documentation
- [ ] 6.1.1 Update README with new auth flow
- [ ] 6.1.2 Add authentication guide
- [ ] 6.1.3 Document environment variables
- [ ] 6.1.4 Add troubleshooting section

### 6.2 Deprecation
- [ ] 6.2.1 Add deprecation warning to `/anonymous-signin`
- [ ] 6.2.2 Log usage of old auth path
- [ ] 6.2.3 Set deprecation date

### 6.3 Removal (separate PR after migration period)
- [ ] 6.3.1 Remove `/anonymous-signin` endpoint
- [ ] 6.3.2 Remove Cognito environment variables
- [ ] 6.3.3 Remove Cognito verification code
- [ ] 6.3.4 Update project.md to remove Cognito references

## Testing

### Unit Tests
- [ ] T.1 JWT generation and verification
- [ ] T.2 OTP validation with pyotp
- [ ] T.3 Credential file read/write
- [ ] T.4 API key generation

### Integration Tests
- [ ] T.5 GitHub OAuth flow (mock GitHub API)
- [ ] T.6 Token CRUD operations
- [ ] T.7 WebSocket auth with API key
- [ ] T.8 WebSocket auth with JWT
- [ ] T.9 DataChannel TOTP handshake

### End-to-End Tests
- [ ] T.10 Full login → token create → worker connect → client auth flow
