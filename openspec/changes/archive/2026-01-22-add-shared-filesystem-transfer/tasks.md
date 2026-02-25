# Implementation Tasks

## 1. Setup & Dependencies
- [ ] 1.1 Add fsspec to pyproject.toml dependencies
- [ ] 1.2 Run `uv sync` to install fsspec
- [ ] 1.3 Verify fsspec installation with import test

## 2. Core Infrastructure
- [ ] 2.1 Create `sleap_rtc/filesystem.py` module
- [ ] 2.2 Implement `FilesystemAdapter` class with fsspec wrapper
  - [ ] 2.2.1 `__init__` with protocol parameter
  - [ ] 2.2.2 `exists()` method
  - [ ] 2.2.3 `copy()` method
  - [ ] 2.2.4 `mkdir()` method
  - [ ] 2.2.5 `rm()` method
  - [ ] 2.2.6 `info()` method for file metadata
  - [ ] 2.2.7 `ls()` method for directory listing
  - [ ] 2.2.8 `from_path()` classmethod for auto-detection
- [ ] 2.3 Add path utility functions to `filesystem.py`
  - [ ] 2.3.1 `validate_path_in_root()` for security checks
  - [ ] 2.3.2 `to_relative_path()` helper
  - [ ] 2.3.3 `to_absolute_path()` helper

## 3. Configuration Layer
- [ ] 3.1 Add `SharedStorageConfig` class to `sleap_rtc/config.py`
  - [ ] 3.1.1 `KNOWN_MOUNT_POINTS` list for auto-detection
  - [ ] 3.1.2 `get_shared_storage_root()` static method
  - [ ] 3.1.3 Environment variable `SHARED_STORAGE_ROOT` support
  - [ ] 3.1.4 Auto-detection fallback logic
  - [ ] 3.1.5 Logging for mount point detection
- [ ] 3.2 Add `has_shared_storage()` helper to detect availability
- [ ] 3.3 Add configuration validation on initialization

## 4. Client Implementation
- [ ] 4.1 Modify `sleap_rtc/client/client_class.py`
  - [ ] 4.1.1 Add `shared_storage_root` attribute to RTCClient
  - [ ] 4.1.2 Add `fs_adapter` attribute (FilesystemAdapter instance)
  - [ ] 4.1.3 Detect shared storage in `__init__`
  - [ ] 4.1.4 Implement `send_file_via_shared_storage()` method
    - [ ] 4.1.4.1 Create unique job directory
    - [ ] 4.1.4.2 Copy file to shared storage
    - [ ] 4.1.4.3 Convert to relative path
    - [ ] 4.1.4.4 Send `SHARED_INPUT_PATH` message
    - [ ] 4.1.4.5 Send `SHARED_OUTPUT_PATH` message
  - [ ] 4.1.5 Add logic to choose transfer method (shared vs RTC)
  - [ ] 4.1.6 Handle `PATH_VALIDATED` response messages
  - [ ] 4.1.7 Handle `PATH_ERROR` and fallback to RTC transfer
  - [ ] 4.1.8 Update `on_message()` to handle shared storage completion
- [ ] 4.2 Add CLI flag `--shared-storage-root` to `sleap_rtc/cli.py`
- [ ] 4.3 Add logging for transfer method selection

## 5. Worker Implementation
- [ ] 5.1 Modify `sleap_rtc/worker/worker_class.py`
  - [ ] 5.1.1 Add `shared_storage_root` attribute to RTCWorkerClient
  - [ ] 5.1.2 Add `fs_adapter` attribute (FilesystemAdapter instance)
  - [ ] 5.1.3 Detect shared storage in `__init__`
  - [ ] 5.1.4 Add handler for `SHARED_INPUT_PATH` message
    - [ ] 5.1.4.1 Receive relative path
    - [ ] 5.1.4.2 Resolve to absolute path
    - [ ] 5.1.4.3 Validate path exists
    - [ ] 5.1.4.4 Validate path within shared root (security)
    - [ ] 5.1.4.5 Send `PATH_VALIDATED::input` or `PATH_ERROR`
  - [ ] 5.1.5 Add handler for `SHARED_OUTPUT_PATH` message
    - [ ] 5.1.5.1 Receive relative path
    - [ ] 5.1.5.2 Resolve to absolute path
    - [ ] 5.1.5.3 Create output directory
    - [ ] 5.1.5.4 Send `PATH_VALIDATED::output`
  - [ ] 5.1.6 Implement `process_shared_storage_job()` method
    - [ ] 5.1.6.1 Read input file directly from shared path
    - [ ] 5.1.6.2 Extract/process as needed
    - [ ] 5.1.6.3 Write results to shared output path
    - [ ] 5.1.6.4 Send `JOB_COMPLETE` with relative output path
  - [ ] 5.1.7 Update `on_message()` to route shared storage messages
  - [ ] 5.1.8 Add logging for path validation

## 6. Message Protocol
- [ ] 6.1 Document new message types in code comments
- [ ] 6.2 Add message type constants
  - [ ] 6.2.1 `SHARED_INPUT_PATH`
  - [ ] 6.2.2 `SHARED_OUTPUT_PATH`
  - [ ] 6.2.3 `PATH_VALIDATED`
  - [ ] 6.2.4 `PATH_ERROR`
- [ ] 6.3 Ensure backward compatibility with existing RTC transfer messages

## 7. Error Handling & Validation
- [ ] 7.1 Add path traversal validation
- [ ] 7.2 Add file permission checks
- [ ] 7.3 Add disk space checks before copying large files
- [ ] 7.4 Add timeout handling for file operations
- [ ] 7.5 Add clear error messages for common failures
  - [ ] 7.5.1 Mount point not found
  - [ ] 7.5.2 Permission denied
  - [ ] 7.5.3 Disk space exhausted
  - [ ] 7.5.4 File not found on shared storage

## 8. Testing
- [ ] 8.1 Unit tests for `FilesystemAdapter`
  - [ ] 8.1.1 Test `exists()` method
  - [ ] 8.1.2 Test `copy()` method
  - [ ] 8.1.3 Test `mkdir()` method
  - [ ] 8.1.4 Test path validation
- [ ] 8.2 Unit tests for `SharedStorageConfig`
  - [ ] 8.2.1 Test auto-detection logic
  - [ ] 8.2.2 Test environment variable override
  - [ ] 8.2.3 Test fallback behavior
- [ ] 8.3 Unit tests for path utilities
  - [ ] 8.3.1 Test relative path conversion
  - [ ] 8.3.2 Test path validation (security)
  - [ ] 8.3.3 Test cross-platform path handling
- [ ] 8.4 Integration tests
  - [ ] 8.4.1 Test Client writing to shared storage
  - [ ] 8.4.2 Test Worker reading from shared storage
  - [ ] 8.4.3 Test path translation (different mount points)
  - [ ] 8.4.4 Test fallback to RTC transfer when shared storage unavailable
  - [ ] 8.4.5 Test with Docker volumes (local testing)
  - [ ] 8.4.6 Test error cases (invalid paths, permissions)
- [ ] 8.5 Create test utility script for validating mount points

## 9. Documentation
- [ ] 9.1 Add docstrings to all new classes and methods (Google-style)
- [ ] 9.2 Update DEVELOPMENT.md with shared storage setup instructions
- [ ] 9.3 Add example usage in code comments
- [ ] 9.4 Document mount point configuration for different platforms
  - [ ] 9.4.1 Vast.ai configuration
  - [ ] 9.4.2 RunAI configuration
  - [ ] 9.4.3 Local Docker development
- [ ] 9.5 Add troubleshooting guide for common issues
- [ ] 9.6 Update README.md with performance improvements

## 10. Validation & Cleanup
- [ ] 10.1 Run formatter (Black) on all modified files
- [ ] 10.2 Run linter (Ruff) and fix issues
- [ ] 10.3 Verify type hints are complete
- [ ] 10.4 Test on actual Vast.ai environment
- [ ] 10.5 Test on RunAI environment (if available)
- [ ] 10.6 Verify backward compatibility with RTC transfer
- [ ] 10.7 Performance testing: Compare transfer times (RTC vs shared storage)
- [ ] 10.8 Update all task checkboxes to `[x]` when complete
