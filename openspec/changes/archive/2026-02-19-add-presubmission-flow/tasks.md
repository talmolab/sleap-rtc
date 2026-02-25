## Phase 1: TrainJobSpec Changes

- [ ] 1.1 Add `config_content: Optional[str] = None` field to `TrainJobSpec` in `sleap_rtc/jobs/spec.py`
- [ ] 1.2 Add `path_mappings: Dict[str, str] = field(default_factory=dict)` field to `TrainJobSpec`
- [ ] 1.3 Update `__post_init__` validation: require either `config_paths` or `config_content`
- [ ] 1.4 Update `to_json()` and `from_json()` to handle `config_content` and `path_mappings`
- [ ] 1.5 Update `JobValidator.validate_train_spec()` to accept `config_content` as alternative to `config_paths`
- [ ] 1.6 Add unit tests for new TrainJobSpec fields and validation

**Verification:** `uv run pytest tests/test_jobs.py -v`

## Phase 2: Worker Job Handler

- [ ] 2.1 Update `handle_job_submit()` in `worker_class.py` to detect `config_content` in spec
- [ ] 2.2 Write `config_content` to temp YAML file when present
- [ ] 2.3 Set `config_paths = [temp_path]` and continue with existing flow
- [ ] 2.4 Add cleanup in `finally` block to delete temp file after job completes or fails
- [ ] 2.5 Add unit tests for config_content handling and temp file cleanup

**Verification:** `uv run pytest tests/test_worker.py -v -k "config_content"`

## Phase 3: API and Runner Updates

- [ ] 3.1 Update `api.run_training()` to accept `config_content` parameter
- [ ] 3.2 When `config_content` provided, build TrainJobSpec with `config_content` instead of reading `config_path`
- [ ] 3.3 Update `gui/runners.py` `run_remote_training()` to accept a `TrainJobSpec` directly
- [ ] 3.4 Update `gui/presubmission.py` to pass `config_content` instead of `config_path`
- [ ] 3.5 Add unit tests for updated API and runner signatures

**Verification:** `uv run pytest tests/test_api.py tests/test_gui_runners.py tests/test_gui_presubmission.py -v`

## Phase 4: SLEAP Dialog Integration

- [ ] 4.1 Update `_run_remote_training()` in dialog.py to serialize config to YAML string
- [ ] 4.2 Call `run_presubmission_checks()` with config_content instead of config_path
- [ ] 4.3 Build TrainJobSpec with config_content and resolved path_mappings from result
- [ ] 4.4 Close dialog only after JOB_ACCEPTED; keep open on failure/cancel
- [ ] 4.5 Manual integration test: verify full flow from "Run Remotely" click through presubmission

**Verification:** Manual testing with SLEAP GUI + running worker
