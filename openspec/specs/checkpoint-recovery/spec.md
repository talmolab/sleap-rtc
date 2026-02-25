# checkpoint-recovery Specification

## Purpose
TBD - created by archiving change add-model-registry. Update Purpose after archive.
## Requirements
### Requirement: Training State Tracking
The worker SHALL track the current state of training jobs to enable recovery from interruptions.

#### Scenario: Training state recorded at start
- **WHEN** a training job begins
- **THEN** the system SHALL record in the registry:
  - Job ID (from current_job if available)
  - Model ID being trained
  - Status set to "training"
  - Current epoch (initially 0)
  - Last checkpoint path (initially null)

#### Scenario: Training state updated during execution
- **WHEN** training is in progress and a checkpoint is saved
- **THEN** the system SHALL update the registry with:
  - Last checkpoint path (e.g., "models/centroid_a3f5e8c9/best.ckpt")
  - Current epoch number
  - Latest validation metrics

### Requirement: Connection Drop Detection
The worker SHALL detect WebRTC connection failures during training and mark jobs as interrupted.

#### Scenario: ICE connection lost during training
- **WHEN** the ICE connection state changes to "failed", "disconnected", or "closed" while a training job is active
- **THEN** the system SHALL mark the current model in the registry with status "interrupted"
- **AND** the system SHALL record the last known checkpoint path and epoch number
- **AND** the system SHALL add the model ID to the "interrupted" list in the registry

#### Scenario: Connection lost but training continues
- **WHEN** the WebRTC connection drops but the training process is still running on the worker
- **THEN** the training process SHALL continue to completion if possible
- **AND** the model SHALL remain marked as "interrupted" until the user reconnects and confirms completion

### Requirement: Interrupted Job Query
The system SHALL provide methods to identify training jobs that were interrupted and can be resumed.

#### Scenario: Query interrupted jobs
- **WHEN** requesting a list of interrupted training jobs
- **THEN** the system SHALL return all models with status "interrupted" that have valid checkpoint paths
- **AND** the results SHALL include the model ID, last checkpoint path, and epoch number for resumption

#### Scenario: No interrupted jobs exist
- **WHEN** requesting interrupted jobs and none are present
- **THEN** the system SHALL return an empty list

### Requirement: Training Resumption
The worker SHALL resume interrupted training from the last saved checkpoint when requested.

#### Scenario: Resume from checkpoint
- **WHEN** starting a training job and an interrupted job for the same model exists in the registry
- **THEN** the system SHALL construct the `sleap-nn train` command with the parameter:
  - `trainer_config.resume_ckpt_path={checkpoint_path}` where checkpoint_path is the absolute path to the last checkpoint
- **AND** the system SHALL update the model status from "interrupted" to "training"
- **AND** PyTorch Lightning SHALL automatically load the checkpoint and continue from the saved epoch

#### Scenario: Resume checkpoint does not exist
- **WHEN** attempting to resume from a checkpoint that no longer exists on disk
- **THEN** the system SHALL log an error indicating the checkpoint file is missing
- **AND** the system SHALL start training from scratch (epoch 0)
- **AND** the system SHALL update the registry to remove the invalid checkpoint path

### Requirement: Checkpoint Path Resolution
The system SHALL resolve checkpoint paths for resumption using the model registry.

#### Scenario: Get resumable checkpoint path
- **WHEN** requesting the checkpoint path for an interrupted model
- **THEN** the system SHALL return the absolute path constructed from:
  - Base directory: unzipped training job directory
  - Relative path: stored in registry (e.g., "models/centroid_a3f5e8c9/best.ckpt")

#### Scenario: Checkpoint file validation
- **WHEN** resolving a checkpoint path for resumption
- **THEN** the system SHOULD verify the file exists on disk before returning the path
- **AND** if the file is missing, the system SHOULD log a warning

### Requirement: Training Completion After Resume
The worker SHALL properly update registry state when resumed training completes.

#### Scenario: Resumed training completes successfully
- **WHEN** a resumed training job reaches the target epoch count without errors
- **THEN** the system SHALL update the registry with:
  - Status changed from "training" to "completed"
  - Completion timestamp set to current time
  - Final metrics (validation loss, total epochs, etc.)
- **AND** the system SHALL remove the model ID from the "interrupted" list

#### Scenario: Resumed training fails again
- **WHEN** a resumed training job encounters another connection drop or error
- **THEN** the system SHALL mark the model as "interrupted" again
- **AND** the system SHALL update the checkpoint path and epoch to the latest saved state
- **AND** the system SHALL allow further resumption attempts

### Requirement: Interrupted Job Cleanup
The system SHALL provide mechanisms to manage interrupted jobs that are no longer needed.

#### Scenario: Mark interrupted job as abandoned
- **WHEN** a user decides not to resume an interrupted job
- **THEN** the system SHALL allow marking the job status as "failed" or "abandoned"
- **AND** the system SHALL remove it from the "interrupted" list
- **AND** the checkpoint files SHALL remain on disk for manual inspection

### Requirement: Automatic Recovery on Reconnection
The worker SHALL check for interrupted jobs when a new connection is established.

#### Scenario: Worker reconnects after connection drop
- **WHEN** the worker establishes a new WebRTC connection with a client
- **AND** the registry contains interrupted jobs
- **THEN** the system SHALL log information about the interrupted jobs
- **AND** the system SHOULD notify the client that resumable jobs are available (future enhancement)

#### Scenario: Fresh training requested despite interrupted job
- **WHEN** a training command is received for a model that has an interrupted job
- **AND** the training package does not specify resumption
- **THEN** the system SHALL start a new training run from scratch
- **AND** the previous interrupted job SHALL remain in the registry with a different model ID (due to new run_name timestamp)

