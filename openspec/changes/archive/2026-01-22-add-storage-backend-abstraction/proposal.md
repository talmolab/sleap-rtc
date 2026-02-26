# Proposal: Add Storage Backend Abstraction

## Why

The current shared filesystem implementation (`add-shared-filesystem-transfer`) assumes a single shared storage root per machine, configured via `SHARED_STORAGE_ROOT`. This creates a critical limitation: **workers become user-specific rather than anonymous compute resources**.

**Current Problem:**
- Worker 1 configured with `SHARED_STORAGE_ROOT=/Volumes/talmo/sam`
- Worker 2 configured with `SHARED_STORAGE_ROOT=/Volumes/talmo/tom`
- When Sam submits a job, only Worker 1 can serve it effectively
- This defeats the purpose of a shared worker pool

**Additional Challenges:**
- Different machines mount the same storage at different paths (Mac: `/Volumes/talmo`, Linux: `/mnt/vast`, Run:AI container: `/home/jovyan/vast`)
- Users may have access to multiple storage backends (institutional VAST, personal Google Drive, local scratch)
- Workers should be fungible - any worker should serve any user's job

This change introduces **storage backend abstraction** where:
1. Workers configure base mount points for storage backends (not user-specific paths)
2. Clients specify which backend and user subdirectory to use in job requests
3. Workers advertise their available storage backends
4. Jobs are routed to workers with matching storage capabilities

## What Changes

- Add `StorageBackend` configuration class for defining named storage backends
- Add multi-backend configuration support in `sleap-rtc.toml` with `[storage.<name>]` sections
- **BREAKING**: Modify job protocol to include `storage_backend` and `user_subdir` fields
- Add worker capability advertisement for available storage backends
- Add path resolution layer: `backend_name + user_subdir + relative_path → absolute_path`
- Maintain backward compatibility with single `SHARED_STORAGE_ROOT` configuration
- Add validation that both client and worker have matching backend configurations

## Impact

- **Affected specs**: storage-backend (new), file-transfer (modified), worker (modified), client (modified)
- **Affected code**:
  - `sleap_rtc/config.py` - Add `StorageBackend` and `StorageConfig` classes
  - `sleap_rtc/filesystem.py` - Add `StorageResolver` for path translation
  - `sleap_rtc/worker/worker_class.py` - Add backend capability advertisement
  - `sleap_rtc/client/client_class.py` - Add backend selection in job requests
  - `sleap_rtc/protocol.py` - Add storage fields to job messages
- **Performance impact**: Minimal - path resolution is O(1) dictionary lookup
- **User experience**: Workers become anonymous compute resources; any worker can serve any user
- **Deployment**: Workers configure base mounts, users specify their subdirectory
- **Testing**: Requires tests with multiple mock storage backends
