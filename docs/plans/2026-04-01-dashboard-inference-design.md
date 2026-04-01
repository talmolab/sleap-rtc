# Dashboard Inference Job Design

**Date:** 2026-04-01
**Branch:** TBD
**Goal:** Enable inference (track) job submission from the dashboard, reusing existing worker infrastructure.

---

## Job Type Selection (Step 1)

Add a Training/Inference toggle at the top of Step 1, before the worker list.

- Default: "Training" (current behavior)
- When "Inference" is selected, Step 2 (config upload) is skipped — Next goes directly to file selection
- Step indicator changes: Training shows 3 steps, Inference shows 2 steps
- State: `_sjJobType = 'train' | 'track'`

## Inference File Selection (Step 2 for inference)

Combined page with two sections:

**Model Checkpoints:**
- "Browse Worker Filesystem" button opens file browser in directory mode
- Selected models appear as cards with remove buttons
- "+ Add Another Model" mini browse button
- At least one model required

**Data File (.slp):**
- Read-only text input with browse button
- File browser filtered to `.slp` files
- Required

Both reuse the existing SSE relay file browser.

State: `_sjInferenceModelPaths = []`, `_sjInferenceDataPath = ''`

## Job Submission

`submitJob()` branches on `_sjJobType`:

```javascript
if (this._sjJobType === 'track') {
    config = {
        type: 'track',
        data_path: this._sjInferenceDataPath,
        model_paths: this._sjInferenceModelPaths,
    };
} else {
    config = {
        type: 'train',
        config_contents: this._sjConfigContents,
        // ...existing training fields
    };
}
```

Rest of submission flow identical: `apiJobSubmit()`, SSE, activeJobs.

## Progress View

Reuses same status view with inference-specific behavior:
- Hide epoch section and training metrics
- Status label: "Running inference..."
- No Stop Early button (single pass, nothing to continue to)
- Cancel button sends `mode: "cancel"` (same mechanism)
- On complete: show output prediction file path
- Worker logs stream as usual
- activeJobs `modelType` set to `"inference"`

## Files Changed

| File | Change |
|------|--------|
| `dashboard/app.js` | Job type toggle state, inference file selection, branched submitJob(), inference progress handling |
| `dashboard/index.html` | Job type toggle in Step 1, inference file selection view |
| `dashboard/styles.css` | Job type toggle styles, model card reuse |

## No Worker Changes Needed

The worker already handles `TrackJobSpec`:
- `handle_job_submit()` routes to `execute_from_spec()` for track jobs
- `build_track_command()` builds `sleap-nn track` CLI
- `RelayChannel` handles `INFERENCE_BEGIN`, `INFERENCE_COMPLETE`, `INFERENCE_FAILED`
- `validate_track_spec()` validates all fields
