# Model Aliases Specification

## ADDED Requirements

### Requirement: Alias Assignment
The system SHALL allow users to assign human-readable aliases to models for easier reference.

#### Scenario: Set alias for model
- **WHEN** user assigns an alias to a model
- **THEN** the system SHALL store the alias in the registry
- **AND** the system SHALL create a mapping in the aliases dictionary
- **AND** the system SHALL validate alias contains only alphanumeric, dash, and underscore characters
- **AND** the system SHALL return success confirmation

#### Scenario: Alias collision detected
- **WHEN** user assigns an alias that already exists
- **THEN** the system SHALL detect the collision
- **AND** the system SHALL display which model currently uses that alias
- **AND** the system SHALL prompt user: "Overwrite existing alias? [y/N]"
- **AND** if user confirms, the system SHALL reassign the alias to the new model
- **AND** if user declines, the system SHALL abort without changes

#### Scenario: Set alias with force flag
- **WHEN** user assigns an alias with --force flag
- **THEN** the system SHALL overwrite any existing alias without prompting
- **AND** the system SHALL log the previous alias assignment for audit

#### Scenario: Invalid alias format
- **WHEN** user provides an alias with invalid characters
- **THEN** the system SHALL reject the alias
- **AND** the system SHALL display error: "Alias must contain only letters, numbers, dashes, and underscores"
- **AND** the system SHALL suggest a sanitized version if possible

### Requirement: Alias Resolution
The system SHALL resolve aliases to model IDs transparently in all commands that accept model identifiers.

#### Scenario: Resolve alias to model ID
- **WHEN** a command receives an identifier
- **THEN** the system SHALL first check if it matches a model ID (8-char hex)
- **AND** if not, the system SHALL check if it matches an alias
- **AND** if alias found, the system SHALL resolve to the corresponding model ID
- **AND** if neither found, the system SHALL return None

#### Scenario: Ambiguous identifier
- **WHEN** an identifier could be both a model ID and an alias
- **THEN** the system SHALL prefer exact model ID match
- **AND** the system SHALL check aliases only if no ID match found

#### Scenario: Resolve on worker
- **WHEN** resolving an alias for a worker operation
- **THEN** the system SHALL query the worker registry for alias resolution
- **AND** the system SHALL use the worker's alias mapping
- **AND** if not found on worker, the system SHALL fall back to client registry

### Requirement: Alias Management
The system SHALL provide operations to manage aliases independently of models.

#### Scenario: Remove alias
- **WHEN** user removes an alias from a model
- **THEN** the system SHALL delete the alias mapping
- **AND** the system SHALL clear the alias field in the model entry
- **AND** the system SHALL preserve the model entry itself
- **AND** the model SHALL remain accessible by ID

#### Scenario: List all aliases
- **WHEN** user requests all aliases
- **THEN** the system SHALL return all alias-to-ID mappings
- **AND** the system SHALL sort alphabetically by alias name
- **AND** the system SHALL include model type for context

#### Scenario: Rename alias
- **WHEN** user assigns a new alias to a model that already has one
- **THEN** the system SHALL remove the old alias mapping
- **AND** the system SHALL create the new alias mapping
- **AND** the system SHALL update the model entry with the new alias

### Requirement: Alias Display
The system SHALL display aliases prominently in model listings and information displays.

#### Scenario: List models with aliases
- **WHEN** displaying a list of models
- **THEN** the system SHALL show alias in the ID/Alias column
- **AND** if alias exists, the system SHALL display: "{model_id}\n{alias}"
- **AND** if no alias, the system SHALL display only model_id
- **AND** the system SHALL truncate long aliases with ellipsis (max 15 chars in table)

#### Scenario: Model info with alias
- **WHEN** displaying detailed model information
- **THEN** the system SHALL show both ID and alias clearly
- **AND** the format SHALL be: "Model: {alias} ({model_id})"
- **AND** if no alias, the format SHALL be: "Model: {model_id}"

#### Scenario: Track command with alias
- **WHEN** user runs track command with an alias
- **THEN** the system SHALL display: "Resolved model: {alias} ({model_id})"
- **AND** the system SHALL show the checkpoint path being used
- **AND** the system SHALL proceed with inference using the resolved path

### Requirement: Alias Synchronization
The system SHALL handle aliases when syncing between client and worker registries.

#### Scenario: Push model with alias
- **WHEN** pushing a model that has an alias on the client
- **THEN** the system SHALL include the alias in the transfer metadata
- **AND** the worker SHALL register the model with the same alias
- **AND** if alias collision on worker, the system SHALL prompt user for worker alias

#### Scenario: Pull model with alias
- **WHEN** pulling a model that has an alias on the worker
- **THEN** the system SHALL transfer the alias to the client registry
- **AND** if alias collision on client, the system SHALL prompt user for client alias
- **AND** the system SHALL offer to keep, rename, or skip the worker alias

#### Scenario: Sync maintains separate aliases
- **WHEN** syncing registries
- **THEN** the system SHALL NOT automatically sync aliases
- **AND** client and worker MAY have different aliases for the same model ID
- **AND** the system SHALL respect each registry's alias namespace
- **AND** sync command SHALL display any alias differences for user awareness

### Requirement: Alias Validation
The system SHALL validate aliases to ensure they are unique, valid, and maintainable.

#### Scenario: Alias length limits
- **WHEN** user provides an alias
- **THEN** the system SHALL enforce minimum length of 1 character
- **AND** the system SHALL enforce maximum length of 64 characters
- **AND** the system SHALL reject empty strings
- **AND** the system SHALL reject whitespace-only strings

#### Scenario: Alias character restrictions
- **WHEN** validating an alias
- **THEN** the system SHALL allow: a-z, A-Z, 0-9, dash (-), underscore (_)
- **AND** the system SHALL reject spaces
- **AND** the system SHALL reject special characters (!, @, #, $, %, etc.)
- **AND** the system SHALL reject leading/trailing dashes or underscores
- **AND** the system SHALL be case-sensitive (Good-Model != good-model)

#### Scenario: Reserved alias names
- **WHEN** user provides an alias
- **THEN** the system SHALL reject reserved names: "all", "latest", "none", "null"
- **AND** the system SHALL reject aliases that look like model IDs (8-char hex)
- **AND** the system SHALL provide clear error message with reason

### Requirement: Alias Auto-Suggestion
The system SHALL offer helpful alias suggestions when appropriate.

#### Scenario: Training completion prompts for alias
- **WHEN** a training job completes successfully
- **THEN** the system SHALL prompt: "Give it a friendly name? [y/N]"
- **AND** if user accepts, the system SHALL prompt for alias input
- **AND** the system SHALL suggest default based on model type and dataset
- **AND** suggested format SHALL be: "{model_type}-{dataset_name}-v1"

#### Scenario: Import prompts for alias
- **WHEN** importing a model without --alias flag
- **THEN** the system SHALL prompt: "Enter alias (optional, press enter to skip):"
- **AND** the system SHALL suggest alias based on directory name if meaningful
- **AND** the system SHALL sanitize suggestion to valid characters

#### Scenario: Collision resolution suggestions
- **WHEN** alias collision occurs
- **THEN** the system SHALL suggest alternative aliases:
  - Append version number: "{original}-v2"
  - Append date: "{original}-2025-11"
  - Append short hash: "{original}-a3f5"
- **AND** the system SHALL check each suggestion for availability
- **AND** the system SHALL present up to 3 suggestions
