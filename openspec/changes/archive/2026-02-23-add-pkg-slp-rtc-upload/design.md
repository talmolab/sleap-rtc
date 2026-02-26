## Context

`.pkg.slp` files embed video frames directly in HDF5, so they are self-contained
for training — no external video files needed. For users without shared filesystem
access, the only way to get the file onto the worker is to transfer it explicitly.

The WebRTC data channel is already used for chunked worker-to-client transfers
(`FileManager.send_file`). Reversing this direction for client-to-worker gives us
P2P transfer with no infrastructure cost and no changes to the signaling server.

Typical sizes: 100 MB–5 GB. At a sustained 10 Mbps data channel throughput, that
is 1–70 minutes. A progress bar and content-hash caching (skip re-upload if file
unchanged) are essential for usability.

## Goals / Non-Goals

- **Goals**
  - Transfer a single `.pkg.slp` from client to worker over the RTC data channel
  - Let the user choose a destination directory on the worker (any configured mount)
  - Optionally create a `sleap-rtc-downloads/` subfolder to avoid clutter
  - Show a progress bar during transfer
  - Skip the upload if the worker already has an identical file (content hash)
  - Auto-fill the Worker path field in the dialog after upload
  - Skip the video-path resolution step for `.pkg.slp` with all-embedded videos
- **Non-Goals**
  - Resume interrupted transfers (v1)
  - Uploading non-`.pkg.slp` files (e.g. raw video)
  - Relay server or cloud storage intermediary
  - Parallel / multi-channel transfer

## Decisions

### Decision: Reuse existing chunked-transfer pattern in reverse

The existing `FILE_META::{name}:{size}:{hint}` + binary chunks + `END_OF_FILE`
protocol runs worker→client. We introduce a mirror `FILE_UPLOAD_*` namespace for
the client→worker direction so both paths coexist without ambiguity.

Alternative: reuse the same `FILE_META` prefix for both directions.
Rejected — message direction would be ambiguous in logs and routing.

### Decision: Content-hash check before upload

Before streaming bytes, the client sends `FILE_UPLOAD_CHECK::{sha256}::{filename}`.
If the worker already has that hash on disk it replies `FILE_UPLOAD_CACHE_HIT::{path}`
and the dialog auto-fills without any transfer. Otherwise it replies
`FILE_UPLOAD_READY`.

This makes repeated runs with the same file (e.g., tuning hyperparameters) instant.

### Decision: Destination directory + optional subfolder

User browses the worker filesystem (existing `RemoteFileBrowser`) to pick a
directory, then checks "Create `sleap-rtc-downloads/` subfolder". This keeps
uploaded files organised without forcing a global config change on the worker.
The worker creates the subdirectory if the flag is set and it does not exist.

Alternative: admin-configured `upload_dir` in `config.toml` (transparent to user).
Not mutually exclusive — can be added later as a default that pre-fills the picker.

### Decision: Skip video-path resolution for pkg.slp with all-embedded videos

`FileManager.check_video_accessibility` already counts embedded videos separately
and does not flag them as missing. When the response shows `missing == 0` the
presubmission flow already continues. No code change needed for that path; the
only fix required is ensuring the upload completes before the video-check message
is sent.

## Protocol Messages

```
# Client → Worker
FILE_UPLOAD_CHECK::{sha256}::{filename}
FILE_UPLOAD_START::{filename}::{total_bytes}::{dest_dir}::{create_subdir}
<binary chunk>  ...repeated...
FILE_UPLOAD_END

# Worker → Client
FILE_UPLOAD_CACHE_HIT::{absolute_path}
FILE_UPLOAD_READY
FILE_UPLOAD_PROGRESS::{bytes_received}::{total_bytes}
FILE_UPLOAD_COMPLETE::{absolute_path}
FILE_UPLOAD_ERROR::{reason}
```

`dest_dir` is an absolute worker-side path selected by the user.
`create_subdir` is `1` or `0`.

## Risks / Trade-offs

- **Large file on slow connection**: 5 GB at 5 Mbps ≈ 2+ hours. No workaround in
  v1 except telling users to use a shared filesystem when possible. A future v2
  could add resume (byte-range restart).
- **Worker disk space**: worker admin must ensure `dest_dir` has capacity. No
  pre-flight disk-space check in v1 — `FILE_UPLOAD_ERROR` covers this at write
  time.
- **Re-upload on label change**: adding new labels to a `.pkg.slp` changes the
  hash, so re-upload is required. Mitigated by content-hash caching for
  unchanged files.

## Open Questions

- Should the worker auto-clean `sleap-rtc-downloads/` older than N days? Deferred
  to a follow-up; not needed for v1.
