## MODIFIED Requirements

### Requirement: Room Credential CLI Options

The `train` and `track` commands SHALL accept `-r/--room-id` and `-s/--room-secret` options for room-based connection. Legacy `client-train` and `client-track` aliases remain available with deprecation warnings.

#### Scenario: Train with room credentials
- **WHEN** user runs `sleap-rtc train -r ROOM -s SECRET --pkg-path PATH`
- **THEN** client connects to room using provided credentials
- **AND** client enters worker discovery and selection flow

#### Scenario: Track with room credentials
- **WHEN** user runs `sleap-rtc track -r ROOM -s SECRET --data-path PATH --model-paths M1 M2`
- **THEN** client connects to room using provided credentials
- **AND** client enters worker discovery and selection flow

#### Scenario: Legacy client-train command usage
- **WHEN** user runs `sleap-rtc client-train ...`
- **THEN** command executes with deprecation warning
- **AND** warning suggests using `sleap-rtc train` instead

#### Scenario: Legacy client-track command usage
- **WHEN** user runs `sleap-rtc client-track ...`
- **THEN** command executes with deprecation warning
- **AND** warning suggests using `sleap-rtc track` instead

#### Scenario: Room-id without room-secret
- **WHEN** user provides `-r/--room-id` without `-s/--room-secret`
- **AND** no saved room-secret exists for that room
- **THEN** CLI returns validation error
- **AND** error message indicates room-secret is required

#### Scenario: Room-id with saved room-secret
- **WHEN** user provides `-r/--room-id` without `-s/--room-secret`
- **AND** saved room-secret exists for that room in credentials
- **THEN** CLI uses saved room-secret for connection

### Requirement: Browse Command JWT Authentication Option

The `sleap-rtc test browse` command SHALL require authentication with stored JWT credentials. The browse functionality is moved to the test subcommand for experimental features.

#### Scenario: Test browse with stored credentials
- **WHEN** user runs `sleap-rtc test browse -r ROOM`
- **AND** credentials file exists with valid JWT
- **THEN** browse uses JWT for signaling server authentication
- **AND** browse sends JWT in WebSocket register message

#### Scenario: Test browse without credentials
- **WHEN** user runs `sleap-rtc test browse` command
- **AND** no credentials file exists or JWT is expired
- **THEN** command returns error indicating login required
- **AND** error message suggests running `sleap-rtc login`

#### Scenario: Legacy browse flag usage
- **WHEN** user runs `sleap-rtc train --browse ...`
- **THEN** command shows deprecation warning
- **AND** warning suggests using `sleap-rtc test browse` instead

## ADDED Requirements

### Requirement: TUI Command

The CLI SHALL provide a `sleap-rtc tui` command to launch the full-screen Textual TUI for file browsing and SLP resolution workflows.

#### Scenario: Launch TUI with room credentials
- **WHEN** user runs `sleap-rtc tui -r ROOM`
- **AND** credentials file exists with valid JWT
- **THEN** Textual TUI app launches
- **AND** TUI connects to specified room

#### Scenario: Launch TUI without credentials
- **WHEN** user runs `sleap-rtc tui`
- **AND** no credentials file exists or JWT is expired
- **THEN** TUI shows login screen
- **AND** user can authenticate via GitHub OAuth flow

#### Scenario: TUI file browser navigation
- **WHEN** TUI is connected to room with available workers
- **THEN** user can browse worker filesystems
- **AND** user can select files for SLP resolution
- **AND** user can navigate with keyboard shortcuts

### Requirement: TUI Room-Secret Resolution

The TUI SHALL resolve room-secrets from credentials and prompt for input when required for worker authentication.

#### Scenario: TUI loads saved room-secret
- **WHEN** user selects a room in the TUI
- **AND** room-secret exists in credentials for that room
- **THEN** TUI uses saved room-secret for worker authentication
- **AND** TUI does not prompt user for secret

#### Scenario: TUI prompts for room-secret when missing
- **WHEN** user selects a room in the TUI
- **AND** no room-secret exists for that room
- **AND** worker requires PSK authentication
- **THEN** TUI displays input prompt for room-secret
- **AND** user can enter the secret interactively

#### Scenario: TUI saves room-secret after successful auth
- **WHEN** user enters room-secret in TUI prompt
- **AND** PSK authentication succeeds with worker
- **THEN** TUI saves room-secret to credentials for future use
- **AND** subsequent connections to same room use saved secret

#### Scenario: TUI handles auth failure gracefully
- **WHEN** user enters incorrect room-secret
- **AND** PSK authentication fails
- **THEN** TUI displays error message explaining auth failure
- **AND** TUI offers option to retry with different secret
- **AND** TUI does not save failed secret to credentials

### Requirement: Status Command

The CLI SHALL provide a `sleap-rtc status` command to display current authentication and connection status.

#### Scenario: Status with valid credentials
- **WHEN** user runs `sleap-rtc status`
- **AND** credentials file exists with valid JWT
- **THEN** command displays user identity (GitHub username)
- **AND** command displays JWT expiration time
- **AND** command displays any saved room-secrets
- **AND** command displays credential file location

#### Scenario: Status without credentials
- **WHEN** user runs `sleap-rtc status`
- **AND** no credentials file exists
- **THEN** command indicates not logged in
- **AND** command suggests running `sleap-rtc login`

#### Scenario: Status with expired JWT
- **WHEN** user runs `sleap-rtc status`
- **AND** credentials file exists but JWT is expired
- **THEN** command indicates JWT expired
- **AND** command shows expiration timestamp
- **AND** command suggests running `sleap-rtc login`

### Requirement: Doctor Command

The CLI SHALL provide a `sleap-rtc doctor` command to diagnose environment and connectivity issues.

#### Scenario: Doctor checks environment
- **WHEN** user runs `sleap-rtc doctor`
- **THEN** command checks Python version compatibility
- **AND** command checks required dependencies installed
- **AND** command checks network connectivity to signaling server
- **AND** command checks credential file existence and permissions

#### Scenario: Doctor reports issues
- **WHEN** user runs `sleap-rtc doctor`
- **AND** issues are detected
- **THEN** command displays issues with severity level
- **AND** command suggests remediation steps
- **AND** command exits with non-zero status code

#### Scenario: Doctor passes all checks
- **WHEN** user runs `sleap-rtc doctor`
- **AND** all checks pass
- **THEN** command displays success message
- **AND** command exits with zero status code

### Requirement: Test Subcommand Group

The CLI SHALL provide a `sleap-rtc test` subcommand group for experimental and debugging features.

#### Scenario: Test subcommand help
- **WHEN** user runs `sleap-rtc test --help`
- **THEN** command displays available test subcommands
- **AND** help text explains these are experimental features

#### Scenario: Test resolve-paths command
- **WHEN** user runs `sleap-rtc test resolve-paths -r ROOM`
- **THEN** command enters SLP resolution mode
- **AND** command shows resolution workflow for debugging

### Requirement: Room-Secret Credential Persistence

The CLI SHALL persist room-secrets in the credentials file for convenient reuse.

#### Scenario: Save room-secret on first connection
- **WHEN** user provides `-s/--room-secret` with `-r/--room-id`
- **AND** connection succeeds
- **THEN** CLI saves room-secret to credentials keyed by room-id
- **AND** future connections can omit `-s/--room-secret`

#### Scenario: Load saved room-secret
- **WHEN** user provides `-r/--room-id` without `-s/--room-secret`
- **AND** saved room-secret exists for that room
- **THEN** CLI loads and uses saved room-secret

#### Scenario: Override saved room-secret
- **WHEN** user provides `-r/--room-id` with `-s/--room-secret`
- **AND** saved room-secret exists for that room
- **THEN** CLI uses provided room-secret (not saved)
- **AND** CLI updates saved room-secret with new value

### Requirement: Standard Flag Conventions

The CLI SHALL use consistent flag naming and short forms across all commands.

#### Scenario: Short flag -r for room-id
- **WHEN** user provides `-r ROOM` to any command accepting room-id
- **THEN** command treats it as equivalent to `--room-id ROOM`

#### Scenario: Short flag -s for room-secret
- **WHEN** user provides `-s SECRET` to any command accepting room-secret
- **THEN** command treats it as equivalent to `--room-secret SECRET`

#### Scenario: Short flag -w for worker-id
- **WHEN** user provides `-w WORKER` to any command accepting worker-id
- **THEN** command treats it as equivalent to `--worker-id WORKER`

#### Scenario: Short flag -f for force
- **WHEN** user provides `-f` to any command accepting force
- **THEN** command treats it as equivalent to `--force`
- **AND** command skips confirmation prompts

#### Scenario: Legacy --token flag usage
- **WHEN** user provides `--token` to any command
- **THEN** command shows deprecation warning
- **AND** warning suggests using `--room-secret` instead
- **AND** command continues with provided value

## REMOVED Requirements

### Requirement: Room Token Authentication
**Reason**: JWT provides equivalent room access control. Room token is redundant.
**Migration**: Use `--room-secret` for P2P authentication. Room access controlled via JWT.
