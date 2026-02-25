# Model Registry Specification (Modifications)

## MODIFIED Requirements

### Requirement: Model Metadata Storage
The registry SHALL store comprehensive metadata for each model to enable identification and tracking, including optional human-readable aliases.

#### Scenario: Registry entry created with alias support
- **WHEN** a model is registered
- **THEN** the registry entry SHALL include:
  - Model ID (8-char hash)
  - Full hash (64-char SHA256)
  - Run name
  - Model type (centroid, centered_instance, etc.)
  - Alias (optional human-readable name, string or null)
  - Training job hash (hash of uploaded package)
  - Creation timestamp (ISO 8601 format)
  - Completion timestamp (ISO 8601 format, null if incomplete)
  - Status (training, completed, interrupted, failed)
  - Checkpoint path (relative to models directory)
  - Config path (path to training_config.yaml)
  - Metrics (validation loss, epochs, etc.)
  - Metadata (dataset name, GPU model, training duration)
  - Training hyperparameters (learning rate, batch size, optimizer, etc.) (optional)
  - sleap_nn_version (version string) (optional)
  - tags (array of strings) (optional)
  - notes (user-provided text) (optional)

#### Scenario: Registry persisted to disk with aliases
- **WHEN** registry is modified and includes models with aliases
- **THEN** the system SHALL write both models and aliases sections to manifest
- **AND** the aliases section SHALL be a flat mapping of alias → model_id
- **AND** the models section SHALL include alias field in each model entry
- **AND** the system SHALL maintain consistency between both sections

## ADDED Requirements

### Requirement: Alias Management on Worker
The worker registry SHALL support human-readable aliases for model identification.

#### Scenario: Set alias for worker model
- **WHEN** an alias is assigned to a model on the worker
- **THEN** the worker SHALL store the alias in the model entry
- **AND** the worker SHALL create mapping in aliases dictionary
- **AND** the worker SHALL validate alias uniqueness within worker registry
- **AND** if alias exists, the worker SHALL reject with collision error

#### Scenario: Resolve alias on worker
- **WHEN** a query or operation uses an alias instead of model ID
- **THEN** the worker SHALL first attempt to match as model ID
- **AND** if no ID match, the worker SHALL look up alias in aliases dictionary
- **AND** if alias found, the worker SHALL resolve to corresponding model ID
- **AND** if neither found, the worker SHALL return not found error

#### Scenario: Model registered with client-provided alias
- **WHEN** client pushes a model with an alias to worker
- **THEN** the worker SHALL attempt to use the provided alias
- **AND** if alias collision on worker, the worker SHALL append numeric suffix (-2, -3)
- **AND** the worker SHALL inform client of final assigned alias
- **AND** the worker SHALL register model with resolved alias

#### Scenario: Remove alias from worker model
- **WHEN** an alias is removed from a worker model
- **THEN** the worker SHALL delete the alias mapping from aliases dictionary
- **AND** the worker SHALL clear the alias field in model entry
- **AND** the model SHALL remain accessible by ID

### Requirement: Enhanced Metadata Storage
The worker registry SHALL store additional metadata for better model tracking and comparison.

#### Scenario: Training hyperparameters captured
- **WHEN** a training job completes
- **THEN** the system SHALL extract hyperparameters from training_config.yaml
- **AND** the system SHALL store: learning_rate, batch_size, optimizer, max_epochs
- **AND** the system SHALL store: augmentation settings, backbone architecture
- **AND** these SHALL be stored in training_hyperparameters object in registry
- **AND** if config unavailable, field SHALL be null

#### Scenario: Version information captured
- **WHEN** a model is registered (from training or upload)
- **THEN** the system SHALL capture sleap-nn version if available
- **AND** the system SHALL capture git commit hash if in development environment
- **AND** these SHALL be stored as optional fields
- **AND** version info SHALL be displayed in model info queries

#### Scenario: User-provided metadata
- **WHEN** a model is uploaded or registered with custom metadata
- **THEN** the system SHALL accept optional tags as array of strings
- **AND** the system SHALL accept optional notes as free-form text
- **AND** the system SHALL validate tags are alphanumeric with dashes/underscores
- **AND** the system SHALL limit notes to 1000 characters
- **AND** these fields SHALL be searchable in list queries

### Requirement: Registry Query with Alias Support
The worker SHALL support querying models by either ID or alias interchangeably.

#### Scenario: Query model by alias
- **WHEN** worker receives query for model with alias identifier
- **THEN** the worker SHALL resolve alias to model ID
- **AND** the worker SHALL return complete model entry
- **AND** the response SHALL include both ID and alias
- **AND** if alias not found, the worker SHALL return not found error

#### Scenario: List models shows aliases
- **WHEN** worker receives list models query
- **THEN** the response SHALL include alias field for each model
- **AND** models without aliases SHALL have alias: null
- **AND** the list SHALL be sortable by alias alphabetically
- **AND** filters SHALL support matching against alias with wildcards

### Requirement: Registry Schema Extension
The worker registry schema SHALL be extended to support aliases and enhanced metadata while maintaining backward compatibility.

#### Scenario: Registry schema with aliases
- **WHEN** loading or creating a registry
- **THEN** the schema SHALL include:
  - version: "1.0" (string)
  - models: object mapping model_id to model entry
  - aliases: object mapping alias to model_id (NEW)
- **AND** if loading old registry without aliases, the system SHALL add empty aliases object
- **AND** the system SHALL migrate seamlessly without data loss

#### Scenario: Model entry schema extended
- **WHEN** reading or writing model entries
- **THEN** each entry MAY include (all optional except existing required fields):
  - alias: string or null (NEW)
  - training_hyperparameters: object or null (NEW)
  - sleap_nn_version: string or null (NEW)
  - git_commit: string or null (NEW)
  - tags: array of strings or null (NEW)
  - notes: string or null (NEW)
- **AND** old registries without these fields SHALL function normally
- **AND** missing optional fields SHALL default to null

## REMOVED Requirements

None. This change is fully additive and maintains backward compatibility.
