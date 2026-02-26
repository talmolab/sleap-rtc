# gui-inference-progress Specification

## Purpose
TBD - created by archiving change add-post-training-inference. Update Purpose after archive.
## Requirements
### Requirement: InferenceProgressDialog

The client SHALL display an `InferenceProgressDialog` during post-training inference,
matching SLEAP's local post-training inference window.

#### Scenario: Dialog opens on INFERENCE_BEGIN

- **WHEN** client receives `INFERENCE_BEGIN::` message
- **THEN** client SHALL open `InferenceProgressDialog`
- **AND** dialog SHALL show status label, progress bar, and log area

#### Scenario: Dialog updates on INFERENCE_PROGRESS

- **WHEN** client receives `INFERENCE_PROGRESS::{json}` message
- **THEN** client SHALL update status label with frame count, FPS, and ETA
- **AND** update progress bar to `n_processed / n_total`

#### Scenario: Dialog closes and predictions merge on INFERENCE_COMPLETE

- **WHEN** client receives `INFERENCE_COMPLETE::{"predictions_path": "..."}` message
- **THEN** client SHALL load predictions from `predictions_path` on shared filesystem
- **AND** merge predictions into open labels project with `frame="replace_predictions"`
- **AND** show completion summary in dialog

#### Scenario: Dialog shows error on INFERENCE_FAILED

- **WHEN** client receives `INFERENCE_FAILED::{"error": "..."}` message
- **THEN** client SHALL display error message in dialog
- **AND** allow user to dismiss dialog

#### Scenario: Dialog silently closes on INFERENCE_SKIPPED

- **WHEN** client receives `INFERENCE_SKIPPED::{"reason": "..."}` message
- **THEN** client SHALL NOT open InferenceProgressDialog
- **AND** log the skip reason

### Requirement: Two-Phase UX Matching SLEAP Local Behavior

The client SHALL present training and inference as two visually distinct phases, matching
SLEAP's local training workflow.

#### Scenario: LossViewer closes before InferenceProgressDialog opens

- **WHEN** `JOB_COMPLETE::` is received (training done)
- **THEN** LossViewer SHALL close
- **AND** when `INFERENCE_BEGIN::` immediately follows
- **THEN** InferenceProgressDialog SHALL open as a new window

#### Scenario: Completion summary matches SLEAP format

- **WHEN** inference completes
- **THEN** dialog SHALL show:
  - Total frames processed
  - Frames with predictions found
  - Frames with no instances found

