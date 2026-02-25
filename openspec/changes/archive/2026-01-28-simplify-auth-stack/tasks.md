## 1. Remove Cognito Anonymous Signin

- [x] 1.1 Delete `request_anonymous_signin()` from `sleap_rtc/worker/state_manager.py`
- [x] 1.2 Remove Cognito fallback from `sleap_rtc/client/client_class.py` (replace with JWT-required error)
- [x] 1.3 Remove Cognito fallback from `sleap_rtc/client/client_track_class.py`
- [x] 1.4 Remove Cognito fallback from `sleap_rtc/rtc_browse.py`
- [x] 1.5 Remove Cognito fallback from `sleap_rtc/rtc_resolve.py`
- [x] 1.6 Remove `--no-jwt` flag from CLI commands in `sleap_rtc/cli.py`
- [x] 1.7 Remove `--use-jwt` flag from CLI commands in `sleap_rtc/cli.py` (JWT is now always on)
- [x] 1.8 Add clear error message when credentials are missing: "Run `sleap-rtc login` first"

## 2. Remove P2P TOTP (OTP) — Worker Side

- [x] 2.1 Remove `_otp_secret` field from `WorkerClass` in `sleap_rtc/worker/worker_class.py`
- [x] 2.2 Remove `_validate_otp()` method from `WorkerClass`
- [x] 2.3 Remove `AUTH_REQUIRED` send on data channel open in `WorkerClass`
- [x] 2.4 Remove `AUTH_RESPONSE` handler in `WorkerClass.on_message()`
- [x] 2.5 Remove OTP secret extraction from `registered_auth` in `WorkerClass`
- [x] 2.6 Remove `SLEAP_RTC_OTP_SECRET` environment variable support

## 3. Remove P2P TOTP (OTP) — Client Side

- [x] 3.1 Remove `otp_secret` field and `_get_otp_secret()` from `sleap_rtc/client/client_class.py`
- [x] 3.2 Remove `AUTH_REQUIRED`/`AUTH_SUCCESS`/`AUTH_FAILURE` handlers from `client_class.py`
- [x] 3.3 Remove OTP handling from `sleap_rtc/client/client_track_class.py`
- [x] 3.4 Remove OTP handling from `sleap_rtc/rtc_browse.py` (`_handle_auth_required`, `_handle_auth_success`, `_handle_auth_failure`, `_get_otp_secret`)
- [x] 3.5 Remove `otp_secret` parameter from `sleap_rtc/rtc_client.py`
- [x] 3.6 Remove `otp_secret` parameter from `sleap_rtc/rtc_client_track.py`
- [x] 3.7 Remove `--otp-secret` flag from `client-train`, `client-track`, `browse` in `sleap_rtc/cli.py`

## 4. Remove OTP — Protocol and Auth Utilities

- [x] 4.1 Remove `MSG_AUTH_REQUIRED`, `MSG_AUTH_RESPONSE`, `MSG_AUTH_SUCCESS`, `MSG_AUTH_FAILURE` from `sleap_rtc/protocol.py`
- [x] 4.2 Remove `get_stored_otp_secret()`, `save_otp_secret()`, `remove_otp_secret()` from `sleap_rtc/auth/credentials.py`
- [x] 4.3 Remove `otp_secrets` from default credential file schema in `sleap_rtc/auth/credentials.py`
- [x] 4.4 Evaluate and delete `sleap_rtc/auth/totp.py` if solely OTP-related

## 5. Remove OTP — TUI

- [x] 5.1 Delete `sleap_rtc/tui/screens/otp_input.py`
- [x] 5.2 Remove `otp_secret` parameter from `sleap_rtc/tui/app.py`
- [x] 5.3 Remove OTP handling from `sleap_rtc/tui/bridge.py`
- [x] 5.4 Remove `otp_secret` parameter from `sleap_rtc/tui/screens/browser.py`

## 6. Remove OTP — Signaling Server

- [x] 6.1 Stop generating OTP secrets on room creation in `server.py`
- [x] 6.2 Stop sending OTP secrets in `registered_auth` response to workers in `server.py`
- [x] 6.3 Remove `/verify-otp` endpoint from `server.py`
- [x] 6.4 Remove OTP-related fields from token creation endpoint in `server.py`

## 7. Remove OTP — Dashboard

- [x] 7.1 Remove "Verify OTP" tab from `dashboard/index.html`
- [x] 7.2 Remove OTP QR code generation from `dashboard/app.js`
- [x] 7.3 Remove OTP verification logic from `dashboard/app.js`

## 8. CLI Flag Cleanup

- [x] 8.1 Standardize `--room` vs `--room-id` naming across all commands (pick one, alias the other)
- [x] 8.2 Ensure `resolve-paths` has consistent flags with other client commands

## 9. Verification

- [x] 9.1 Run full test suite (if tests exist for affected paths)
- [x] 9.2 Manual smoke test: `sleap-rtc login` → `browse` → `client-train` without OTP
- [x] 9.3 Manual smoke test: worker startup with API key only (no OTP secret)
- [x] 9.4 Verify dashboard loads without OTP tab
- [x] 9.5 Verify clear error when running client commands without login
