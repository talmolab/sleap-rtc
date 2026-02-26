# job-specification

## Purpose

Define structured data types for training and inference job specifications, with validation and command building capabilities.

## ADDED Requirements

### Requirement: Train Job Specification Data Type

The system SHALL define a `TrainJobSpec` data type for training job configuration.

#### Scenario: Create train job spec with required fields

- **GIVEN** user provides config path `/vast/project/centroid.yaml`
- **WHEN** TrainJobSpec is instantiated
- **THEN** spec SHALL have `config_path` set to provided path
- **AND** all optional fields SHALL default to None

#### Scenario: Create train job spec with all fields

- **GIVEN** user provides config, labels, val_labels, max_epochs, batch_size, learning_rate, run_name, resume path
- **WHEN** TrainJobSpec is instantiated with all fields
- **THEN** spec SHALL store all provided values
- **AND** spec SHALL be serializable to JSON

#### Scenario: Serialize train job spec to JSON

- **GIVEN** a TrainJobSpec instance
- **WHEN** `to_json()` is called
- **THEN** result SHALL be valid JSON string
- **AND** JSON SHALL include `"type": "train"` field
- **AND** JSON SHALL include all non-None fields

#### Scenario: Deserialize train job spec from JSON

- **GIVEN** valid JSON string with type "train"
- **WHEN** `TrainJobSpec.from_json()` is called
- **THEN** result SHALL be TrainJobSpec instance
- **AND** all fields SHALL match JSON values

---

### Requirement: Track Job Specification Data Type

The system SHALL define a `TrackJobSpec` data type for inference job configuration.

#### Scenario: Create track job spec with required fields

- **GIVEN** user provides data_path and model_paths list
- **WHEN** TrackJobSpec is instantiated
- **THEN** spec SHALL have required fields set
- **AND** optional fields SHALL default appropriately

#### Scenario: Create track job spec with all fields

- **GIVEN** user provides data_path, model_paths, output_path, batch_size, peak_threshold, only_suggested_frames, frames
- **WHEN** TrackJobSpec is instantiated with all fields
- **THEN** spec SHALL store all provided values

#### Scenario: Serialize track job spec to JSON

- **GIVEN** a TrackJobSpec instance
- **WHEN** `to_json()` is called
- **THEN** result SHALL be valid JSON string
- **AND** JSON SHALL include `"type": "track"` field

---

### Requirement: Job Spec Validation

The system SHALL validate job specifications before execution.

#### Scenario: Validate train spec with valid paths

- **GIVEN** TrainJobSpec with all paths within allowed mounts
- **AND** all paths exist on filesystem
- **WHEN** validator checks the spec
- **THEN** validation SHALL return empty error list

#### Scenario: Validate train spec with path outside mounts

- **GIVEN** TrainJobSpec with config_path `/etc/passwd`
- **AND** `/etc` is not in allowed mounts
- **WHEN** validator checks the spec
- **THEN** validation SHALL return error for `config_path` field
- **AND** error message SHALL indicate "Path not within allowed mounts"

#### Scenario: Validate train spec with non-existent path

- **GIVEN** TrainJobSpec with labels_path `/vast/project/missing.slp`
- **AND** file does not exist
- **WHEN** validator checks the spec
- **THEN** validation SHALL return error for `labels_path` field
- **AND** error message SHALL indicate "Path does not exist"
- **AND** error SHALL include the invalid path

#### Scenario: Validate train spec with invalid numeric value

- **GIVEN** TrainJobSpec with max_epochs = 0
- **WHEN** validator checks the spec
- **THEN** validation SHALL return error for `max_epochs` field
- **AND** error message SHALL indicate valid range (1 to 10000)

#### Scenario: Validate train spec with out-of-range learning rate

- **GIVEN** TrainJobSpec with learning_rate = 5.0
- **AND** valid range is 1e-10 to 1.0
- **WHEN** validator checks the spec
- **THEN** validation SHALL return error for `learning_rate` field

#### Scenario: Validate track spec with valid configuration

- **GIVEN** TrackJobSpec with existing data_path and model_paths
- **WHEN** validator checks the spec
- **THEN** validation SHALL return empty error list

#### Scenario: Validate track spec with missing model directory

- **GIVEN** TrackJobSpec with model_paths containing non-existent directory
- **WHEN** validator checks the spec
- **THEN** validation SHALL return error for `model_paths[N]` field
- **AND** error SHALL identify which model path is invalid

---

### Requirement: Command Building from Job Spec

The system SHALL build sleap-nn commands from validated job specifications.

#### Scenario: Build train command with minimal spec

- **GIVEN** TrainJobSpec with only config_path `/vast/project/centroid.yaml`
- **WHEN** CommandBuilder builds train command
- **THEN** command SHALL be `["sleap-nn", "train", "--config-name", "centroid.yaml", "--config-dir", "/vast/project", ...]`
- **AND** command SHALL include ZMQ port defaults

#### Scenario: Build train command with labels override

- **GIVEN** TrainJobSpec with config_path and labels_path `/vast/data/labels.slp`
- **WHEN** CommandBuilder builds train command
- **THEN** command SHALL include `data_config.train_labels_path=/vast/data/labels.slp`

#### Scenario: Build train command with all overrides

- **GIVEN** TrainJobSpec with max_epochs=100, batch_size=8, learning_rate=0.0001, run_name="exp1"
- **WHEN** CommandBuilder builds train command
- **THEN** command SHALL include all Hydra override arguments
- **AND** batch_size SHALL apply to both train and val data loaders

#### Scenario: Build train command with resume checkpoint

- **GIVEN** TrainJobSpec with resume_ckpt_path `/vast/models/checkpoint.ckpt`
- **WHEN** CommandBuilder builds train command
- **THEN** command SHALL include `trainer_config.resume_ckpt_path=/vast/models/checkpoint.ckpt`

#### Scenario: Build track command with minimal spec

- **GIVEN** TrackJobSpec with data_path and single model_path
- **WHEN** CommandBuilder builds track command
- **THEN** command SHALL be `["sleap-nn", "track", "--data_path", "...", "--model_paths", "..."]`

#### Scenario: Build track command with multiple models

- **GIVEN** TrackJobSpec with two model_paths (centroid, instance)
- **WHEN** CommandBuilder builds track command
- **THEN** command SHALL include `--model_paths` for each model

#### Scenario: Build track command with all options

- **GIVEN** TrackJobSpec with output_path, batch_size, peak_threshold, only_suggested_frames, frames
- **WHEN** CommandBuilder builds track command
- **THEN** command SHALL include all optional flags
- **AND** boolean flags SHALL be included without values when True

---

### Requirement: Validation Error Structure

The system SHALL return structured validation errors with field information.

#### Scenario: Validation error includes field name

- **GIVEN** validation fails for `labels_path` field
- **WHEN** error is returned
- **THEN** error SHALL include `field: "labels_path"`
- **AND** error SHALL include human-readable `message`
- **AND** error SHALL include `path` if path-related

#### Scenario: Multiple validation errors

- **GIVEN** TrainJobSpec with multiple invalid fields
- **WHEN** validator checks the spec
- **THEN** validation SHALL return all errors (not just first)
- **AND** each error SHALL identify its specific field
