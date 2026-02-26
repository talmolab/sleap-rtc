# Tasks: Add Storage Backend Abstraction

## Phase 1: Configuration Layer

### 1.1 Add StorageBackend dataclass
- [ ] Create `StorageBackend` dataclass in `sleap_rtc/config.py`
  - Fields: `name`, `base_path`, `type`, `description`
  - Method: `resolve_path(user_subdir, relative_path) -> Path`
  - Method: `validate_path(resolved_path) -> bool` (security check)
- [ ] Add unit tests for `StorageBackend`
  - Test path resolution with various inputs
  - Test security validation (path traversal prevention)

### 1.2 Add StorageConfig class
- [ ] Create `StorageConfig` class in `sleap_rtc/config.py`
  - Method: `from_toml(config_data) -> StorageConfig`
  - Method: `has_backend(name) -> bool`
  - Method: `resolve_path(backend, user_subdir, relative_path) -> Path`
  - Method: `list_backends() -> List[str]`
- [ ] Add backward compatibility for `SHARED_STORAGE_ROOT`
  - If env var set and no `[storage.*]` config, create `default` backend
- [ ] Add unit tests for `StorageConfig`
  - Test loading from TOML
  - Test backward compatibility with env var

### 1.3 Update TOML parser
- [ ] Add `[storage.<name>]` section parsing to config loader
- [ ] Update `config.example.toml` with storage backend examples
- [ ] Add validation for required fields (`base_path`)
- [ ] Add helpful error messages for misconfiguration

### 1.4 Add StorageResolver utility
- [ ] Create `StorageResolver` class in `sleap_rtc/filesystem.py`
  - Method: `resolve(backend, user_subdir, relative_path) -> Path`
  - Method: `to_relative(absolute_path, backend) -> Tuple[str, str, str]`
  - Integrate with existing `validate_path_in_root()` function
- [ ] Add unit tests for `StorageResolver`

**Validation**: Run `pytest tests/test_config.py tests/test_filesystem.py`

---

## Phase 2: Worker Capability Advertisement

### 2.1 Add storage backends to worker metadata
- [ ] Modify `RTCWorkerClient` to load `StorageConfig` on init
- [ ] Add `storage_backends` field to worker registration message
- [ ] Update worker logging to show configured backends on startup

### 2.2 Update signaling protocol (if needed)
- [ ] Review signaling server message handling
- [ ] Ensure worker metadata includes storage capabilities
- [ ] Document protocol changes

**Validation**: Start worker, verify logs show configured backends

---

## Phase 3: Job Protocol Changes

### 3.1 Add storage fields to job messages
- [ ] Update `protocol.py` with new message fields:
  - `storage_backend: str` (required if using shared storage)
  - `user_subdir: str` (required if using shared storage)
- [ ] Update `SHARED_INPUT_PATH` message format to include backend info
- [ ] Add backward compatibility: missing fields = legacy behavior

### 3.2 Update Client job submission
- [ ] Modify `RTCClient` to include storage fields in job requests
- [ ] Add `--storage-backend` CLI flag (optional, defaults to `default`)
- [ ] Add `--user-subdir` CLI flag (optional, can be inferred from config)
- [ ] Client validates it has the specified backend before sending job

### 3.3 Update Worker job handling
- [ ] Modify `RTCWorkerClient` to read storage fields from job request
- [ ] Resolve paths using `StorageConfig` and `StorageResolver`
- [ ] Return clear error if backend not available: fall back to RTC transfer
- [ ] Update path validation to use backend-specific base_path

### 3.4 Add fallback logic
- [ ] If worker lacks requested backend, send `BACKEND_NOT_AVAILABLE` message
- [ ] Client receives message, falls back to RTC transfer
- [ ] Log which transfer method is being used

**Validation**:
- Submit job with valid backend, verify shared storage used
- Submit job with invalid backend, verify RTC fallback works

---

## Phase 4: Job Routing (Optional Enhancement)

### 4.1 Add storage-aware job routing
- [ ] Client can specify `required_storage` in job request
- [ ] Room admin / signaling server routes to workers with matching backend
- [ ] If no matching worker available, return error or queue job

### 4.2 Add worker selection UI/feedback
- [ ] Client can query available workers and their backends
- [ ] User can see which workers can serve their job before submitting

**Validation**: Submit job requiring specific backend, verify correct worker receives it

---

## Phase 5: Documentation and Testing

### 5.1 Documentation
- [ ] Update README with storage backend configuration section
- [ ] Add examples for common setups:
  - SLURM cluster with NFS
  - Run:AI with VAST
  - Mixed environment (laptop + cloud workers)
- [ ] Document migration from `SHARED_STORAGE_ROOT` to new config

### 5.2 Integration tests
- [ ] Test multi-backend configuration
- [ ] Test path resolution across different "simulated" mount points
- [ ] Test fallback to RTC when backend missing
- [ ] Test security: path traversal attempts rejected

### 5.3 End-to-end testing
- [ ] Test on actual SLURM cluster (if available)
- [ ] Test on Run:AI environment
- [ ] Test mixed environment (Mac client, Linux worker)

**Validation**: All tests pass, documentation reviewed

---

## Dependencies

- Phase 1 must complete before Phase 2
- Phase 2 must complete before Phase 3
- Phase 3 must complete before Phase 4
- Phase 5 can run in parallel with Phase 3 and 4

## Parallelizable Work

Within Phase 1:
- Tasks 1.1 and 1.2 can be done in parallel
- Task 1.3 depends on 1.1 and 1.2
- Task 1.4 can be done in parallel with 1.3

Within Phase 3:
- Tasks 3.2 (Client) and 3.3 (Worker) can be done in parallel after 3.1

## Estimated Scope

- **Phase 1**: Core configuration - foundational, enables all other phases
- **Phase 2**: Worker capability - small change, prepares for routing
- **Phase 3**: Protocol changes - largest phase, delivers main value
- **Phase 4**: Job routing - optional enhancement, can defer
- **Phase 5**: Documentation - ongoing throughout

## Success Criteria

1. Workers can be configured with multiple storage backends
2. Jobs specify which backend and user subdirectory to use
3. Any worker with the required backend can serve any user's job
4. Backward compatibility with existing `SHARED_STORAGE_ROOT` config
5. Clear error messages when storage configuration is invalid
6. Fallback to RTC transfer when shared storage unavailable
