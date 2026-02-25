## ADDED Requirements

### Requirement: Client-to-Worker Upload Receive Handler

The `FileManager` SHALL accept incoming file uploads from clients via the RTC data
channel, writing chunks to disk and reporting progress.

#### Scenario: Start upload session
- **WHEN** worker receives `FILE_UPLOAD_START::{filename}::{total_bytes}::{dest_dir}::{create_subdir}`
- **AND** `dest_dir` resolves within a configured mount
- **THEN** worker creates the destination directory (and `sleap-rtc-downloads/`
  subfolder if `create_subdir` is `1`)
- **AND** opens a write handle for the incoming file
- **AND** replies `FILE_UPLOAD_READY`

#### Scenario: Receive and write chunks
- **WHEN** worker receives binary data chunks during an active upload session
- **THEN** worker appends each chunk to the open write handle
- **AND** sends `FILE_UPLOAD_PROGRESS::{bytes_received}::{total_bytes}` at most
  every 500 ms

#### Scenario: Finalise upload
- **WHEN** worker receives `FILE_UPLOAD_END`
- **THEN** worker closes the write handle and flushes to disk
- **AND** verifies the written file size matches `{total_bytes}`
- **AND** sends `FILE_UPLOAD_COMPLETE::{absolute_path}`

#### Scenario: Reject destination outside mounts
- **WHEN** worker receives `FILE_UPLOAD_START` with a `dest_dir` that resolves
  outside all configured mounts
- **THEN** worker sends `FILE_UPLOAD_ERROR::Destination outside configured mounts`
- **AND** no file is written to disk

#### Scenario: Disk write failure
- **WHEN** an I/O error occurs while writing a chunk
- **THEN** worker sends `FILE_UPLOAD_ERROR::{reason}`
- **AND** worker deletes the partial file

### Requirement: Upload Cache Index

The `FileManager` SHALL maintain an in-memory index of uploaded files keyed by
SHA-256 so repeat uploads of unchanged files can be skipped.

#### Scenario: Cache hit
- **WHEN** worker receives `FILE_UPLOAD_CHECK::{sha256}::{filename}`
- **AND** the index contains an entry for `{sha256}` pointing to a file that
  still exists on disk
- **THEN** worker replies `FILE_UPLOAD_CACHE_HIT::{absolute_path}`

#### Scenario: Cache miss
- **WHEN** worker receives `FILE_UPLOAD_CHECK::{sha256}::{filename}`
- **AND** no matching entry exists in the index (or the cached file no longer
  exists on disk)
- **THEN** worker replies `FILE_UPLOAD_READY`

#### Scenario: Index updated after successful upload
- **WHEN** an upload completes successfully
- **THEN** the SHA-256 and absolute path are stored in the index
- **AND** subsequent checks for the same hash hit the cache
