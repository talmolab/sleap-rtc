## REMOVED Requirements

### Requirement: Browse Command TOTP Authentication
**Reason**: P2P TOTP is being removed entirely. Workers no longer challenge clients with OTP codes. JWT + room membership gates access at the signaling server.
**Migration**: Browse command connects directly after signaling server authentication. No OTP prompt or auto-resolve needed.

## MODIFIED Requirements

### Requirement: Browse Command JWT Authentication Option

The `browse` command SHALL require authentication with stored JWT credentials.

#### Scenario: Browse with stored credentials
- **WHEN** user runs `sleap-rtc browse --room-id ROOM --token TOKEN`
- **AND** credentials file exists with valid JWT
- **THEN** browse uses JWT for signaling server authentication
- **AND** browse sends JWT in WebSocket register message

#### Scenario: Browse without credentials
- **WHEN** user runs browse command
- **AND** no credentials file exists or JWT is expired
- **THEN** browse returns error indicating login required
- **AND** error message suggests running `sleap-rtc login`
