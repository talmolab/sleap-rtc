# cli-verbosity Specification Delta

## ADDED Requirements

### Requirement: Verbosity Flags for Train Command

The `train` command SHALL accept `--verbose/-v` and `--quiet/-q` flags to control output verbosity.

#### Scenario: Default verbosity shows setup and progress
- **WHEN** user runs `sleap-rtc train --room ROOM --config PATH`
- **AND** no verbosity flag is provided
- **THEN** output shows connection status
- **AND** output shows sleap-nn setup logs (model summary, params, sanity check)
- **AND** output shows training progress with in-place updates
- **AND** output shows errors and warnings
- **AND** output hides keep-alive messages
- **AND** output hides ICE connection state changes
- **AND** output hides detailed file transfer logs

#### Scenario: Verbose mode shows all logs
- **WHEN** user runs `sleap-rtc train --room ROOM --config PATH --verbose`
- **THEN** output shows all default logs plus:
  - Keep-alive messages
  - ICE connection state changes
  - File transfer details
- **AND** output includes DEBUG level messages

#### Scenario: Quiet mode shows minimal output
- **WHEN** user runs `sleap-rtc train --room ROOM --config PATH --quiet`
- **THEN** output shows only errors and final status
- **AND** output hides training progress bars
- **AND** output hides connection status messages

#### Scenario: Verbose and quiet are mutually exclusive
- **WHEN** user runs `sleap-rtc train --verbose --quiet`
- **THEN** CLI returns validation error
- **AND** error message indicates flags are mutually exclusive

### Requirement: Verbosity Flags for Track Command

The `track` command SHALL accept the same `--verbose/-v` and `--quiet/-q` flags.

#### Scenario: Track command respects verbosity flags
- **WHEN** user runs `sleap-rtc track --room ROOM --data-path PATH --model-paths M1 --quiet`
- **THEN** output follows same verbosity rules as train command

### Requirement: Verbosity Flag for Worker Command

The `worker` command SHALL accept `--verbose/-v` flag to control worker-side logging.

#### Scenario: Worker verbose mode
- **WHEN** user runs `sleap-rtc worker --api-key KEY --verbose`
- **THEN** worker logs show detailed connection and job execution info
- **AND** worker logs include DEBUG level messages

## REMOVED Requirements

### Requirement: Deprecated DynamoDB Log Messages

Log messages referencing DynamoDB and Cognito cleanup SHALL be removed.

#### Scenario: No DynamoDB messages on disconnect
- **WHEN** client disconnects from worker
- **THEN** no log message mentioning "DynamoDB" is displayed
- **AND** no log message mentioning "Cognito" is displayed

### Requirement: Legacy Room Token CLI Options

The `--token` CLI option for room-based authentication SHALL be removed in favor of worker API keys.

#### Scenario: Token flag removed from train command
- **WHEN** user runs `sleap-rtc train --help`
- **THEN** help output does NOT show `--token` option
- **AND** room-based connection uses only `--room` flag with JWT authentication

#### Scenario: Token flag removed from track command
- **WHEN** user runs `sleap-rtc track --help`
- **THEN** help output does NOT show `--token` option

#### Scenario: Token flag removed from worker command
- **WHEN** user runs `sleap-rtc worker --help`
- **THEN** help output does NOT show `--token` option
- **AND** worker authentication uses only `--api-key` flag

#### Scenario: Worker output no longer shows room token
- **WHEN** worker starts and joins a room
- **THEN** worker output does NOT display "Room Token:" line
- **AND** worker output shows only room ID and worker peer ID
