# worker-post-training-inference Specification

## Purpose
TBD - created by archiving change add-post-training-inference. Update Purpose after archive.
## Requirements
### Requirement: Automatic Post-Training Inference

After all pipeline models train successfully, the worker SHALL automatically run inference
on the training labels file using all trained model checkpoints.

#### Scenario: Inference runs after successful single-model training

- **WHEN** a single training model completes successfully
- **THEN** the worker SHALL spawn `sleap track` with the trained checkpoint
- **AND** use the same labels file that was used for training
- **AND** pass `--only_suggested_frames` flag

#### Scenario: Inference runs once after full multi-model pipeline

- **WHEN** all models in a multi-model pipeline complete successfully
- **THEN** the worker SHALL spawn a single `sleap track` with ALL trained checkpoints
- **AND** NOT run inference after each individual model

#### Scenario: Inference skipped after cancellation

- **WHEN** training is cancelled via `MSG_JOB_CANCEL`
- **THEN** the worker SHALL NOT run inference
- **AND** send `INFERENCE_SKIPPED::{"reason": "cancelled"}`

#### Scenario: Inference skipped after pipeline partial failure

- **WHEN** any model in a multi-model pipeline fails
- **THEN** the worker SHALL NOT run inference
- **AND** send `INFERENCE_SKIPPED::{"reason": "training_failed"}`

#### Scenario: Inference runs after Stop Early

- **WHEN** training is stopped early via ZMQ stop command
- **THEN** the worker SHALL run inference (checkpoint was saved)

### Requirement: Inference Output Path

The worker SHALL write predictions to a path derived from the labels file location.

#### Scenario: Output path adjacent to labels file

- **WHEN** training labels are at `/vast/project/labels.slp`
- **THEN** predictions SHALL be written to `/vast/project/labels.predictions.slp`

#### Scenario: Output path for .pkg.slp labels

- **WHEN** training labels are at `/vast/project/labels.pkg.slp`
- **THEN** predictions SHALL be written to `/vast/project/labels.predictions.slp`

### Requirement: Inference Progress Messages

The worker SHALL forward inference progress over the RTC data channel.

#### Scenario: INFERENCE_BEGIN sent before subprocess starts

- **WHEN** inference subprocess is about to be spawned
- **THEN** worker SHALL send `INFERENCE_BEGIN::{}` to client

#### Scenario: INFERENCE_PROGRESS forwarded from stdout

- **WHEN** `sleap track` emits a JSON progress line on stdout
- **THEN** worker SHALL send `INFERENCE_PROGRESS::{json}` to client
- **AND** json SHALL contain `n_processed`, `n_total`, `rate`, `eta` fields

#### Scenario: INFERENCE_COMPLETE sent with predictions path

- **WHEN** inference subprocess exits with return code 0
- **AND** predictions file exists on shared filesystem
- **THEN** worker SHALL send `INFERENCE_COMPLETE::{"predictions_path": "..."}` to client

#### Scenario: INFERENCE_FAILED on subprocess error

- **WHEN** inference subprocess exits with non-zero return code
- **OR** predictions file does not exist after subprocess exits
- **THEN** worker SHALL send `INFERENCE_FAILED::{"error": "..."}` to client

### Requirement: Checkpoint Path Resolution

The worker SHALL determine trained model checkpoint directories from training configs.

#### Scenario: Checkpoint dir derived from config

- **WHEN** training config specifies `trainer_config.save_ckpt_path` and `trainer_config.run_name`
- **THEN** checkpoint directory SHALL be `{save_ckpt_path}/{run_name}/`
- **AND** this path SHALL be passed as a model path to `sleap track`

### Requirement: Cancel During Inference

The worker SHALL handle cancellation requests while inference is running.

#### Scenario: MSG_JOB_CANCEL kills inference subprocess

- **WHEN** client sends `MSG_JOB_CANCEL` while inference is running
- **THEN** worker SHALL terminate the inference subprocess
- **AND** send `INFERENCE_FAILED::{"error": "cancelled"}`

