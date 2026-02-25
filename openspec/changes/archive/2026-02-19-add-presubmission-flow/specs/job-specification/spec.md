## MODIFIED Requirements

### Requirement: Train Job Specification Data Type

A TrainJobSpec SHALL contain fields for training configuration, supporting both file-path-based configs (for CLI/shared storage) and inline config content (for GUI/datachannel delivery).

#### Scenario: Create train job spec with config_content

- **WHEN** creating a TrainJobSpec with config_content="model_config:\n  backbone: unet\n"
- **AND** labels_path="/mnt/data/labels.slp"
- **THEN** spec has config_content set to the YAML string
- **AND** config_paths is empty

#### Scenario: Create train job spec with config_paths (existing behavior)

- **WHEN** creating a TrainJobSpec with config_paths=["/mnt/data/config.yaml"]
- **AND** labels_path="/mnt/data/labels.slp"
- **THEN** spec has config_paths set
- **AND** config_content is None

#### Scenario: Validation requires config_paths or config_content

- **WHEN** creating a TrainJobSpec with no config_paths and no config_content
- **THEN** validation raises an error indicating either config_paths or config_content is required

#### Scenario: Serialize train job spec with config_content to JSON

- **WHEN** a TrainJobSpec has config_content set
- **AND** to_json() is called
- **THEN** the JSON includes "config_content" key with the YAML string value
- **AND** the JSON can be deserialized back with from_json()

#### Scenario: Serialize train job spec with path_mappings to JSON

- **WHEN** a TrainJobSpec has path_mappings={"C:/data/vid.mp4": "/mnt/data/vid.mp4"}
- **AND** to_json() is called
- **THEN** the JSON includes "path_mappings" key with the mapping dict
- **AND** the JSON can be deserialized back with from_json()

### Requirement: Job Spec Validation

The system SHALL validate job specifications before execution, checking paths, numeric ranges, and config source.

#### Scenario: Validate train spec with config_content

- **WHEN** validating a TrainJobSpec with config_content set
- **AND** labels_path exists within allowed mounts
- **THEN** validation passes with no errors

#### Scenario: Validate train spec with neither config_paths nor config_content

- **WHEN** validating a TrainJobSpec with empty config_paths and no config_content
- **THEN** validation returns an error with field="config" and code="MISSING_CONFIG"

#### Scenario: Validate train spec with valid paths

- **WHEN** validating a TrainJobSpec
- **AND** all paths (labels_path, val_labels_path, resume_ckpt_path) exist within allowed mounts
- **THEN** validation returns no errors

#### Scenario: Validate train spec with path outside mounts

- **WHEN** validating a TrainJobSpec with labels_path="/etc/passwd"
- **AND** allowed mounts are ["/mnt/data"]
- **THEN** validation returns error with field="labels_path" and code="NOT_ALLOWED"
- **AND** error message includes the disallowed path

#### Scenario: Validate train spec with non-existent path

- **WHEN** validating a TrainJobSpec with labels_path="/mnt/data/missing.slp"
- **AND** the file does not exist
- **THEN** validation returns error with field="labels_path" and code="PATH_NOT_FOUND"
- **AND** error message includes the path

#### Scenario: Validate train spec with invalid numeric value

- **WHEN** validating a TrainJobSpec with max_epochs=-1
- **THEN** validation returns error with field="max_epochs" and code="INVALID_VALUE"

#### Scenario: Multiple validation errors

- **WHEN** validating a TrainJobSpec with missing labels_path and invalid max_epochs
- **THEN** all errors are returned together (not just the first one)

## ADDED Requirements

### Requirement: Train Job Spec Path Mappings

A TrainJobSpec SHALL support an optional `path_mappings` field containing a dictionary that maps original client-side paths to resolved worker-side paths.

#### Scenario: Path mappings applied during execution

- **WHEN** a TrainJobSpec has path_mappings={"C:/Users/data/video.mp4": "/mnt/shared/video.mp4"}
- **AND** the worker executes the job
- **THEN** the worker uses the mapped worker-side paths for video file access

#### Scenario: Empty path mappings

- **WHEN** a TrainJobSpec has empty path_mappings
- **THEN** no path remapping is performed
- **AND** the spec is valid
