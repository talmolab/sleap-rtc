# cli-job-submission Specification

## Purpose
TBD - created by archiving change add-structured-job-specs. Update Purpose after archive.
## Requirements
### Requirement: Train Command Config-Based Interface

The `sleap-rtc train` command SHALL accept a config file path for structured job submission.

#### Scenario: Train with config path only

- **WHEN** user runs `sleap-rtc train --room lab --config /vast/project/centroid.yaml`
- **THEN** client SHALL build TrainJobSpec with config_path
- **AND** client SHALL submit job to worker via JOB_SUBMIT message
- **AND** client SHALL NOT use legacy pkg-path flow

#### Scenario: Train with config and labels override

- **WHEN** user runs `sleap-rtc train --room lab --config /vast/config.yaml --labels /vast/labels.slp`
- **THEN** TrainJobSpec SHALL have labels_path set
- **AND** labels_path SHALL override data_config.train_labels_path in config

#### Scenario: Train with validation labels override

- **WHEN** user runs `sleap-rtc train --room lab --config /vast/config.yaml --val-labels /vast/val.slp`
- **THEN** TrainJobSpec SHALL have val_labels_path set
- **AND** val_labels_path SHALL override data_config.val_labels_path in config

#### Scenario: Train with training hyperparameters

- **WHEN** user runs `sleap-rtc train --room lab --config /vast/config.yaml --max-epochs 100 --batch-size 8 --learning-rate 0.0001`
- **THEN** TrainJobSpec SHALL include all hyperparameter overrides
- **AND** overrides SHALL apply via Hydra syntax on worker

#### Scenario: Train with run name

- **WHEN** user runs `sleap-rtc train --room lab --config /vast/config.yaml --run-name experiment-1`
- **THEN** TrainJobSpec SHALL have run_name set
- **AND** run_name SHALL be used for checkpoint directory naming

#### Scenario: Train with resume from checkpoint

- **WHEN** user runs `sleap-rtc train --room lab --config /vast/config.yaml --resume /vast/models/checkpoint.ckpt`
- **THEN** TrainJobSpec SHALL have resume_ckpt_path set
- **AND** training SHALL continue from specified checkpoint

---

### Requirement: Track Command Structured Interface

The `sleap-rtc track` command SHALL accept structured parameters for inference.

#### Scenario: Track with data and models

- **WHEN** user runs `sleap-rtc track --room lab --data-path /vast/labels.slp --model-paths /vast/models/centroid --model-paths /vast/models/instance`
- **THEN** client SHALL build TrackJobSpec
- **AND** model_paths SHALL be list with both paths

#### Scenario: Track with output path

- **WHEN** user runs `sleap-rtc track --room lab --data-path /vast/data.slp --model-paths /vast/model --output /vast/predictions.slp`
- **THEN** TrackJobSpec SHALL have output_path set

#### Scenario: Track with inference options

- **WHEN** user runs `sleap-rtc track --room lab --data-path /vast/data.slp --model-paths /vast/model --batch-size 8 --peak-threshold 0.3`
- **THEN** TrackJobSpec SHALL include batch_size and peak_threshold

#### Scenario: Track only suggested frames

- **WHEN** user runs `sleap-rtc track --room lab --data-path /vast/data.slp --model-paths /vast/model --only-suggested-frames`
- **THEN** TrackJobSpec SHALL have only_suggested_frames=True

#### Scenario: Track specific frame range

- **WHEN** user runs `sleap-rtc track --room lab --data-path /vast/data.slp --model-paths /vast/model --frames "0-100,200-300"`
- **THEN** TrackJobSpec SHALL have frames set to provided range string

---

### Requirement: Backward Compatibility with pkg-path

The train command SHALL maintain backward compatibility with existing `--pkg-path` workflow.

#### Scenario: Train with pkg-path shows deprecation warning

- **WHEN** user runs `sleap-rtc train --room lab --pkg-path /vast/training.pkg.slp`
- **THEN** client SHALL log deprecation warning
- **AND** client SHALL proceed with legacy workflow
- **AND** warning SHALL suggest using --config with --labels

#### Scenario: Mutually exclusive config and pkg-path

- **WHEN** user provides both `--config` and `--pkg-path`
- **THEN** CLI SHALL return validation error
- **AND** error message SHALL explain options are mutually exclusive

---

### Requirement: Job Submission Protocol

The client SHALL submit jobs using structured protocol messages.

#### Scenario: Send job submission message

- **WHEN** client has validated job spec locally
- **AND** WebRTC connection is established
- **THEN** client SHALL send `JOB_SUBMIT::{json_spec}` message
- **AND** client SHALL wait for worker response

#### Scenario: Handle job accepted response

- **WHEN** worker sends `JOB_ACCEPTED::{job_id}`
- **THEN** client SHALL store job_id for tracking
- **AND** client SHALL enter progress monitoring mode
- **AND** client SHALL display "Job accepted" message

#### Scenario: Handle job rejected response

- **WHEN** worker sends `JOB_REJECTED::{errors_json}`
- **THEN** client SHALL parse validation errors
- **AND** client SHALL display each error with field name and message
- **AND** client SHALL offer path correction for path-related errors

#### Scenario: Handle job progress messages

- **WHEN** worker sends `JOB_PROGRESS::{progress_json}`
- **THEN** client SHALL display progress information
- **AND** display SHALL include epoch, loss, val_loss if present

#### Scenario: Handle job completion

- **WHEN** worker sends `JOB_COMPLETE::{result_json}`
- **THEN** client SHALL display completion message
- **AND** client SHALL show output paths from result

#### Scenario: Handle job failure

- **WHEN** worker sends `JOB_FAILED::{error_json}`
- **THEN** client SHALL display error message
- **AND** client SHALL exit with non-zero status

---

### Requirement: Path Correction on Validation Failure

The client SHALL offer interactive path correction when job validation fails due to path errors.

#### Scenario: Prompt for path correction

- **WHEN** JOB_REJECTED contains path-not-found error
- **THEN** client SHALL display error message with invalid path
- **AND** client SHALL ask "Would you like to browse for the correct file?"
- **AND** if user confirms, client SHALL launch DirectoryBrowser

#### Scenario: Resubmit after path correction

- **WHEN** user corrects path via DirectoryBrowser
- **THEN** client SHALL update job spec with corrected path
- **AND** client SHALL resubmit job with corrected spec
- **AND** client SHALL NOT prompt again for same field if still invalid

#### Scenario: Cancel path correction

- **WHEN** user declines path correction prompt
- **THEN** client SHALL display original error
- **AND** client SHALL exit with error status

#### Scenario: Multiple path errors

- **WHEN** JOB_REJECTED contains multiple path errors
- **THEN** client SHALL prompt for each invalid path in sequence
- **AND** client SHALL collect all corrections before resubmitting

