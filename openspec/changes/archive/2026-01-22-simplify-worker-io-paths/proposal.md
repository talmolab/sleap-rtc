# Proposal: Simplify Worker I/O Paths

## Why

The current proposals for shared filesystem transfer (`add-shared-filesystem-transfer` and `add-storage-backend-abstraction`) introduce significant complexity:

- Multiple named storage backends with different mount paths
- Path translation layers between logical names and physical paths
- Interactive selection flows for backends and user folders
- Complex configuration with `[storage.<name>]` sections

**This complexity is unnecessary for most users.** In practice:
- Users typically have ONE shared filesystem (NFS mount, cloud drive, etc.)
- Workers don't need to know about multiple backends - they just need to know where to read inputs and write outputs
- The user knows where their files are and can place them in the right location

**Simpler approach:** Each worker advertises:
1. An **input path** - where clients should place files for this worker
2. An **output path** - where the worker writes job results
3. A **filesystem label** - human-readable name for display (e.g., "vast", "gdrive")

The user sees these paths when selecting a worker and manually places their training package in the input folder. No automatic file copying, no complex path translation, no storage backend abstraction.

## What Changes

- Add simple `input_path`, `output_path`, and `filesystem` configuration to workers
- Workers advertise I/O paths in registration metadata
- Client displays I/O paths when listing available workers
- Client sends just the filename; worker resolves to `{input_path}/{filename}`
- Worker validates file exists before starting job
- Worker writes outputs to `{output_path}/jobs/{job_id}/`
- **SUPERSEDES**: `add-shared-filesystem-transfer` and `add-storage-backend-abstraction`
- **BREAKING**: Remove `SHARED_STORAGE_ROOT` configuration and auto-copy behavior entirely
- Remove complex storage backend configuration and path translation code
- Remove `SharedStorageConfig` class and related code from client
- Remove `--shared-storage-root` CLI flag from both client and worker
- Only two transfer modes: Worker I/O paths (new) OR RTC transfer (fallback)

## Impact

- **Affected specs**: worker-io (new), worker (modified), client (modified)
- **Affected code**:
  - `sleap_rtc/config.py` - Simplify to `WorkerIOConfig` with input/output paths
  - `sleap_rtc/worker/worker_class.py` - Advertise I/O paths, validate input exists
  - `sleap_rtc/worker/capabilities.py` - Add I/O path fields to metadata
  - `sleap_rtc/client/client_class.py` - Display I/O paths, send filename only
  - `sleap_rtc/protocol.py` - Simplify messages to `INPUT_FILE::` and path validation
  - `sleap_rtc/cli.py` - Add `--input-path` and `--output-path` flags to worker
  - Remove: Complex `StorageBackend`, `StorageConfig`, `StorageResolver` classes
- **Performance impact**: None - simpler code path
- **User experience**:
  - User sees worker I/O paths when selecting worker
  - User manually copies file to input path (drag-and-drop, `cp`, etc.)
  - User specifies filename in CLI, not full path
- **Deployment**: Workers configure two paths instead of complex storage backend sections
- **Testing**: Simpler test scenarios - just verify paths exist and files are found
