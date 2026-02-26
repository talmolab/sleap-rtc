# Client Model Registry Specification

## ADDED Requirements

### Requirement: Client Registry Initialization
The client SHALL maintain a local registry of models in the user's home directory for tracking downloaded and imported models.

#### Scenario: First use initializes registry
- **WHEN** a user runs any model management command for the first time
- **THEN** the system SHALL create `~/.sleap-rtc/models/` directory
- **AND** the system SHALL create `manifest.json` with version "1.0" and empty models dictionary
- **AND** the system SHALL set appropriate file permissions (user read/write only)

#### Scenario: Registry already exists
- **WHEN** the client registry file exists
- **THEN** the system SHALL load the existing registry
- **AND** the system SHALL validate the schema version is compatible
- **AND** if schema version is older, the system SHALL migrate to current version

#### Scenario: Registry is corrupted
- **WHEN** the registry file exists but contains invalid JSON
- **THEN** the system SHALL log an error with corruption details
- **AND** the system SHALL create a timestamped backup of the corrupted file
- **AND** the system SHALL initialize a fresh registry

### Requirement: Model Registration on Client
The client SHALL register models in the local registry when downloaded, imported, or trained.

#### Scenario: Model downloaded from worker
- **WHEN** a model is successfully downloaded from a worker
- **THEN** the client SHALL create a registry entry with:
  - Model ID (from worker registry)
  - Model type
  - Alias (if provided)
  - Source: "worker-pull" or "worker-training"
  - Downloaded timestamp
  - Local path to checkpoint files
  - Worker availability status: on_worker=true
  - Metrics (validation loss, epochs, etc.)
- **AND** the system SHALL save files to `~/.sleap-rtc/models/{model_type}_{model_id}/`

#### Scenario: Model imported from local filesystem
- **WHEN** a user imports a model from a local directory
- **THEN** the client SHALL create a registry entry with:
  - Model ID (generated or extracted from config)
  - Model type (detected or user-provided)
  - Alias (if provided)
  - Source: "local-import"
  - Imported timestamp
  - Local path (symlink to original or copied files)
  - Worker availability status: on_worker=false
- **AND** the system SHALL create a symlink by default (unless --copy flag used)

#### Scenario: Model registered after training
- **WHEN** training completes on a worker and user chooses to download
- **THEN** the client SHALL automatically register the model
- **AND** the system SHALL prompt user for an optional alias
- **AND** the system SHALL set source: "worker-training"
- **AND** the system SHALL mark on_worker=true

### Requirement: Client Registry Storage
The client registry SHALL persist model metadata in JSON format with atomic writes.

#### Scenario: Registry updated
- **WHEN** any model is added, updated, or removed from the registry
- **THEN** the system SHALL write changes using atomic file operations
- **AND** the system SHALL write to a temporary file first
- **AND** the system SHALL rename the temporary file to the final path
- **AND** the system SHALL maintain 2-space indentation for readability

#### Scenario: Concurrent registry access
- **WHEN** multiple CLI commands access the registry simultaneously
- **THEN** the system SHALL load the latest state from disk each time
- **AND** the system SHALL handle file locking appropriately per OS
- **AND** if write fails due to lock, the system SHALL retry up to 3 times with 100ms delay

### Requirement: Model Retrieval from Client Registry
The client SHALL provide methods to query and retrieve model information from the local registry.

#### Scenario: Get model by ID
- **WHEN** requesting a model by its ID
- **THEN** the system SHALL return the complete registry entry
- **AND** if the model does not exist, the system SHALL return None

#### Scenario: Get model by alias
- **WHEN** requesting a model by alias
- **THEN** the system SHALL resolve the alias to a model ID
- **AND** the system SHALL return the complete registry entry
- **AND** if the alias does not exist, the system SHALL return None

#### Scenario: List local models
- **WHEN** requesting a list of all local models
- **THEN** the system SHALL return all models sorted by download timestamp (newest first)

#### Scenario: Filter models by location
- **WHEN** requesting models with location filter
- **THEN** the system SHALL return only models matching the filter:
  - "local-only": on_worker=false
  - "worker-only": local=false (not yet implemented)
  - "both": on_worker=true AND local=true

#### Scenario: Filter models by source
- **WHEN** requesting models with source filter
- **THEN** the system SHALL return only models matching the specified source
- **AND** valid sources are: "worker-training", "worker-pull", "local-import", "client-upload"

### Requirement: Worker Availability Tracking
The client registry SHALL track which models are available on workers to enable informed transfer decisions.

#### Scenario: Model available on worker
- **WHEN** a model exists on a connected worker
- **THEN** the client registry SHALL mark on_worker=true
- **AND** the system SHALL store worker_last_seen timestamp
- **AND** the system SHALL store worker_path for reference

#### Scenario: Model pushed to worker
- **WHEN** a local model is successfully pushed to a worker
- **THEN** the client SHALL update the registry entry
- **AND** the system SHALL set on_worker=true
- **AND** the system SHALL update worker_last_seen to current timestamp
- **AND** the system SHALL store the worker path

#### Scenario: Sync detects model removed from worker
- **WHEN** sync command queries worker and model no longer exists
- **THEN** the client SHALL update on_worker=false
- **AND** the system SHALL clear worker_path
- **AND** the system SHALL preserve worker_last_seen for historical record

### Requirement: Local File Management
The client SHALL manage local model files with validation and cleanup capabilities.

#### Scenario: Validate checkpoint files exist
- **WHEN** accessing a model from the registry
- **THEN** the system SHALL check if checkpoint_path exists on disk
- **AND** if missing, the system SHALL log a warning
- **AND** the system SHALL mark the model status as "checkpoint_missing" in registry

#### Scenario: Symlink import with broken link
- **WHEN** a model was imported via symlink and source moved
- **THEN** the system SHALL detect broken symlink on access
- **AND** the system SHALL log an error with original source path
- **AND** the system SHALL mark status as "broken_symlink"
- **AND** the system SHALL offer repair via `repair-model` command

#### Scenario: Delete model from client
- **WHEN** user deletes a model via CLI command
- **THEN** the system SHALL remove the registry entry
- **AND** the system SHALL optionally delete local checkpoint files
- **AND** the system SHALL prompt user for confirmation before deleting files
- **AND** the system SHALL preserve on_worker status for recovery if needed

### Requirement: Client Registry Schema
The client registry SHALL use a defined JSON schema for consistency and validation.

#### Scenario: Registry schema v1.0
- **WHEN** creating or loading a v1.0 registry
- **THEN** the schema SHALL include:
  - version: "1.0" (string)
  - models: object mapping model_id to model entry
  - aliases: object mapping alias to model_id
- **AND** each model entry SHALL include:
  - id: string (8-char hash)
  - model_type: string (centroid, topdown, etc.)
  - alias: string or null
  - source: string enum
  - downloaded_at or imported_at: ISO 8601 timestamp
  - local_path: string (expanded path)
  - checkpoint_path: string
  - on_worker: boolean
  - worker_last_seen: ISO 8601 timestamp or null
  - worker_path: string or null
  - metrics: object (optional)
  - training_hyperparameters: object (optional)
  - sleap_nn_version: string (optional)
  - tags: array of strings (optional)
  - notes: string (optional)

#### Scenario: Future schema migration
- **WHEN** loading a registry with version < current version
- **THEN** the system SHALL apply migration transforms
- **AND** the system SHALL update version field to current
- **AND** the system SHALL preserve all existing data
- **AND** the system SHALL log the migration action
