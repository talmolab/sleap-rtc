## ADDED Requirements

### Requirement: Presubmission Validation Orchestration

The system SHALL run a validation sequence when the user clicks "Run Remotely" in the SLEAP Training Configuration dialog, before any job is submitted.

#### Scenario: All checks pass

- **WHEN** user clicks "Run Remotely"
- **AND** JWT is valid
- **AND** all video paths and SLP path exist on the worker
- **THEN** job is submitted with config_content over the datachannel
- **AND** dialog closes after JOB_ACCEPTED

#### Scenario: Authentication fails

- **WHEN** user clicks "Run Remotely"
- **AND** JWT is expired or missing
- **AND** browser login is attempted but fails or is cancelled
- **THEN** dialog stays open
- **AND** user sees "Login required. Please try again."

#### Scenario: Paths missing but resolved by user

- **WHEN** video paths are missing on the worker
- **AND** PathResolutionDialog is shown
- **AND** user maps all missing paths to correct worker paths
- **THEN** path_mappings are included in the TrainJobSpec
- **AND** submission proceeds with resolved paths

#### Scenario: User cancels path resolution

- **WHEN** PathResolutionDialog is shown
- **AND** user clicks Cancel
- **THEN** dialog stays open (no submission)
- **AND** no error message is shown

### Requirement: Authentication Check

The presubmission flow SHALL verify the user has a valid JWT before proceeding to path checks.

#### Scenario: Valid JWT

- **WHEN** is_logged_in() returns True
- **THEN** authentication check passes
- **AND** flow proceeds to path checking

#### Scenario: Expired JWT with successful re-login

- **WHEN** is_logged_in() returns False
- **AND** browser login is triggered
- **AND** user completes login successfully
- **THEN** authentication check passes
- **AND** flow proceeds to path checking

#### Scenario: Expired JWT with failed re-login

- **WHEN** is_logged_in() returns False
- **AND** browser login times out or user closes the browser
- **THEN** presubmission returns failure
- **AND** PresubmissionResult.success is False

### Requirement: Video Path Validation via WebRTC

The presubmission flow SHALL check that the SLP file and all referenced video paths exist on the worker filesystem via a WebRTC connection.

#### Scenario: All paths found

- **WHEN** check_video_paths() is called with slp_path, room_id, worker_id
- **AND** worker confirms SLP and all videos exist
- **THEN** PathCheckResult.all_found is True
- **AND** no PathResolutionDialog is shown

#### Scenario: Some videos missing

- **WHEN** worker reports 2 of 5 video paths missing
- **THEN** PathResolutionDialog is shown with found/missing list
- **AND** missing paths show suggestions from worker filesystem search

#### Scenario: SLP file missing

- **WHEN** worker reports SLP file does not exist
- **THEN** SLP is shown as missing in PathResolutionDialog
- **AND** user can map it to the correct worker path

#### Scenario: Worker unreachable

- **WHEN** WebRTC connection to worker fails or times out
- **THEN** presubmission returns failure
- **AND** user sees "Could not connect to worker. Check that the worker is running."

### Requirement: Config Delivery Over Datachannel

The presubmission flow SHALL serialize the training config and include it in the TrainJobSpec as config_content for datachannel delivery.

#### Scenario: Config serialized from dialog

- **WHEN** presubmission passes and job is submitted
- **THEN** TrainJobSpec.config_content contains the serialized training config
- **AND** TrainJobSpec.config_paths is empty
- **AND** the spec is sent as JSON over the WebRTC datachannel

#### Scenario: Config with resolved paths

- **WHEN** path resolution produced mappings
- **THEN** TrainJobSpec.labels_path is set to the resolved worker SLP path
- **AND** TrainJobSpec.path_mappings contains {original_video_path: worker_video_path} entries

### Requirement: Dialog State During Presubmission

The SLEAP Training Configuration dialog SHALL remain open and responsive during presubmission checks.

#### Scenario: Dialog stays open on failure

- **WHEN** any presubmission step fails or is cancelled
- **THEN** dialog remains open at the training configuration tab
- **AND** user can modify settings and try again

#### Scenario: Dialog closes on success

- **WHEN** all presubmission checks pass
- **AND** worker sends JOB_ACCEPTED
- **THEN** dialog closes
- **AND** progress monitoring begins via LossViewer

### Requirement: Post-Submission Error Handling

The system SHALL display errors that occur after job submission as popup dialogs.

#### Scenario: Job rejected by worker

- **WHEN** worker sends JOB_REJECTED with validation errors
- **THEN** error popup shows the worker's rejection reason
- **AND** dialog stays open for user to fix issues

#### Scenario: Connection lost during submission

- **WHEN** WebRTC connection drops during JOB_SUBMIT
- **THEN** error popup shows "Connection lost. Try again."
- **AND** dialog stays open

#### Scenario: Training fails during execution

- **WHEN** worker sends JOB_FAILED during training
- **THEN** TrainingFailureDialog shows failure details
- **AND** includes resume instructions if checkpoint exists
