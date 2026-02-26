# cli-config Specification Delta

## ADDED Requirements

### Requirement: Config Show Command

The CLI SHALL provide a `config show` command to display current configuration.

#### Scenario: Show merged configuration
- **WHEN** user runs `sleap-rtc config show`
- **THEN** output shows merged configuration from all sources
- **AND** output indicates which file each setting came from

#### Scenario: Show config as JSON
- **WHEN** user runs `sleap-rtc config show --json`
- **THEN** output is valid JSON
- **AND** JSON includes source file information

#### Scenario: Show config when no config files exist
- **WHEN** user runs `sleap-rtc config show`
- **AND** no sleap-rtc.toml files exist
- **THEN** output shows default configuration values
- **AND** output indicates defaults are being used

### Requirement: Config Path Command

The CLI SHALL provide a `config path` command to display configuration file locations.

#### Scenario: Show config paths
- **WHEN** user runs `sleap-rtc config path`
- **THEN** output shows CWD config path (`./sleap-rtc.toml`)
- **AND** output shows home config path (`~/.sleap-rtc/config.toml`)
- **AND** output indicates which files exist

### Requirement: Config Add Mount Command

The CLI SHALL provide a command to add mount points to configuration.

#### Scenario: Add mount to CWD config
- **WHEN** user runs `sleap-rtc config add-mount /vast/data "VAST"`
- **THEN** mount is added to `./sleap-rtc.toml`
- **AND** config file is created if it doesn't exist
- **AND** output confirms mount was added

#### Scenario: Add mount to global config
- **WHEN** user runs `sleap-rtc config add-mount /vast/data "VAST" --global`
- **THEN** mount is added to `~/.sleap-rtc/config.toml`
- **AND** config file is created if it doesn't exist

#### Scenario: Add mount with duplicate label
- **WHEN** user runs `sleap-rtc config add-mount /new/path "VAST"`
- **AND** mount with label "VAST" already exists
- **THEN** CLI prompts for confirmation to replace
- **AND** upon confirmation, updates mount path

### Requirement: Config Remove Mount Command

The CLI SHALL provide a command to remove mount points from configuration.

#### Scenario: Remove mount by label
- **WHEN** user runs `sleap-rtc config remove-mount "VAST"`
- **THEN** mount with label "VAST" is removed from config
- **AND** output confirms removal

#### Scenario: Remove non-existent mount
- **WHEN** user runs `sleap-rtc config remove-mount "UNKNOWN"`
- **AND** no mount with that label exists
- **THEN** output indicates mount not found
