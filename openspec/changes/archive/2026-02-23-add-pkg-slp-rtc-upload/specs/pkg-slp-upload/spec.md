## ADDED Requirements

### Requirement: Content-Hash Pre-Check

Before transferring a `.pkg.slp` file the client SHALL send a content-hash check
message so the worker can skip the upload when it already holds an identical file.

#### Scenario: Worker has matching cached file
- **WHEN** client sends `FILE_UPLOAD_CHECK::{sha256}::{filename}`
- **AND** worker finds a file on disk whose SHA-256 matches `{sha256}`
- **THEN** worker replies `FILE_UPLOAD_CACHE_HIT::{absolute_path}`
- **AND** the upload dialog marks transfer as complete immediately
- **AND** the Worker path field auto-fills with `{absolute_path}`

#### Scenario: Worker has no matching cached file
- **WHEN** client sends `FILE_UPLOAD_CHECK::{sha256}::{filename}`
- **AND** no matching file is found
- **THEN** worker replies `FILE_UPLOAD_READY`
- **AND** client proceeds to send `FILE_UPLOAD_START`

### Requirement: Chunked Client-to-Worker Transfer

The client SHALL stream a `.pkg.slp` file to the worker in chunks over the
existing RTC data channel using the `FILE_UPLOAD_*` message namespace.

#### Scenario: Successful upload
- **WHEN** client sends `FILE_UPLOAD_START::{filename}::{total_bytes}::{dest_dir}::{create_subdir}`
- **AND** worker acknowledges with `FILE_UPLOAD_READY`
- **AND** client sends binary chunks followed by `FILE_UPLOAD_END`
- **THEN** worker writes the file to `{dest_dir}/{filename}` (or
  `{dest_dir}/sleap-rtc-downloads/{filename}` when `create_subdir` is `1`)
- **AND** worker sends `FILE_UPLOAD_COMPLETE::{absolute_path}`
- **AND** the Worker path field in the dialog auto-fills with `{absolute_path}`

#### Scenario: Flow control
- **WHEN** the RTC data channel `bufferedAmount` exceeds 16 MB
- **THEN** the client pauses sending chunks until `bufferedAmount` drops below 16 MB
- **AND** transfer resumes automatically without data loss

#### Scenario: Worker write error
- **WHEN** the worker cannot write a chunk (disk full, permission denied, etc.)
- **THEN** worker sends `FILE_UPLOAD_ERROR::{reason}`
- **AND** the upload dialog displays the error
- **AND** any partial file on worker disk is deleted

### Requirement: Upload Time Warning

Before beginning a transfer the dialog SHALL display an estimated upload duration
based on file size so the user can decide whether to proceed.

#### Scenario: Warning shown before upload starts
- **WHEN** the user confirms a destination directory and clicks Upload
- **AND** the content-hash check returns `FILE_UPLOAD_READY` (no cache hit)
- **THEN** the dialog SHALL display an estimated time in the form
  "Estimated upload time: ~N min (XGB at ~10 Mbps)"
- **AND** the user SHALL be able to cancel before transfer begins

#### Scenario: Estimate tiers
- **WHEN** file size is under 500 MB
- **THEN** estimated label is "~N min"
- **WHEN** file size is 500 MB – 2 GB
- **THEN** estimated label is "~N min – this may take a while"
- **WHEN** file size is over 2 GB
- **THEN** estimated label is "~N min – consider using a shared filesystem if available"

#### Scenario: Cache hit skips warning
- **WHEN** the content-hash check returns `FILE_UPLOAD_CACHE_HIT`
- **THEN** no time warning is shown
- **AND** the Worker path field auto-fills immediately

### Requirement: Upload Progress Reporting

The worker SHALL send periodic progress messages back to the client during upload
so the user can track transfer status.

#### Scenario: Progress updates during transfer
- **WHEN** worker receives chunks from client
- **THEN** worker sends `FILE_UPLOAD_PROGRESS::{bytes_received}::{total_bytes}`
  after each chunk or at most every 500 ms, whichever comes first
- **AND** the upload dialog displays a progress bar reflecting the ratio

#### Scenario: Upload complete feedback
- **WHEN** worker receives `FILE_UPLOAD_END` and finalises the file
- **THEN** worker sends `FILE_UPLOAD_COMPLETE::{absolute_path}`
- **AND** the progress bar shows 100 %

### Requirement: Destination Directory Selection

The user SHALL be able to choose any configured worker mount as the upload
destination, with an option to create a dedicated subfolder.

#### Scenario: User selects destination directory
- **WHEN** the upload dialog is shown
- **THEN** the user can browse the worker filesystem using the existing
  `RemoteFileBrowser` to pick a destination directory
- **AND** the chosen path must resolve to within a configured worker mount

#### Scenario: Create sleap-rtc-downloads subfolder
- **WHEN** the user checks "Create sleap-rtc-downloads/ subfolder"
- **AND** the destination is `/vast/data`
- **THEN** the final upload path is `/vast/data/sleap-rtc-downloads/{filename}`
- **AND** the worker creates `/vast/data/sleap-rtc-downloads/` if it does not exist

#### Scenario: Destination outside configured mounts
- **WHEN** the chosen destination resolves outside all configured worker mounts
- **THEN** the worker rejects the upload with `FILE_UPLOAD_ERROR::Destination outside configured mounts`
- **AND** the user is prompted to select a different directory
