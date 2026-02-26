## ADDED Requirements

### Requirement: API Availability Check

The sleap-rtc API SHALL provide a method to check if sleap-rtc is available and properly configured.

#### Scenario: Check availability when installed
- **WHEN** `sleap_rtc.api.is_available()` is called
- **AND** sleap-rtc is properly installed
- **THEN** the function SHALL return `True`

#### Scenario: Check availability when not configured
- **WHEN** `sleap_rtc.api.is_available()` is called
- **AND** configuration is missing or invalid
- **THEN** the function SHALL return `False`

### Requirement: Authentication Status

The sleap-rtc API SHALL provide methods to check and manage authentication status.

#### Scenario: Check login status when authenticated
- **WHEN** `sleap_rtc.api.is_logged_in()` is called
- **AND** valid JWT credentials exist
- **THEN** the function SHALL return `True`

#### Scenario: Check login status when not authenticated
- **WHEN** `sleap_rtc.api.is_logged_in()` is called
- **AND** no valid credentials exist
- **THEN** the function SHALL return `False`

#### Scenario: Initiate login flow
- **WHEN** `sleap_rtc.api.login()` is called
- **THEN** the system SHALL open the default browser to the authentication page
- **AND** the function SHALL return when authentication completes or times out

#### Scenario: Logout and clear credentials
- **WHEN** `sleap_rtc.api.logout()` is called
- **THEN** the system SHALL clear stored JWT credentials
- **AND** subsequent `is_logged_in()` calls SHALL return `False`

### Requirement: Room Discovery

The sleap-rtc API SHALL provide methods to discover available rooms.

#### Scenario: List available rooms
- **WHEN** `sleap_rtc.api.list_rooms()` is called
- **AND** user is authenticated
- **THEN** the function SHALL return a list of `Room` objects
- **AND** each Room SHALL have `id`, `name`, and `created_at` attributes

#### Scenario: List rooms when not authenticated
- **WHEN** `sleap_rtc.api.list_rooms()` is called
- **AND** user is not authenticated
- **THEN** the function SHALL raise `AuthenticationError`

### Requirement: Worker Discovery

The sleap-rtc API SHALL provide methods to discover available workers in a room.

#### Scenario: List workers in room
- **WHEN** `sleap_rtc.api.list_workers(room_id)` is called
- **AND** room exists and user has access
- **THEN** the function SHALL return a list of `Worker` objects
- **AND** each Worker SHALL have `id`, `name`, `gpu_info`, and `status` attributes

#### Scenario: List workers in empty room
- **WHEN** `sleap_rtc.api.list_workers(room_id)` is called
- **AND** no workers are connected to the room
- **THEN** the function SHALL return an empty list

#### Scenario: List workers with invalid room
- **WHEN** `sleap_rtc.api.list_workers(room_id)` is called
- **AND** room does not exist or user lacks access
- **THEN** the function SHALL raise `RoomNotFoundError`

### Requirement: Remote Training Execution

The sleap-rtc API SHALL provide a method to run training remotely.

#### Scenario: Start remote training
- **WHEN** `sleap_rtc.api.run_training(config_path, room_id, worker_id, progress_callback)` is called
- **AND** config is valid and worker is available
- **THEN** the system SHALL submit training job to specified worker
- **AND** the function SHALL call `progress_callback` with progress updates
- **AND** the function SHALL return `TrainingResult` on completion

#### Scenario: Auto-select worker
- **WHEN** `sleap_rtc.api.run_training(config_path, room_id, worker_id=None, ...)` is called
- **AND** `worker_id` is not specified
- **THEN** the system SHALL automatically select the best available worker

#### Scenario: Training with invalid config
- **WHEN** `sleap_rtc.api.run_training(...)` is called
- **AND** config file is invalid or missing
- **THEN** the function SHALL raise `ConfigurationError`

#### Scenario: Training cancelled
- **WHEN** training is in progress
- **AND** `TrainingJob.cancel()` is called
- **THEN** the system SHALL send cancellation signal to worker
- **AND** the function SHALL return partial results if available

### Requirement: Remote Inference Execution

The sleap-rtc API SHALL provide a method to run inference remotely.

#### Scenario: Start remote inference
- **WHEN** `sleap_rtc.api.run_inference(model_paths, video_path, room_id, worker_id, progress_callback)` is called
- **AND** models and video are valid
- **THEN** the system SHALL submit inference job to specified worker
- **AND** the function SHALL call `progress_callback` with progress updates
- **AND** the function SHALL return `InferenceResult` on completion

#### Scenario: Inference with multiple models
- **WHEN** `sleap_rtc.api.run_inference(model_paths=[centroid, instance], ...)` is called
- **THEN** the system SHALL use all specified models in the inference pipeline

### Requirement: Video Path Checking

The sleap-rtc API SHALL provide a method to check if video paths are accessible on a worker.

#### Scenario: Check paths when all videos found
- **WHEN** `sleap_rtc.api.check_video_paths(slp_path, room_id)` is called
- **AND** all video paths in the SLP are accessible on the worker
- **THEN** the function SHALL return `PathCheckResult` with `all_found=True`

#### Scenario: Check paths when videos missing
- **WHEN** `sleap_rtc.api.check_video_paths(slp_path, room_id)` is called
- **AND** some video paths are not accessible on the worker
- **THEN** the function SHALL return `PathCheckResult` with `all_found=False`
- **AND** `missing_videos` SHALL list the inaccessible paths

#### Scenario: Check paths with suggested resolutions
- **WHEN** videos are missing
- **AND** similar files exist in nearby directories
- **THEN** `PathCheckResult.suggestions` SHALL contain suggested path mappings

### Requirement: Config Validation

The sleap-rtc API SHALL provide a method to validate training configs before submission.

#### Scenario: Validate valid config
- **WHEN** `sleap_rtc.api.validate_config(config_path)` is called
- **AND** config is valid
- **THEN** the function SHALL return `ValidationResult` with `valid=True`

#### Scenario: Validate invalid config
- **WHEN** `sleap_rtc.api.validate_config(config_path)` is called
- **AND** config has errors
- **THEN** the function SHALL return `ValidationResult` with `valid=False`
- **AND** `errors` SHALL list each validation error with field and message

#### Scenario: Validate config with warnings
- **WHEN** config is valid but has non-blocking issues
- **THEN** `ValidationResult.warnings` SHALL list the warnings

### Requirement: Progress Callback Interface

The sleap-rtc API SHALL define a standard progress callback interface.

#### Scenario: Receive training progress
- **WHEN** training epoch completes
- **THEN** callback SHALL be called with `ProgressEvent` containing:
  - `event_type`: "epoch_end"
  - `epoch`: current epoch number
  - `metrics`: dict with train_loss, val_loss, etc.

#### Scenario: Receive training start event
- **WHEN** training begins
- **THEN** callback SHALL be called with `ProgressEvent` containing:
  - `event_type`: "train_begin"
  - `wandb_url`: optional WandB run URL

#### Scenario: Receive training end event
- **WHEN** training completes
- **THEN** callback SHALL be called with `ProgressEvent` containing:
  - `event_type`: "train_end"
  - `success`: boolean
  - `error_message`: optional error if failed
