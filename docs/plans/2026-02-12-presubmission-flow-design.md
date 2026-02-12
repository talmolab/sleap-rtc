# Presubmission Flow for Remote Training

**Date:** 2026-02-12
**Status:** Approved

## Overview

When the user clicks "Run Remotely" in SLEAP's Training Configuration dialog, a presubmission validation flow runs before any job is submitted. The config travels over the WebRTC datachannel as JSON. Video and SLP paths must exist on the worker's shared filesystem and are validated via a live WebRTC connection to the worker.

## Flow

```
User clicks "Run Remotely"
    │
    ├─ 1. Build config from dialog form (serialize to YAML string, keep in memory)
    │
    ├─ 2. Authentication check
    │     └─ Is JWT valid? If not → prompt browser login → if fails → return to dialog
    │
    ├─ 3. Video path check (WebRTC to worker)
    │     ├─ Connect to selected worker in room
    │     ├─ Send SLP path → worker checks if SLP exists
    │     ├─ Worker checks all video paths referenced in SLP
    │     └─ Returns: found/missing list with suggestions
    │
    ├─ 4. Path resolution (if any paths missing)
    │     ├─ Show PathResolutionDialog with found/missing paths
    │     ├─ User maps missing paths to correct worker paths
    │     └─ If user cancels → return to dialog (no submission)
    │
    ├─ 5. Submit job over WebRTC datachannel
    │     ├─ TrainJobSpec with:
    │     │   ├─ config_content: serialized training config (YAML string)
    │     │   ├─ labels_path: resolved SLP path on worker
    │     │   └─ path_mappings: {original_video_path → worker_video_path}
    │     ├─ Worker receives JOB_SUBMIT message
    │     ├─ Worker writes config_content to temp file
    │     ├─ Worker validates all paths within allowed mounts
    │     └─ Worker sends JOB_ACCEPTED or JOB_REJECTED
    │
    └─ 6. Progress monitoring (dialog closes after JOB_ACCEPTED)
          └─ JOB_PROGRESS → ZMQ → SLEAP LossViewer
```

Key principle: The dialog stays open until step 4 passes. Only after all paths are confirmed and the job is accepted does it close.

## What travels over WebRTC vs. shared filesystem

- **Over datachannel:** Training config (as JSON/YAML string in TrainJobSpec)
- **Shared filesystem:** SLP file and video files (must be mounted on both client and worker)

## Component Changes

### A. TrainJobSpec (sleap_rtc/jobs/spec.py)

Add one new optional field:

```python
config_content: Optional[str] = None  # Training config sent over datachannel
```

- When `config_content` is present, `config_paths` becomes optional
- Update `__post_init__` validation: require either `config_paths` or `config_content`
- Update `to_json()` / `from_json()` to include the new field

### B. Worker job handler (sleap_rtc/worker/worker_class.py)

When `JOB_SUBMIT` contains a spec with `config_content`:
1. Write `config_content` to a temp file in the worker's temp directory
2. Set `config_paths = [temp_config_path]`
3. Continue with existing validation and execution flow
4. Clean up temp file after job completes or fails

### C. SLEAP dialog _run_remote_training() (dialog.py)

Replace the current implementation with:
1. Serialize config to YAML string (OmegaConf.to_yaml)
2. Get room_id, worker_id from RemoteTrainingWidget
3. Call run_presubmission_checks(slp_path, room_id, worker_id)
   - If cancelled or failed: show message, return to dialog
   - If passed: get path_mappings from result
4. Build TrainJobSpec with config_content and resolved paths
5. Close dialog
6. Call run_remote_training() with the spec

### D. run_remote_training() (sleap_rtc/gui/runners.py)

Update signature to accept a TrainJobSpec directly (or config_content + paths) instead of a config_path string. The runner passes the spec through to api.run_training().

### E. api.run_training() (sleap_rtc/api.py)

Update to accept config_content as an alternative to config_path. When config_content is provided, include it in the TrainJobSpec JSON sent over the datachannel instead of reading from a local file.

## Error Handling

### Presubmission errors (steps 2-4) → return to dialog

| Scenario | Message |
|----------|---------|
| JWT expired, login fails | "Login required. Please try again." |
| Worker unreachable | "Could not connect to worker. Check that the worker is running." |
| SLP not found on worker | Shown in PathResolutionDialog as missing path |
| Some videos missing | PathResolutionDialog with suggestions |
| All videos missing | PathResolutionDialog with hint about shared storage mount |
| User cancels resolution | Silent return to dialog |

### Post-submission errors (steps 5-6) → popup

| Scenario | Message |
|----------|---------|
| JOB_REJECTED | Error popup with worker's rejection reason |
| WebRTC drops during submit | "Connection lost. Try again." |
| JOB_FAILED during training | Error popup with failure details |

## Files Changed

| File | Change |
|------|--------|
| `sleap_rtc/jobs/spec.py` | Add `config_content` field to `TrainJobSpec` |
| `sleap_rtc/worker/worker_class.py` | Handle `config_content` in job handler |
| `sleap_rtc/gui/runners.py` | Accept spec/config_content instead of config_path |
| `sleap_rtc/api.py` | Accept config_content, include in datachannel spec |
| `scratch/.../dialog.py` | Wire presubmission flow into `_run_remote_training()` |
