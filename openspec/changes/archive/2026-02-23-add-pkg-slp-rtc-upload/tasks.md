## 1. Protocol

- [x] 1.1 Add `FILE_UPLOAD_CHECK`, `FILE_UPLOAD_START`, `FILE_UPLOAD_END`,
      `FILE_UPLOAD_READY`, `FILE_UPLOAD_PROGRESS`, `FILE_UPLOAD_COMPLETE`,
      `FILE_UPLOAD_CACHE_HIT`, `FILE_UPLOAD_ERROR` constants to `protocol.py`

## 2. Worker — Receive Side

- [x] 2.1 Add `receive_upload()` coroutine to `FileManager`: handles
      `FILE_UPLOAD_START` → chunk writes → `FILE_UPLOAD_END`, sends
      `FILE_UPLOAD_PROGRESS` and `FILE_UPLOAD_COMPLETE` / `FILE_UPLOAD_ERROR`
- [x] 2.2 Add `check_upload_cache(sha256, filename)` method to `FileManager`:
      returns cached path or `None`; updates index on successful upload
- [x] 2.3 Route `FILE_UPLOAD_CHECK`, `FILE_UPLOAD_START`, binary-chunk, and
      `FILE_UPLOAD_END` messages in `worker_class.py` to `FileManager`
- [x] 2.4 Add destination-mount validation in `receive_upload()` (reuse existing
      mount-bounds check pattern)
- [x] 2.5 Write tests for `receive_upload()` and `check_upload_cache()` covering
      success, cache hit, disk error, and destination-outside-mounts cases

## 3. Client — Send Side

- [x] 3.1 Add `upload_file(channel, file_path, dest_dir, create_subdir, on_progress)`
      coroutine to client-side utilities: SHA-256 pre-check → chunked send →
      await `FILE_UPLOAD_COMPLETE` or `FILE_UPLOAD_ERROR`
- [x] 3.2 Write tests for `upload_file()` covering success, cache hit, and error
      handling

## 4. GUI — SlpPathDialog

- [x] 4.1 Detect `.pkg.slp` extension in `SlpPathDialog.__init__` and add
      "Upload file to worker..." button when true
- [x] 4.2 Clicking "Upload file to worker..." opens a destination-picker using
      `RemoteFileBrowser` + "Create sleap-rtc-downloads/ subfolder" checkbox
- [x] 4.3 After destination confirm and a `FILE_UPLOAD_READY` response, compute
      estimated duration (file_size / 10 Mbps) and display a tiered warning:
      under 500 MB → "~N min"; 500 MB–2 GB → "~N min — this may take a while";
      over 2 GB → "~N min — consider using a shared filesystem if available";
      user can cancel before transfer starts
- [x] 4.4 Start `upload_file()` in background after user confirms and show
      progress bar in the dialog
- [x] 4.5 On `FILE_UPLOAD_COMPLETE`, auto-fill the Worker path field and enable
      Continue
- [x] 4.6 On `FILE_UPLOAD_ERROR`, show the error message and re-enable the Upload
      button so the user can retry

## 5. Presubmission — Skip Video Resolution for Fully-Embedded pkg.slp

- [ ] 5.1 In `presubmission.check_video_paths`, after receiving the worker's
      video-accessibility response, check `missing == 0 and embedded > 0`; if so,
      return success without showing `PathResolutionDialog`
- [ ] 5.2 Write tests for the skip-resolution path

## 6. Dev Environment — sleap-nn DDP Fix

> **Note:** Unrelated to the upload feature but tracked here for visibility.
> `scratch/sleap-nn` is pinned to the `v0.1.0` tag, which predates the DDP
> synchronization fix merged in commit `699a8e2e` on `main`. The fix resolves
> training freezes/deadlocks after each epoch during multi-GPU DDP runs.

- [ ] 6.1 Checkout `main` in `scratch/sleap-nn` (or cherry-pick `699a8e2e` onto a
      local branch based on `v0.1.0`) so the DDP callback fix is active
- [ ] 6.2 Verify `sleap_nn/training/callbacks.py` contains the `reduce_boolean_decision`
      / barrier synchronization changes from the DDP fix commit
- [ ] 6.3 Run a quick multi-GPU smoke test to confirm training no longer freezes
      after the first epoch

## 7. Validation

- [ ] 7.1 Run `openspec validate add-pkg-slp-rtc-upload --strict` and resolve all
      issues
- [ ] 7.2 Manual end-to-end smoke test: upload a small `.pkg.slp` to a worker,
      verify the path auto-fills, and training submits successfully
