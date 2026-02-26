# signaling-configuration Specification

## Purpose
TBD - created by archiving change add-signaling-server-config. Update Purpose after archive.
## Requirements
### Requirement: Configuration Loading

The system SHALL support loading signaling server configuration from multiple sources with the following priority order: CLI arguments (highest), environment variables, configuration file, defaults (lowest).

#### Scenario: CLI argument overrides all
- **WHEN** user provides `--server ws://custom-server.com` via CLI
- **THEN** the system uses that server regardless of environment variables or config file

#### Scenario: Environment variable fallback
- **WHEN** no CLI argument is provided AND environment variable SLEAP_RTC_SIGNALING_WS is set
- **THEN** the system uses the environment variable value

#### Scenario: Config file fallback
- **WHEN** no CLI argument or environment variable is set AND config file exists
- **THEN** the system reads signaling server URLs from the config file

#### Scenario: Default fallback
- **WHEN** no configuration is provided from any source
- **THEN** the system uses the default production signaling server

### Requirement: Configuration File Format

The system SHALL support TOML configuration files with environment-specific sections located at `~/.sleap-rtc/config.toml` or in the current working directory as `sleap-rtc.toml`. The file MUST use `[environments.<env-name>]` sections where `<env-name>` is one of: `development`, `staging`, `production`.

#### Scenario: Valid environment-based config structure
- **WHEN** a config file contains `[environments.production]` section with `signaling_websocket` and `signaling_http` keys
- **THEN** the system successfully loads these values for the production environment

#### Scenario: Multiple environment sections
- **WHEN** config file contains `[environments.development]`, `[environments.staging]`, and `[environments.production]` sections
- **THEN** the system loads the appropriate section based on SLEAP_RTC_ENV

#### Scenario: Default section support
- **WHEN** config file contains a `[default]` section with shared settings
- **THEN** those settings apply to all environments unless overridden

#### Scenario: Missing config file
- **WHEN** no config file is found at expected locations
- **THEN** the system continues with environment variables or defaults without error

#### Scenario: Missing environment section
- **WHEN** config file exists but lacks the requested environment section
- **THEN** the system falls back to defaults for that environment

### Requirement: Environment Selection

The system SHALL support environment selection via the `SLEAP_RTC_ENV` environment variable with valid values: `development`, `staging`, `production`. If not set, the system SHALL default to `production`.

#### Scenario: Development environment selection
- **WHEN** SLEAP_RTC_ENV is set to `development`
- **THEN** the system loads configuration from `[environments.development]` section

#### Scenario: Production default
- **WHEN** SLEAP_RTC_ENV is not set
- **THEN** the system uses `production` environment configuration

#### Scenario: Invalid environment name
- **WHEN** SLEAP_RTC_ENV is set to an unrecognized value
- **THEN** the system logs a warning and defaults to `production`

### Requirement: Environment Variables Override

The system SHALL support the following environment variables for overriding signaling server configuration:
- `SLEAP_RTC_SIGNALING_WS`: WebSocket URL (e.g., `ws://server.com:8080`)
- `SLEAP_RTC_SIGNALING_HTTP`: HTTP API base URL (e.g., `http://server.com:8001`)

These variables SHALL take precedence over config file settings but be overridden by CLI arguments.

#### Scenario: Environment variables override config file
- **WHEN** SLEAP_RTC_SIGNALING_WS is set to `ws://dev-server.com:8080` AND config file has different value
- **THEN** all WebSocket connections use the environment variable value

#### Scenario: Partial environment configuration
- **WHEN** only SLEAP_RTC_SIGNALING_WS is set
- **THEN** HTTP URL falls back to config file or default

### Requirement: URL Construction

The system SHALL construct HTTP API endpoint URLs by combining the base HTTP URL with the appropriate path (`/create-room`, `/delete-peers-and-room`, `/anonymous-signin`).

#### Scenario: HTTP endpoint construction
- **WHEN** HTTP base URL is `http://custom-server.com:8001`
- **THEN** create-room endpoint becomes `http://custom-server.com:8001/create-room`

### Requirement: Backward Compatibility

The system SHALL maintain backward compatibility by defaulting to the current production signaling server when no custom configuration is provided.

#### Scenario: No configuration provided
- **WHEN** user runs sleap-rtc without any configuration
- **THEN** the system connects to the default production signaling server at `ws://ec2-54-176-92-10.us-west-1.compute.amazonaws.com:8080`

