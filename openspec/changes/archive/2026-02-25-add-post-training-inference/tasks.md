## Phase 1: Worker — Checkpoint Path Tracking

- [ ] 1.1 Add `_get_checkpoint_dir(config_path)` helper in `worker_class.py` that parses
      `trainer_config.save_ckpt_path` and `trainer_config.run_name` from the YAML config
      to derive the checkpoint directory path
- [ ] 1.2 Accumulate `trained_model_paths` list in the pipeline loop in `worker_class.py`,
      appending checkpoint dir after each `execute_from_spec()` returns
- [ ] 1.3 Track `worker_labels_path` (already-resolved worker-side path) throughout the
      pipeline loop so it is available for the inference step

**Verification:** Add unit test for `_get_checkpoint_dir()` with sample config YAML

## Phase 2: Worker — `run_inference()` in `job_executor.py`

- [ ] 2.1 Add `run_inference(channel, cmd, predictions_path)` method to `JobExecutor`
      that spawns the `sleap track` subprocess with `start_new_session=True`
- [ ] 2.2 Forward stdout JSON progress lines as `INFERENCE_PROGRESS::{line}` messages;
      skip non-JSON lines (log them only)
- [ ] 2.3 On clean exit (returncode 0) and predictions file present, send
      `INFERENCE_COMPLETE::{"predictions_path": "..."}`, else send `INFERENCE_FAILED::{"error": "..."}`
- [ ] 2.4 Handle `MSG_JOB_CANCEL` during inference: terminate subprocess and send
      `INFERENCE_FAILED::{"error": "cancelled"}`

**Verification:** Manual test with `sleap track` against a small labels file

## Phase 3: Worker — Inference Trigger in `worker_class.py`

- [ ] 3.1 After pipeline loop exits, check skip conditions (cancelled, any failure,
      `save_ckpt=False`) and send `INFERENCE_SKIPPED::{"reason": "..."}` if applicable
- [ ] 3.2 Build `TrackJobSpec` from `worker_labels_path`, `trained_model_paths`,
      `only_suggested_frames=True`, and derived `predictions_path`
- [ ] 3.3 Call `builder.build_track_command(track_spec)`, send `INFERENCE_BEGIN::{}`,
      then `await self.job_executor.run_inference(channel, track_cmd, predictions_path)`
- [ ] 3.4 Handle Stop Early case: treat `stopped_early=True` as success → inference runs

**Verification:** End-to-end test: train 1 epoch, confirm `INFERENCE_BEGIN` + progress
messages appear on client

## Phase 4: Client — `InferenceProgressDialog` in `sleap_rtc/gui/`

- [ ] 4.1 Create `InferenceProgressDialog(QDialog)` with status label, `QProgressBar`,
      and `QTextEdit` log area (dark theme, monospace), plus OK/Cancel buttons
- [ ] 4.2 Add `update(data: dict)` method: parse `n_processed`, `n_total`, `rate`, `eta`
      and update status label + progress bar
- [ ] 4.3 Add `finish(n_frames, n_with_instances, n_empty)` method: show completion summary
      and enable OK button
- [ ] 4.4 Add `show_error(msg: str)` method: display error, enable OK button

**Verification:** `uv run pytest tests/test_inference_dialog.py -v`

## Phase 5: Client — Message Handling in `RemoteProgressBridge`

- [ ] 5.1 Add handler for `INFERENCE_BEGIN::` → open `InferenceProgressDialog`
- [ ] 5.2 Add handler for `INFERENCE_PROGRESS::` → call `dialog.update(data)`
- [ ] 5.3 Add handler for `INFERENCE_COMPLETE::` → call `dialog.finish()`, load `.slp`
      from `predictions_path`, merge into `main_window.labels`
- [ ] 5.4 Add handler for `INFERENCE_FAILED::` → call `dialog.show_error(msg)`
- [ ] 5.5 Add handler for `INFERENCE_SKIPPED::` → log reason, no dialog shown

**Verification:** `uv run pytest tests/test_gui_runners.py -v -k inference`
