## Why

When a user clicks "Run Remotely" in SLEAP's Training Configuration dialog, the training config must travel over the WebRTC datachannel (not the shared filesystem) and all SLP/video paths must be validated on the worker before submission. Currently, `TrainJobSpec` requires a local `config_path` that the worker reads from disk, but the GUI client may not share a filesystem with the worker for configs. A presubmission validation flow is needed to check paths, resolve mismatches, and send the config inline.

## What Changes

- Add `config_content` field to `TrainJobSpec` so training configs can be sent over the datachannel as a serialized string instead of requiring a shared filesystem path
- Update worker job handler to write `config_content` to a temp file and clean up after execution
- Update `api.run_training()` to accept `config_content` as an alternative to `config_path`
- Update `gui/runners.py` to accept a `TrainJobSpec` directly instead of building one from loose parameters
- Wire the presubmission flow (auth check → path check → path resolution → submit) into the SLEAP dialog's `_run_remote_training()` method

## Impact

- **Modified specs**:
  - `job-specification`: Add `config_content` field to `TrainJobSpec`, update validation
  - `worker-job-execution`: Handle `config_content` by writing to temp file
- **New spec**:
  - `gui-presubmission`: Presubmission validation orchestration for GUI
- **Affected code**:
  - `sleap_rtc/jobs/spec.py` — Add `config_content` field
  - `sleap_rtc/jobs/validator.py` — Update validation for config_content-based specs
  - `sleap_rtc/worker/worker_class.py` — Handle `config_content` in job handler
  - `sleap_rtc/api.py` — Accept `config_content` in `run_training()`
  - `sleap_rtc/gui/runners.py` — Accept `TrainJobSpec` directly
  - `sleap_rtc/gui/presubmission.py` — Update to pass `config_content` instead of `config_path`
  - `scratch/.../dialog.py` (SLEAP side) — Wire presubmission into `_run_remote_training()`

## Dependencies

- Builds on `add-sleap-gui-integration` (must be merged first — already merged as PR #45)
- Existing `TrainJobSpec`, `JobValidator`, `CommandBuilder` in `sleap_rtc/jobs/`
- Existing presubmission stubs in `sleap_rtc/gui/presubmission.py`
