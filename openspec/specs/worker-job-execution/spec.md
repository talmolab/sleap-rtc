# worker-job-execution Specification

## Purpose
TBD - created by archiving change refactor-worker-modular. Update Purpose after archive.
## Requirements
### Requirement: Training Script Parsing

The job executor SHALL parse `train-script.sh` files to extract SLEAP training job configurations.

#### Scenario: Parse sleap-nn train commands

- **WHEN** script contains `sleap-nn train --config-name centroid.yaml`
- **THEN** parser SHALL extract "centroid.yaml" as config name
- **AND** return list of config names for sequential execution

#### Scenario: Multiple training jobs

- **WHEN** script contains 3 sleap-nn train commands
- **THEN** parser SHALL return list with 3 config names in order

### Requirement: Training Job Execution

The job executor SHALL execute training jobs sequentially and stream logs to client via RTC data channel.

#### Scenario: Successful training execution

- **WHEN** training job starts with valid config
- **THEN** executor SHALL send "TRAIN_JOB_START::{job_name}" message
- **AND** stream stdout/stderr logs to client as they arrive
- **AND** send "TRAIN_JOB_END::{job_name}" on successful completion
- **AND** update job status to completed via peer message

#### Scenario: Training job failure

- **WHEN** training process exits with non-zero code
- **THEN** executor SHALL send "TRAIN_JOB_ERROR::{job_name}::{exit_code}" message
- **AND** send job_failed peer message with error details
- **AND** NOT proceed to next job in sequence

#### Scenario: Log streaming with progress

- **WHEN** training outputs progress bars with carriage returns
- **THEN** executor SHALL preserve carriage returns for progress line updates
- **AND** send newline-terminated logs as complete lines

### Requirement: Inference Script Parsing

The job executor SHALL parse `track-script.sh` files to extract SLEAP inference commands.

#### Scenario: Parse sleap-nn track commands

- **WHEN** script contains `sleap-nn track --model centroid.ckpt --video input.mp4`
- **THEN** parser SHALL extract full command with arguments
- **AND** handle multi-line commands with backslash continuation

### Requirement: Inference Job Execution

The job executor SHALL execute inference jobs and return predictions file to client.

#### Scenario: Successful inference execution

- **WHEN** inference job starts with valid model and video
- **THEN** executor SHALL send "INFERENCE_START" message
- **AND** send "INFERENCE_JOB_START::inference" message
- **AND** stream track logs to client
- **AND** send predictions file when complete
- **AND** send job_complete peer message

#### Scenario: Inference without predictions file

- **WHEN** inference completes but no .predictions.slp file generated
- **THEN** executor SHALL log warning
- **AND** send job_complete with warning in result

### Requirement: Shared Storage Job Processing

The job executor SHALL process jobs using shared filesystem when available, avoiding RTC file transfer.

#### Scenario: Training via shared storage

- **WHEN** client sends job via shared storage paths
- **THEN** executor SHALL read training package from shared input path
- **AND** unzip to shared storage (not local directory)
- **AND** execute training with output to shared output path
- **AND** send job completion notification with relative output path

#### Scenario: Shared storage file not found

- **WHEN** input path does not exist in shared storage
- **THEN** executor SHALL send "JOB_FAILED" message with FileNotFoundError
- **AND** NOT attempt to execute job

### Requirement: Progress Reporting Integration

The job executor SHALL integrate with progress reporter for real-time training metrics when GUI mode enabled.

#### Scenario: GUI mode training with ZMQ

- **WHEN** job starts in GUI mode (gui=True)
- **THEN** executor SHALL start progress listener task
- **AND** initialize ZMQ control socket before training
- **AND** stream ZMQ progress reports to client
- **AND** cancel progress listener when training completes

#### Scenario: CLI mode training without ZMQ

- **WHEN** job starts in CLI mode (gui=False)
- **THEN** executor SHALL NOT start progress listener
- **AND** stream logs directly without ZMQ overhead

