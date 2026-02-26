# model-registry Specification

## Purpose
TBD - created by archiving change add-model-registry. Update Purpose after archive.
## Requirements
### Requirement: Model Registration
The worker SHALL register each trained model in a persistent registry with unique identification and metadata.

#### Scenario: Training job starts
- **WHEN** a training job begins on the worker
- **THEN** the system SHALL generate a unique 8-character model ID using SHA256 hash of the training configuration, dataset hash, and run_name
- **AND** the system SHALL create a registry entry with status "training", creation timestamp, and training parameters

#### Scenario: Training job completes successfully
- **WHEN** a training job completes without errors
- **THEN** the system SHALL update the registry entry with status "completed", completion timestamp, and final metrics (validation loss, epochs completed, best epoch)
- **AND** the system SHALL store the checkpoint file path and training configuration path in the registry

#### Scenario: Hash collision detected
- **WHEN** generating a model ID that already exists in the registry
- **THEN** the system SHALL append a numeric suffix ("-2", "-3", etc.) to ensure uniqueness
- **AND** the system SHALL log a warning about the collision

### Requirement: Model Metadata Storage
The registry SHALL store comprehensive metadata for each model to enable identification and tracking.

#### Scenario: Registry entry created
- **WHEN** a model is registered
- **THEN** the registry entry SHALL include:
  - Model ID (8-char hash)
  - Full hash (64-char SHA256)
  - Run name
  - Model type (centroid, centered_instance, etc.)
  - Training job hash (hash of uploaded package)
  - Creation timestamp (ISO 8601 format)
  - Completion timestamp (ISO 8601 format, null if incomplete)
  - Status (training, completed, interrupted, failed)
  - Checkpoint path (relative to models directory)
  - Config path (path to training_config.yaml)
  - Metrics (validation loss, epochs, etc.)
  - Metadata (dataset name, GPU model, training duration)

#### Scenario: Registry persisted to disk as JSON
- **WHEN** registry is modified and format is JSON
- **THEN** the system SHALL write changes to `models/.registry/manifest.json` using atomic file operations (write to temp file, then rename)
- **AND** the system SHALL maintain JSON formatting with 2-space indentation for human readability

#### Scenario: Registry persisted to disk as YAML
- **WHEN** registry is modified and format is YAML
- **THEN** the system SHALL write changes to `models/.registry/manifest.yaml` using atomic file operations (write to temp file, then rename)
- **AND** the system SHALL maintain YAML formatting for human readability

### Requirement: Model Directory Naming
The worker SHALL organize model checkpoints in directories named using model type and hash for human readability and uniqueness.

#### Scenario: Model checkpoint directory created
- **WHEN** training begins and checkpoint directory is needed
- **THEN** the directory SHALL be named `{model_type}_{short_hash}` (e.g., "centroid_a3f5e8c9")
- **AND** the directory SHALL be created under the `models/` base directory
- **AND** the system SHALL pass this directory name to `sleap-nn train` via `trainer_config.run_name`

### Requirement: Model Listing
The system SHALL provide methods to query and filter models from the registry.

#### Scenario: List all models
- **WHEN** requesting a list of all models
- **THEN** the system SHALL return all registry entries sorted by creation timestamp (newest first)

#### Scenario: Filter models by status
- **WHEN** requesting models with a specific status filter
- **THEN** the system SHALL return only models matching the specified status (training, completed, interrupted, failed)

#### Scenario: Filter models by type
- **WHEN** requesting models with a specific model type filter
- **THEN** the system SHALL return only models matching the specified model type (centroid, centered_instance, etc.)

### Requirement: Model Retrieval
The system SHALL provide methods to retrieve individual model metadata and checkpoint paths.

#### Scenario: Get model by ID
- **WHEN** requesting a model by its 8-character ID
- **THEN** the system SHALL return the complete registry entry for that model
- **AND** if the model ID does not exist, the system SHALL return None

#### Scenario: Resolve checkpoint path
- **WHEN** requesting the checkpoint path for a model ID
- **THEN** the system SHALL return the absolute path to the model's `best.ckpt` file
- **AND** if the checkpoint file does not exist on disk, the system SHALL log a warning and return the path anyway

### Requirement: Registry Initialization
The system SHALL initialize the registry on first use and handle missing or corrupted registry files gracefully.

#### Scenario: Registry does not exist
- **WHEN** the worker starts and no registry file exists
- **THEN** the system SHALL create a new registry with version "1.0" and empty models dictionary
- **AND** the system SHALL create the `.registry/` directory if it does not exist
- **AND** the system SHALL use JSON format by default

#### Scenario: Registry format auto-detection
- **WHEN** loading an existing registry
- **THEN** the system SHALL detect the format based on file extension (.json or .yaml)
- **AND** the system SHALL parse the file using the appropriate parser
- **AND** if both formats exist, the system SHALL prefer the most recently modified file

#### Scenario: Registry is corrupted
- **WHEN** the registry file exists but contains invalid JSON or YAML
- **THEN** the system SHALL log an error with the corruption details
- **AND** the system SHALL create a backup of the corrupted file with timestamp suffix
- **AND** the system SHALL initialize a fresh registry

### Requirement: Model Hash Generation
The system SHALL generate deterministic model hashes based on training configuration and dataset to ensure reproducibility.

#### Scenario: Generate model hash
- **WHEN** creating a model ID for a new training job
- **THEN** the system SHALL compute a SHA256 hash from:
  - Model type (from `head_configs` keys)
  - Backbone configuration (architecture, filters, etc.)
  - Run name (timestamp-based identifier)
  - Dataset MD5 hash (hash of labels file)
- **AND** the system SHALL use JSON serialization with sorted keys for deterministic string representation
- **AND** the system SHALL return the first 8 hexadecimal characters of the hash as the model ID

#### Scenario: Same configuration produces same hash
- **WHEN** two training jobs use identical configuration files, dataset, and run_name
- **THEN** they SHALL generate the same model ID (collision detection will add suffix to second job)

