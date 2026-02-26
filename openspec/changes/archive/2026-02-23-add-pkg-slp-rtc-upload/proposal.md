## Why

Users without access to a shared filesystem cannot train remotely with `.pkg.slp`
files (self-contained labels files with embedded video frames) because the existing
flow assumes the file is accessible on both client and worker. This change adds a
P2P upload path over the WebRTC data channel so those users can upload their
`.pkg.slp` to the worker directly from the SLP path resolution dialog before
training proceeds.

## What Changes

- **New capability — `pkg-slp-upload`**: Client-to-worker chunked file transfer
  over the existing RTC data channel, with destination directory selection, an
  optional `sleap-rtc-downloads/` subfolder, content-hash caching (skip re-upload
  if unchanged), and a progress bar.
- **Modified — `slp-video-resolution`**: The SLP Path Resolution dialog gains an
  "Upload file to worker..." option when the local file ends in `.pkg.slp`. On
  upload completion the Worker path field auto-fills and Continue is enabled.
  Video path resolution is skipped for `.pkg.slp` files because embedded frames
  need no external video files.
- **Modified — `worker-file-transfer`**: `FileManager` gains a receive-side handler
  for client-to-worker uploads: accepts `FILE_UPLOAD_START`, stores incoming chunks,
  sends progress ACKs, and finalises with the on-disk path.

## Impact

- Affected specs: `pkg-slp-upload` (new), `slp-video-resolution` (modified),
  `worker-file-transfer` (modified)
- Affected code:
  - `sleap_rtc/gui/widgets.py` — `SlpPathDialog`: new Upload button + progress bar
  - `sleap_rtc/gui/presubmission.py` — skip video-path check when file is pkg.slp
    with all-embedded videos
  - `sleap_rtc/worker/file_manager.py` — receive-side upload handler
  - `sleap_rtc/worker/worker_class.py` — route new upload protocol messages
  - `sleap_rtc/protocol.py` — new `FILE_UPLOAD_*` message constants
- No changes to the signaling server; all transfer is P2P over the existing data
  channel.
- The `.training_job.zip` offline export workflow is unaffected.
- Shared-filesystem users are unaffected; the upload option only surfaces when the
  worker cannot locate the file.
