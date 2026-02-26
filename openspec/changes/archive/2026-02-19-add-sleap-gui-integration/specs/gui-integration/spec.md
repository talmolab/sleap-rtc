## ADDED Requirements

### Requirement: Remote Training Widget

The sleap-rtc GUI SHALL provide a `RemoteTrainingWidget` for embedding in SLEAP's Training Configuration dialog.

#### Scenario: Widget displays when experimental features enabled
- **WHEN** SLEAP's `enable_experimental_features` preference is `True`
- **AND** sleap-rtc is installed
- **THEN** `RemoteTrainingWidget` SHALL be visible in Training Configuration dialog

#### Scenario: Widget hidden when experimental features disabled
- **WHEN** SLEAP's `enable_experimental_features` preference is `False`
- **THEN** `RemoteTrainingWidget` SHALL NOT be visible

#### Scenario: Widget hidden when sleap-rtc not installed
- **WHEN** sleap-rtc is not installed
- **THEN** `RemoteTrainingWidget` SHALL NOT be visible
- **AND** no import errors SHALL occur

### Requirement: Remote Training Toggle

The `RemoteTrainingWidget` SHALL provide a checkbox to enable/disable remote training.

#### Scenario: Enable remote training
- **WHEN** user checks "Enable Remote Training" checkbox
- **THEN** remote training configuration fields SHALL become enabled
- **AND** clicking "Run" SHALL submit to remote worker instead of local

#### Scenario: Disable remote training
- **WHEN** user unchecks "Enable Remote Training" checkbox
- **THEN** remote training configuration fields SHALL be disabled
- **AND** clicking "Run" SHALL use local training as normal

### Requirement: Room Selection

The `RemoteTrainingWidget` SHALL provide room selection functionality.

#### Scenario: Display room dropdown
- **WHEN** widget is displayed
- **AND** user is authenticated
- **THEN** room dropdown SHALL show available rooms

#### Scenario: Browse rooms button
- **WHEN** user clicks "Browse..." button
- **THEN** `RoomBrowserDialog` SHALL open
- **AND** dialog SHALL show room details and worker counts

#### Scenario: Room selection updates workers
- **WHEN** user selects a room from dropdown
- **THEN** worker dropdown SHALL be populated with workers in that room

### Requirement: Worker Selection

The `RemoteTrainingWidget` SHALL provide worker selection functionality.

#### Scenario: Auto-select worker option
- **WHEN** "Auto-select (best GPU)" radio button is selected
- **THEN** system SHALL automatically choose worker when training starts

#### Scenario: Manual worker selection
- **WHEN** "Choose worker" radio button is selected
- **THEN** worker dropdown SHALL be enabled
- **AND** dropdown SHALL show worker name, GPU info, and status

#### Scenario: Display worker details
- **WHEN** worker dropdown is populated
- **THEN** each option SHALL display: "{worker_name} ({gpu_name}, {gpu_memory}GB)"

### Requirement: Authentication Status Display

The `RemoteTrainingWidget` SHALL display authentication status.

#### Scenario: Display logged in status
- **WHEN** user is authenticated
- **THEN** widget SHALL display "Status: Logged in as {email}"
- **AND** "Logout" button SHALL be enabled

#### Scenario: Display not logged in status
- **WHEN** user is not authenticated
- **THEN** widget SHALL display "Status: Not logged in"
- **AND** "Login..." button SHALL be enabled

#### Scenario: Login button action
- **WHEN** user clicks "Login..." button
- **THEN** system SHALL open browser for authentication
- **AND** status SHALL update when authentication completes

### Requirement: Connection Status Display

The `RemoteTrainingWidget` SHALL display connection status.

#### Scenario: Display connected status
- **WHEN** room is selected
- **AND** connection is established
- **THEN** widget SHALL display "Status: Connected to room {room_id} ({n} workers available)"

#### Scenario: Display disconnected status
- **WHEN** no room is selected
- **OR** connection failed
- **THEN** widget SHALL display appropriate error message

### Requirement: Progress Bridge

The sleap-rtc GUI SHALL bridge remote progress to SLEAP's LossViewer.

#### Scenario: Forward progress to LossViewer
- **WHEN** remote training is running
- **AND** worker sends progress update
- **THEN** progress SHALL be forwarded to local ZMQ socket
- **AND** SLEAP's LossViewer SHALL display the progress

#### Scenario: Maintain message format compatibility
- **WHEN** progress is forwarded
- **THEN** message format SHALL match sleap-nn's `ProgressReporterZMQ` format
- **AND** messages SHALL include: `train_begin`, `epoch_end`, `train_end`

### Requirement: Remote Training Runner

The sleap-rtc GUI SHALL provide `run_remote_training()` function for SLEAP integration.

#### Scenario: Execute remote training
- **WHEN** `run_remote_training(config_path, room_id, worker_id, publish_port)` is called
- **THEN** function SHALL submit training job via sleap-rtc API
- **AND** function SHALL forward progress to specified ZMQ port
- **AND** function SHALL return trained model paths on completion

#### Scenario: Open LossViewer for remote training
- **WHEN** remote training starts
- **THEN** SLEAP's LossViewer SHALL open as with local training
- **AND** LossViewer SHALL receive progress updates via ZMQ

#### Scenario: Handle remote training failure
- **WHEN** remote training fails
- **THEN** error message SHALL be displayed to user
- **AND** LossViewer SHALL show error state

### Requirement: Room Browser Dialog

The sleap-rtc GUI SHALL provide a `RoomBrowserDialog` for detailed room selection.

#### Scenario: Display room list
- **WHEN** dialog opens
- **THEN** dialog SHALL display list of available rooms
- **AND** each room SHALL show: name, creation date, worker count

#### Scenario: Select room from dialog
- **WHEN** user selects a room and clicks "Select"
- **THEN** dialog SHALL close
- **AND** selected room SHALL be set in parent widget

#### Scenario: Refresh room list
- **WHEN** user clicks "Refresh" button
- **THEN** room list SHALL be updated from server

### Requirement: Error Handling in GUI

The sleap-rtc GUI widgets SHALL handle errors gracefully.

#### Scenario: Display network error
- **WHEN** network request fails
- **THEN** widget SHALL display user-friendly error message
- **AND** retry option SHALL be available

#### Scenario: Display authentication error
- **WHEN** authentication is required but missing
- **THEN** widget SHALL prompt user to log in
- **AND** "Login..." button SHALL be highlighted

#### Scenario: Display worker unavailable error
- **WHEN** selected worker becomes unavailable
- **THEN** widget SHALL notify user
- **AND** widget SHALL suggest auto-select or different worker

### Requirement: Worker Setup Dialog

The sleap-rtc GUI SHALL provide a `WorkerSetupDialog` to help users set up their first worker.

#### Scenario: Show dialog when no workers available
- **WHEN** user selects a room with 0 workers
- **THEN** `WorkerSetupDialog` SHALL be displayed
- **AND** dialog SHALL show step-by-step setup instructions

#### Scenario: Provide installation command
- **WHEN** dialog is displayed
- **THEN** dialog SHALL show `pip install sleap-rtc` command
- **AND** "Copy Commands" button SHALL copy commands to clipboard

#### Scenario: Link to dashboard for API key
- **WHEN** user clicks "Open Dashboard"
- **THEN** system SHALL open sleap-rtc dashboard in browser
- **AND** user can generate API key from dashboard

#### Scenario: Show worker start command
- **WHEN** dialog is displayed
- **THEN** dialog SHALL show `sleap-rtc worker --api-key ... --name ...` command

### Requirement: Worker Refresh

The `RemoteTrainingWidget` SHALL provide a refresh button to update the worker list.

#### Scenario: Refresh worker list
- **WHEN** user clicks refresh button
- **THEN** worker dropdown SHALL be repopulated with current workers
- **AND** worker status (idle/busy) SHALL be updated

#### Scenario: Show loading indicator during refresh
- **WHEN** refresh is in progress
- **THEN** refresh button SHALL show loading indicator
- **AND** worker dropdown SHALL be disabled

### Requirement: Path Resolution Dialog

The sleap-rtc GUI SHALL provide a `PathResolutionDialog` to fix missing video paths before job submission.

#### Scenario: Show dialog when paths missing
- **WHEN** user clicks "Run" for remote training
- **AND** video paths check reveals missing files
- **THEN** `PathResolutionDialog` SHALL be displayed

#### Scenario: Display path status table
- **WHEN** dialog is displayed
- **THEN** table SHALL show each video with status (Found/Missing)
- **AND** missing videos SHALL have "Browse..." button

#### Scenario: Browse for correct path
- **WHEN** user clicks "Browse..." for a missing video
- **THEN** remote file browser dialog SHALL open
- **AND** user can navigate worker filesystem to find correct file

#### Scenario: Auto-detect paths in folder
- **WHEN** user clicks "Auto-detect in folder..."
- **THEN** system SHALL search selected folder for matching video names
- **AND** found matches SHALL be populated automatically

#### Scenario: Continue with resolved paths
- **WHEN** all paths are resolved
- **AND** user clicks "Continue with Resolved"
- **THEN** dialog SHALL close
- **AND** training SHALL proceed with corrected paths

### Requirement: Config Validation Dialog

The sleap-rtc GUI SHALL provide a `ConfigValidationDialog` to show validation errors before job submission.

#### Scenario: Show dialog on validation failure
- **WHEN** user clicks "Run" for remote training
- **AND** config validation fails
- **THEN** `ConfigValidationDialog` SHALL be displayed

#### Scenario: Display validation errors
- **WHEN** dialog is displayed
- **THEN** each error SHALL show field name and error message
- **AND** errors SHALL be marked with error icon

#### Scenario: Display validation warnings
- **WHEN** config has warnings but no errors
- **THEN** warnings SHALL be shown with warning icon
- **AND** user can proceed despite warnings

#### Scenario: Block submission on errors
- **WHEN** config has validation errors
- **THEN** dialog SHALL only have "OK" button (no proceed option)
- **AND** user must fix config before retrying

### Requirement: Training Failure Dialog

The sleap-rtc GUI SHALL provide informative error dialogs when remote training fails.

#### Scenario: Show failure dialog with details
- **WHEN** remote training fails
- **THEN** error dialog SHALL display failure reason
- **AND** dialog SHALL show epoch at which failure occurred

#### Scenario: Show checkpoint recovery information
- **WHEN** training fails after checkpoints were saved
- **THEN** dialog SHALL show checkpoint path on worker
- **AND** dialog SHALL show CLI command to resume from checkpoint

#### Scenario: Show error message from worker
- **WHEN** worker reports specific error (e.g., CUDA OOM)
- **THEN** dialog SHALL display the worker's error message
