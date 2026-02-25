## Phase 1: Python API Foundation

- [ ] 1.1 Create `sleap_rtc/api.py` module skeleton with type hints
- [ ] 1.2 Implement `is_available()` function
- [ ] 1.3 Implement `is_logged_in()` function using existing credential storage
- [ ] 1.4 Implement `login()` function (wraps existing auth flow)
- [ ] 1.5 Implement `logout()` function (wraps credential clearing)
- [ ] 1.6 Add unit tests for authentication functions
- [ ] 1.7 Implement `list_rooms()` function
- [ ] 1.8 Implement `list_workers(room_id)` function
- [ ] 1.9 Add unit tests for discovery functions

**Verification:** `uv run pytest tests/test_api.py -v`

## Phase 2: Path Checking and Config Validation API

- [ ] 2.1 Define `PathCheckResult` dataclass
- [ ] 2.2 Implement `check_video_paths(slp_path, room_id)` function
- [ ] 2.3 Add path suggestion logic (find similar files in nearby folders)
- [ ] 2.4 Define `ValidationResult` dataclass with errors/warnings
- [ ] 2.5 Implement `validate_config(config_path)` function
- [ ] 2.6 Add unit tests for path checking and validation

**Verification:** `uv run pytest tests/test_api.py -v -k "path or valid"`

## Phase 3: Remote Execution API

- [ ] 3.1 Define `ProgressEvent` dataclass
- [ ] 3.2 Define `TrainingResult` dataclass
- [ ] 3.3 Define `InferenceResult` dataclass
- [ ] 3.4 Implement `run_training()` function wrapping RTCClient
- [ ] 3.5 Implement progress callback forwarding
- [ ] 3.6 Implement `run_inference()` function wrapping RTCTrackClient
- [ ] 3.7 Add integration tests for remote execution (mock worker)

**Verification:** `uv run pytest tests/test_api.py -v -k "training or inference"`

## Phase 4: Core GUI Widgets

- [ ] 4.1 Create `sleap_rtc/gui/__init__.py`
- [ ] 4.2 Create `sleap_rtc/gui/widgets.py` skeleton
- [ ] 4.3 Implement `RemoteTrainingWidget(QGroupBox)` layout
- [ ] 4.4 Add enable/disable checkbox functionality
- [ ] 4.5 Add room selection dropdown
- [ ] 4.6 Add worker selection (auto/manual radio buttons + dropdown)
- [ ] 4.7 Add refresh button for worker list
- [ ] 4.8 Add authentication status display and login/logout buttons
- [ ] 4.9 Add connection status indicator
- [ ] 4.10 Capture widget screenshot with qt-testing skill

**Verification:** Run `qt-testing` capture script and visually inspect `scratch/.qt-screenshots/`

## Phase 5: Worker Setup Dialog

- [ ] 5.1 Implement `WorkerSetupDialog(QDialog)` layout
- [ ] 5.2 Add step-by-step setup instructions
- [ ] 5.3 Add "Copy Commands" button with clipboard functionality
- [ ] 5.4 Add "Open Dashboard" button to launch browser
- [ ] 5.5 Add "Open Documentation" button
- [ ] 5.6 Connect dialog to show when room has 0 workers
- [ ] 5.7 Capture dialog screenshot with qt-testing skill

**Verification:** Run `qt-testing` capture script and visually inspect

## Phase 6: Room Browser Dialog

- [ ] 6.1 Implement `RoomBrowserDialog(QDialog)` layout
- [ ] 6.2 Add room list table view (name, date, workers)
- [ ] 6.3 Add refresh button functionality
- [ ] 6.4 Add room selection and OK/Cancel buttons
- [ ] 6.5 Connect dialog to parent widget
- [ ] 6.6 Capture dialog screenshot with qt-testing skill

**Verification:** Run `qt-testing` capture script and visually inspect

## Phase 7: Path Resolution Dialog

- [ ] 7.1 Implement `PathResolutionDialog(QDialog)` layout
- [ ] 7.2 Add path status table (video name, status, worker path)
- [ ] 7.3 Implement "Browse..." button with remote file browser
- [ ] 7.4 Implement "Auto-detect in folder..." functionality
- [ ] 7.5 Add "Continue with Resolved" / "Cancel" buttons
- [ ] 7.6 Connect dialog to pre-submission flow
- [ ] 7.7 Capture dialog screenshot with qt-testing skill

**Verification:** Run `qt-testing` capture script and visually inspect

## Phase 8: Config Validation Dialog

- [ ] 8.1 Implement `ConfigValidationDialog(QDialog)` layout
- [ ] 8.2 Add error list with field names and messages
- [ ] 8.3 Add warning list (non-blocking issues)
- [ ] 8.4 Style errors with red icon, warnings with yellow icon
- [ ] 8.5 Connect dialog to pre-submission flow
- [ ] 8.6 Capture dialog screenshot with qt-testing skill

**Verification:** Run `qt-testing` capture script and visually inspect

## Phase 9: Training Failure Dialog

- [ ] 9.1 Implement failure dialog layout
- [ ] 9.2 Add epoch and error message display
- [ ] 9.3 Add checkpoint path and CLI resume command
- [ ] 9.4 Add "Copy Command" button for resume command
- [ ] 9.5 Connect dialog to training error handler

**Verification:** Run `qt-testing` capture script and visually inspect

## Phase 10: Progress Bridge

- [ ] 10.1 Create `sleap_rtc/gui/runners.py`
- [ ] 10.2 Implement `RemoteProgressBridge` class
- [ ] 10.3 Bridge WebRTC progress messages to ZMQ publisher
- [ ] 10.4 Ensure message format matches sleap-nn `ProgressReporterZMQ`
- [ ] 10.5 Match CLI formatting from cleanup-cli-ux (visual separators)
- [ ] 10.6 Add test that verifies LossViewer compatibility
- [ ] 10.7 Implement `run_remote_training()` entry point function

**Verification:** `uv run pytest tests/test_gui_runners.py -v`

## Phase 11: Pre-submission Flow

- [ ] 11.1 Implement pre-submission validation sequence:
  - Check authentication → show login prompt if needed
  - Check video paths → show PathResolutionDialog if needed
  - Validate config → show ConfigValidationDialog if needed
- [ ] 11.2 Only proceed to training if all checks pass
- [ ] 11.3 Add tests for pre-submission flow

**Verification:** `uv run pytest tests/test_gui_presubmission.py -v`

## Phase 12: Integration Testing

- [ ] 12.1 Create integration test with mock SLEAP preferences
- [ ] 12.2 Test widget visibility based on experimental features flag
- [ ] 12.3 Test full training flow with mock worker
- [ ] 12.4 Test progress forwarding end-to-end
- [ ] 12.5 Test failure scenarios (network error, validation error, training error)
- [ ] 12.6 Document testing approach for SLEAP maintainers

**Verification:** `uv run pytest tests/test_gui_integration.py -v`

## Phase 13: Documentation

- [ ] 13.1 Add docstrings to all public API functions
- [ ] 13.2 Create `docs/gui-integration.md` usage guide
- [ ] 13.3 Add example code for programmatic API usage
- [ ] 13.4 Document SLEAP-side changes needed (for SLEAP PR)
- [ ] 13.5 Document worker setup instructions with screenshots

**Verification:** Review documentation completeness

---

## SLEAP-Side Changes (Separate PRs)

These tasks require PRs to `talmolab/sleap` repository:

### SLEAP PR 1: Feature Gate
- [ ] S1.1 Add `enable_experimental_features: False` to `sleap/prefs.py` defaults
- [ ] S1.2 Add "Help > Experimental Features" checkable menu item in `app.py`
- [ ] S1.3 Connect menu item to preference toggle
- [ ] S1.4 Test preference persistence

### SLEAP PR 2: Widget Integration
- [ ] S2.1 Add conditional import of `sleap_rtc.gui.widgets` in `main_tab.py`
- [ ] S2.2 Add `RemoteTrainingWidget` to `MainTabWidget` layout
- [ ] S2.3 Wire up widget signals to dialog state
- [ ] S2.4 Test with sleap-rtc installed vs not installed

### SLEAP PR 3: Runner Integration
- [ ] S3.1 Modify `run_learning_pipeline()` in `runners.py`
- [ ] S3.2 Add check for remote training mode
- [ ] S3.3 Call `sleap_rtc.gui.runners.run_remote_training()` when enabled
- [ ] S3.4 Pass LossViewer's publish_port for progress forwarding
- [ ] S3.5 Handle remote training errors gracefully
- [ ] S3.6 Update LossViewer title to show "Remote (worker-name)"
