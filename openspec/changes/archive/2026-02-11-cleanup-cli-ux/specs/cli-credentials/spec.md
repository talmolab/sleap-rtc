# cli-credentials Specification Delta

## ADDED Requirements

### Requirement: Credentials List Command

The CLI SHALL provide a `credentials list` command to display stored credentials.

#### Scenario: List credentials when logged in
- **WHEN** user runs `sleap-rtc credentials list`
- **AND** user is logged in with stored JWT
- **THEN** output shows logged-in username
- **AND** output shows rooms with saved secrets (secrets redacted)
- **AND** output shows rooms with saved API tokens (tokens redacted)

#### Scenario: List credentials when not logged in
- **WHEN** user runs `sleap-rtc credentials list`
- **AND** no JWT is stored
- **THEN** output shows "Not logged in"
- **AND** output still shows any saved room secrets and tokens

#### Scenario: List credentials with no stored data
- **WHEN** user runs `sleap-rtc credentials list`
- **AND** credentials file does not exist
- **THEN** output shows "No credentials stored"

### Requirement: Credentials Show Command

The CLI SHALL provide a `credentials show` command to display full credential details.

#### Scenario: Show credentials with redaction
- **WHEN** user runs `sleap-rtc credentials show`
- **THEN** output shows credentials file path
- **AND** output shows full structure with secrets redacted (e.g., `slp_****xxxx`)

#### Scenario: Show credentials with reveal flag
- **WHEN** user runs `sleap-rtc credentials show --reveal`
- **THEN** output shows full secrets without redaction
- **AND** output includes warning about exposing sensitive data

### Requirement: Credentials Clear Command

The CLI SHALL provide a `credentials clear` command to remove all stored credentials.

#### Scenario: Clear credentials with confirmation
- **WHEN** user runs `sleap-rtc credentials clear`
- **THEN** CLI prompts for confirmation
- **AND** upon confirmation, deletes credentials file
- **AND** outputs success message

#### Scenario: Clear credentials with yes flag
- **WHEN** user runs `sleap-rtc credentials clear --yes`
- **THEN** CLI skips confirmation prompt
- **AND** deletes credentials file immediately

### Requirement: Credentials Remove Secret Command

The CLI SHALL provide a command to remove a specific room secret.

#### Scenario: Remove room secret
- **WHEN** user runs `sleap-rtc credentials remove-secret --room abc123`
- **AND** room secret exists for abc123
- **THEN** secret is removed from credentials file
- **AND** other credentials remain unchanged
- **AND** output confirms removal

#### Scenario: Remove non-existent room secret
- **WHEN** user runs `sleap-rtc credentials remove-secret --room xyz`
- **AND** no secret exists for room xyz
- **THEN** output indicates no secret found for room

### Requirement: Credentials Remove Token Command

The CLI SHALL provide a command to remove a specific room API token.

#### Scenario: Remove room token
- **WHEN** user runs `sleap-rtc credentials remove-token --room abc123`
- **AND** API token exists for abc123
- **THEN** token is removed from credentials file
- **AND** other credentials remain unchanged
- **AND** output confirms removal
