## Why

When SLEAP trains a model locally, the GUI automatically runs inference on suggested frames
immediately after all pipeline models finish training, then merges predictions into the
labels project. The current sleap-rtc pipeline stops at training completion — users must
manually run inference afterward, which breaks the expected workflow and makes remote
training feel incomplete compared to local training.

## What Changes

- **Worker**: After all pipeline models train successfully, automatically trigger
  `sleap track` on the same labels file using all trained checkpoints, targeting suggested
  frames (falling back to all frames if none are suggested). Output written to
  `{labels_dir}/{labels_stem}.predictions.slp` on the shared filesystem.
- **Worker**: Stream inference progress (stdout JSON lines) over the RTC data channel as
  `INFERENCE_PROGRESS::` messages.
- **Worker**: Send `INFERENCE_BEGIN::` before inference starts and
  `INFERENCE_COMPLETE::{"predictions_path": "..."}` on success,
  `INFERENCE_FAILED::{"error": "..."}` on failure, or
  `INFERENCE_SKIPPED::{"reason": "..."}` when training was cancelled or incomplete.
- **Client (GUI)**: On `INFERENCE_BEGIN::`, open an `InferenceProgressDialog` matching
  SLEAP's local post-training inference window. Update progress on each
  `INFERENCE_PROGRESS::`. On `INFERENCE_COMPLETE::`, load predictions from shared
  filesystem path and merge into the open labels project.

## Design Decisions

- **Shared filesystem for predictions**: Predictions `.slp` files can be hundreds of MB.
  The worker writes to the shared filesystem and tells the client the path rather than
  transferring over RTC.
- **Suggested frames with all-frames fallback**: Matches SLEAP's local
  `--only_suggested_frames` behavior; falls back to all frames if the labels file has no
  suggested frames.
- **Single inference pass after full pipeline**: Inference runs once after ALL models
  complete, not after each individual model. Top-down pipelines require both centroid and
  centered-instance models together.
- **Reuse resolved labels path**: The worker uses the already-mapped worker-side labels
  path from training setup rather than re-applying `path_mappings` at inference time.
- **`JOB_COMPLETE::` timing**: `JOB_COMPLETE::` continues to fire after training completes
  (closing LossViewer). Inference messages follow immediately, matching SLEAP's two-phase
  UX (LossViewer closes → InferenceProgressDialog opens).

## Impact

- **New specs**:
  - `worker-post-training-inference`: Worker-side automatic inference after training
  - `gui-inference-progress`: Client-side `InferenceProgressDialog` and predictions merge
- **Modified specs**:
  - `worker-job-execution`: Add inference trigger and checkpoint path tracking
  - `worker-progress-reporting`: Add `INFERENCE_*` message forwarding

## Dependencies

- Builds on merged PR #49 (`fix-gui-lossviewer-and-path-resolution`)
- Requires `TrackJobSpec` and `build_track_command()` already implemented in
  `sleap_rtc/jobs/spec.py` and `sleap_rtc/jobs/builder.py`
- Requires shared filesystem between client and worker for predictions file access
- SLEAP `InferenceProgressDialog` in `sleap/gui/learning/runners.py` (design reference)
