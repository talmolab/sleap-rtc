# Tasks: Simplify Worker I/O Paths

## Phase 1: Configuration & Worker Advertisement

### 1.1 Add Worker I/O Configuration
- [x] Add `WorkerIOConfig` dataclass to `config.py` with fields:
  - `input_path: Path` - Where worker reads input files
  - `output_path: Path` - Where worker writes job outputs
  - `filesystem: str` - Human-readable label (e.g., "vast", "gdrive", "local")
- [x] Add `[worker.io]` section parsing in TOML config
- [x] Add validation that paths exist and are accessible
- [x] Add CLI flags `--input-path` and `--output-path` to worker command
- [x] **Validation**: Config loads correctly, paths are validated on startup

### 1.2 Update Worker Capabilities
- [x] Add `io_config` field to `WorkerCapabilities`
- [x] Update `to_metadata_dict()` to include I/O paths
- [x] Log I/O paths on worker startup
- [x] **Validation**: Worker registration includes I/O paths in metadata

### 1.3 Update Worker Registration
- [x] Modify worker registration message to include I/O paths
- [x] Ensure paths are sent as strings (for JSON serialization)
- [x] **Validation**: Signaling server receives and stores I/O path metadata

## Phase 2: Client Display & Selection

### 2.1 Display I/O Paths in Worker List
- [x] Update `_prompt_worker_selection()` to display I/O paths
- [x] Show filesystem label prominently
- [x] Format paths clearly with labels:
  ```
  1. worker-abc123
     GPU: NVIDIA A100 (40GB)
     Filesystem: vast
     Input:  /mnt/vast/inputs    <- Place your files here
     Output: /mnt/vast/outputs
  ```
- [x] **Validation**: User can see I/O paths when selecting worker

### 2.2 Update Auto-Select Display
- [x] Log selected worker's I/O paths after auto-selection
- [x] Store `target_worker_io_paths` for use in `on_channel_open()`
- [x] **Validation**: Auto-selected worker I/O paths are visible in logs

## Phase 3: Job Protocol Changes

### 3.1 Simplify Protocol Messages
- [x] Add `MSG_INPUT_FILE = "INPUT_FILE"` message type
- [x] Add `MSG_FILE_EXISTS = "FILE_EXISTS"` response
- [x] Add `MSG_FILE_NOT_FOUND = "FILE_NOT_FOUND"` response
- [x] Add `MSG_JOB_OUTPUT_PATH = "JOB_OUTPUT_PATH"` message type
- [x] Mark complex storage backend messages as deprecated
- [x] **Validation**: New messages parse correctly

### 3.2 Update Client Job Submission
- [x] Modify `on_channel_open()` to check if worker has I/O paths
- [x] If worker has I/O paths:
  - Extract filename from `--pkg_path`
  - Send `INPUT_FILE::{filename}` instead of transferring file
  - Wait for `FILE_EXISTS` or `FILE_NOT_FOUND` response
- [x] If worker has no I/O paths: fall back to RTC transfer
- [x] **Validation**: Client sends filename, not file data, when I/O paths available

### 3.3 Update Worker File Handling
- [x] Add handler for `INPUT_FILE::` message
- [x] Resolve full path: `{input_path}/{filename}`
- [x] Validate file exists and is readable
- [x] Validate filename for security (no path traversal)
- [x] Send `FILE_EXISTS::` or `FILE_NOT_FOUND::{reason}`
- [x] Store resolved path for job execution
- [x] **Validation**: Worker correctly locates files in input path

## Phase 4: Job Execution & Output

### 4.1 Update Job Output Directory
- [x] Create job output structure: `{output_path}/jobs/{job_id}/`
- [ ] Subdirectories: `models/`, `logs/`
- [x] Update `JobExecutor` to use configured output path (`process_io_paths_job()`)
- [ ] **Validation**: Job outputs appear in correct location

### 4.2 Update Job Completion Message
- [x] Include output path in job completion message (`MSG_JOB_OUTPUT_PATH`)
- [x] Client logs where to find results
- [ ] **Validation**: User knows where to find job outputs

## Phase 5: Remove Legacy Shared Storage Code

### 5.1 Remove SHARED_STORAGE_ROOT from Worker
- [ ] Remove `shared_storage_root` parameter from `RTCWorkerClient.__init__()`
- [ ] Remove `SHARED_STORAGE_ROOT` environment variable handling
- [ ] Remove `get_shared_storage_root()` function from `config.py`
- [ ] Remove shared storage path validation on worker startup
- [ ] Remove `SHARED_INPUT_PATH::` and `SHARED_OUTPUT_PATH::` message handlers
- [ ] **Validation**: Worker starts without shared storage config

### 5.2 Remove SHARED_STORAGE_ROOT from Client
- [ ] Remove `shared_storage_root` parameter from `RTCClient.__init__()`
- [ ] Remove `--shared-storage-root` CLI flag from `client-train` command
- [ ] Remove `--shared-storage-root` CLI flag from `client-track` command
- [ ] Remove `send_file_via_shared_storage()` method
- [ ] Remove auto-copy logic from `on_channel_open()`
- [ ] Remove `SharedStorageConfig` class if exists
- [ ] **Validation**: Client works without shared storage config

### 5.3 Remove Complex Storage Backend Code
- [ ] Remove `StorageBackend` class from `config.py`
- [ ] Remove `StorageConfig` class from `config.py`
- [ ] Remove `StorageResolver` from `filesystem.py` (if exists)
- [ ] Remove `[storage.<name>]` config parsing
- [ ] Remove interactive storage selection methods from client
- [ ] Remove `MSG_STORAGE_BACKEND`, `MSG_USER_SUBDIR`, `MSG_BACKEND_NOT_AVAILABLE` from protocol
- [ ] **Validation**: Code compiles, no references to removed classes

### 5.4 Update Configuration Files
- [ ] Update `config.example.toml` with new `[worker.io]` format only
- [ ] Remove `[storage.*]` sections from example config
- [ ] Remove `SHARED_STORAGE_ROOT` references from documentation
- [ ] **Validation**: Example config is valid TOML

## Phase 6: Documentation & CLI

### 6.1 Update CLI Help
- [ ] Update worker `--help` to document I/O path flags
- [ ] Update client-train `--help` to explain filename-only `--pkg_path`
- [ ] Remove `--storage-backend` and `--user-folder` flags if present
- [ ] **Validation**: CLI help is accurate and clear

### 6.2 Update Documentation
- [ ] Update `config.example.toml` with worker I/O example
- [ ] Add comments explaining the workflow
- [ ] **Validation**: Example config is valid TOML

## Phase 7: Testing

### 7.1 Unit Tests
- [ ] Test `WorkerIOConfig` validation (paths exist, permissions)
- [ ] Test `WorkerCapabilities` includes I/O paths
- [ ] Test protocol message parsing for new message types
- [ ] Test removal of legacy shared storage code doesn't break imports
- [ ] **Validation**: All unit tests pass

### 7.2 Integration Tests
- [ ] Test worker advertises I/O paths in registration
- [ ] Test client displays I/O paths in worker selection
- [ ] Test job submission with filename resolves correctly
- [ ] Test fallback to RTC when no I/O paths configured
- [ ] Test that old `SHARED_STORAGE_ROOT` env var is ignored
- [ ] **Validation**: Integration tests pass

## Dependencies

- Phase 2 depends on Phase 1 (worker must advertise before client can display)
- Phase 3 depends on Phase 1 (worker must have config before handling messages)
- Phase 4 depends on Phase 3 (job execution follows file validation)
- Phase 5 (removal) should happen AFTER Phases 1-4 are working
- Phase 6 can run in parallel with Phase 5
- Phase 7 should run after each phase for validation

## Parallelizable Work

- 1.1 (config) and 1.2 (capabilities) can be done in parallel
- 3.2 (client) and 3.3 (worker) can be done in parallel after 3.1
- 5.1 (cleanup) and 5.2/5.3 (docs) can be done in parallel
