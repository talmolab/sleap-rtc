# Tasks: Add Structured Job Specifications

## Phase 1: Core Infrastructure

### 1.1 Create JobSpec Data Types
- [ ] Create `sleap_rtc/jobs/` package with `__init__.py`
- [ ] Implement `TrainJobSpec` dataclass in `sleap_rtc/jobs/spec.py`
- [ ] Implement `TrackJobSpec` dataclass in `sleap_rtc/jobs/spec.py`
- [ ] Add `to_json()` and `from_json()` methods to both specs
- [ ] Write unit tests for serialization/deserialization

**Verification:** `pytest tests/test_job_spec.py` passes

### 1.2 Implement JobValidator
- [ ] Create `sleap_rtc/jobs/validator.py`
- [ ] Implement `ValidationError` dataclass
- [ ] Implement path validation against FileManager mounts
- [ ] Implement numeric range validation with NUMERIC_CONSTRAINTS
- [ ] Implement `validate_train_spec()` method
- [ ] Implement `validate_track_spec()` method
- [ ] Write unit tests for validation scenarios

**Verification:** `pytest tests/test_job_validator.py` passes

### 1.3 Implement CommandBuilder
- [ ] Create `sleap_rtc/jobs/builder.py`
- [ ] Implement `build_train_command()` - config path splitting, Hydra overrides
- [ ] Implement `build_track_command()` - model paths, optional flags
- [ ] Write unit tests verifying command structure

**Verification:** `pytest tests/test_command_builder.py` passes

---

## Phase 2: Protocol Messages

### 2.1 Add Protocol Message Types
- [ ] Add message constants to `sleap_rtc/protocol.py`:
  - `MSG_JOB_SUBMIT`
  - `MSG_JOB_ACCEPTED`
  - `MSG_JOB_REJECTED`
  - `MSG_JOB_PROGRESS`
  - `MSG_JOB_COMPLETE`
  - `MSG_JOB_FAILED`

**Verification:** Protocol constants importable, no syntax errors

### 2.2 Worker Job Submission Handler
- [ ] Add `handle_job_submit()` method to `RTCWorkerClient`
- [ ] Parse incoming JOB_SUBMIT message
- [ ] Validate spec using JobValidator
- [ ] Send JOB_REJECTED if validation fails (with error details)
- [ ] Send JOB_ACCEPTED if validation passes
- [ ] Build command using CommandBuilder
- [ ] Execute via existing JobExecutor infrastructure

**Verification:** Worker handles JOB_SUBMIT and responds appropriately

### 2.3 Update JobExecutor for Structured Specs
- [ ] Add `execute_from_spec()` method to JobExecutor
- [ ] Accept command list instead of script path
- [ ] Reuse existing log streaming and progress reporting
- [ ] Send JOB_PROGRESS messages during execution
- [ ] Send JOB_COMPLETE or JOB_FAILED on completion

**Verification:** JobExecutor can run from pre-built command list

---

## Phase 3: CLI Train Command

### 3.1 Add New CLI Flags to Train Command
- [ ] Add `--config` option (path to config YAML)
- [ ] Add `--labels` option (override train_labels_path)
- [ ] Add `--val-labels` option (override val_labels_path)
- [ ] Add `--max-epochs` option (int)
- [ ] Add `--batch-size` option (int)
- [ ] Add `--learning-rate` option (float)
- [ ] Add `--run-name` option (str)
- [ ] Add `--resume` option (path to checkpoint)
- [ ] Make `--config` and `--pkg-path` mutually exclusive

**Verification:** `sleap-rtc train --help` shows new options

### 3.2 Implement Structured Job Submission in Client
- [ ] Build TrainJobSpec from CLI arguments
- [ ] Send JOB_SUBMIT message after connection
- [ ] Handle JOB_ACCEPTED response
- [ ] Handle JOB_REJECTED response (display errors)
- [ ] Handle JOB_PROGRESS messages (display progress)
- [ ] Handle JOB_COMPLETE/JOB_FAILED messages

**Verification:** `sleap-rtc train --config ... --room ...` submits job

### 3.3 Add Deprecation Warning for pkg-path
- [ ] Log warning when `--pkg-path` is used
- [ ] Warning message suggests `--config` with `--labels`
- [ ] Existing workflow continues to work

**Verification:** `sleap-rtc train --pkg-path ...` shows warning but works

---

## Phase 4: CLI Track Command

### 4.1 Add New CLI Flags to Track Command
- [ ] Add `--data-path` option (required for new workflow)
- [ ] Add `--model-paths` option (multiple, required)
- [ ] Add `--output` option (output path)
- [ ] Add `--batch-size` option (int)
- [ ] Add `--peak-threshold` option (float)
- [ ] Add `--only-suggested-frames` flag
- [ ] Add `--frames` option (frame range string)

**Verification:** `sleap-rtc track --help` shows new options

### 4.2 Implement Track Job Submission
- [ ] Build TrackJobSpec from CLI arguments
- [ ] Send JOB_SUBMIT message
- [ ] Handle responses (same pattern as train)

**Verification:** `sleap-rtc track --data-path ... --model-paths ... --room ...` works

---

## Phase 5: CLI Directory Browser

### 5.1 Implement DirectoryBrowser Class
- [ ] Create `sleap_rtc/client/directory_browser.py`
- [ ] Implement prompt_toolkit Application with key bindings
- [ ] Implement `_refresh_listing()` async method
- [ ] Implement navigation (up/down/enter/backspace)
- [ ] Implement file filtering
- [ ] Implement size formatting
- [ ] Implement sorting (dirs first, alphabetical)

**Verification:** DirectoryBrowser can be instantiated and displays UI

### 5.2 Integrate with Path Correction Flow
- [ ] Add `prompt_path_correction()` function to client
- [ ] Detect path-related errors in JOB_REJECTED
- [ ] Prompt user to confirm path correction
- [ ] Launch DirectoryBrowser with appropriate filter
- [ ] Update job spec with corrected path
- [ ] Resubmit job

**Verification:** Path correction flow works end-to-end

### 5.3 Write Integration Tests
- [ ] Test DirectoryBrowser navigation
- [ ] Test path correction with mock worker responses
- [ ] Test full train job submission with path correction

**Verification:** `pytest tests/test_directory_browser.py` passes

---

## Phase 6: Documentation & Cleanup

### 6.1 Update CLI Help Text
- [ ] Ensure all new options have descriptive help text
- [ ] Add examples to command docstrings

### 6.2 Update README/Docs
- [ ] Document new training workflow
- [ ] Document new tracking workflow
- [ ] Add migration guide from pkg-path to config

### 6.3 Final Testing
- [ ] Manual end-to-end test: train with config
- [ ] Manual end-to-end test: track with models
- [ ] Manual test: path correction flow
- [ ] Verify backward compatibility with pkg-path

**Verification:** All manual tests pass

---

## Dependencies

```
Phase 1 (Core) ─┬─► Phase 2 (Protocol) ─┬─► Phase 3 (CLI Train)
                │                        │
                │                        └─► Phase 4 (CLI Track)
                │
                └─► Phase 5 (Browser) ──────► Phase 3/4 (Integration)

Phase 6 (Docs) depends on all above
```

## Parallelizable Work

- Phase 1 tasks (1.1, 1.2, 1.3) can be done in parallel
- Phase 3 and Phase 4 can be done in parallel after Phase 2
- Phase 5 can start after Phase 1, integrates with Phase 3/4
