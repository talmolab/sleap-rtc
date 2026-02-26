# Implementation Tasks

## 1. Extract Worker Capabilities Module
- [ ] 1.1 Create `sleap_rtc/worker/capabilities.py` with `WorkerCapabilities` class
- [ ] 1.2 Move GPU detection methods (`_detect_gpu_memory`, `_detect_gpu_model`, `_detect_cuda_version`)
- [ ] 1.3 Move job compatibility methods (`_check_job_compatibility`, `_estimate_job_duration`)
- [ ] 1.4 Move resource query methods (`_get_gpu_utilization`, `_get_available_memory`)
- [ ] 1.5 Add docstrings (Google-style) and type hints
- [ ] 1.6 Update `RTCWorkerClient.__init__` to instantiate `WorkerCapabilities`

## 2. Extract Job Executor Module
- [ ] 2.1 Create `sleap_rtc/worker/job_executor.py` with `JobExecutor` class
- [ ] 2.2 Move script parsing methods (`parse_training_script`, `parse_track_script`)
- [ ] 2.3 Move training execution (`run_all_training_jobs` and helper methods)
- [ ] 2.4 Move inference execution (`run_track_workflow` and helper methods)
- [ ] 2.5 Move shared storage processing (`process_shared_storage_job`)
- [ ] 2.6 Add dependency injection for capabilities, file manager, progress reporter
- [ ] 2.7 Update `RTCWorkerClient` to delegate job execution to `JobExecutor`

## 3. Extract File Transfer Module
- [ ] 3.1 Create `sleap_rtc/worker/file_manager.py` with `FileManager` class
- [ ] 3.2 Move file transfer methods (`send_file`)
- [ ] 3.3 Move compression methods (`zip_results`, `unzip_results`)
- [ ] 3.4 Move shared storage path validation logic (from `on_message`)
- [ ] 3.5 Add shared storage configuration handling
- [ ] 3.6 Update `RTCWorkerClient` to use `FileManager` for file operations

## 4. Extract Job Coordinator Module
- [ ] 4.1 Create `sleap_rtc/worker/job_coordinator.py` with `JobCoordinator` class
- [ ] 4.2 Move peer messaging methods (`_send_peer_message`, `handle_peer_message`)
- [ ] 4.3 Move job request handlers (`_handle_job_request`, `_handle_job_assignment`, `_handle_job_cancel`)
- [ ] 4.4 Add job queue tracking and state management
- [ ] 4.5 Update `RTCWorkerClient` to route peer messages through `JobCoordinator`

## 5. Extract State Manager Module
- [ ] 5.1 Create `sleap_rtc/worker/state_manager.py` with `StateManager` class
- [ ] 5.2 Move status update methods (`update_status`, `reregister_worker`)
- [ ] 5.3 Move signaling server API methods (`request_create_room`, `request_anonymous_signin`, `request_peer_room_deletion`)
- [ ] 5.4 Move session string generation (`generate_session_string`)
- [ ] 5.5 Add worker registration lifecycle management
- [ ] 5.6 Update `RTCWorkerClient` to use `StateManager` for registration and status

## 6. Extract Progress Reporter Module
- [ ] 6.1 Create `sleap_rtc/worker/progress_reporter.py` with `ProgressReporter` class
- [ ] 6.2 Move ZMQ socket initialization (`start_zmq_control`)
- [ ] 6.3 Move progress listener (`start_progress_listener`)
- [ ] 6.4 Add lifecycle management (start, stop, cleanup)
- [ ] 6.5 Update `JobExecutor` to use `ProgressReporter` for training progress

## 7. Refactor RTCWorkerClient as Orchestrator
- [ ] 7.1 Update `RTCWorkerClient.__init__` to instantiate all manager classes
- [ ] 7.2 Keep WebRTC connection methods (`handle_connection`, `on_datachannel`, `on_iceconnectionstatechange`)
- [ ] 7.3 Update `on_datachannel` message handling to delegate to appropriate managers
- [ ] 7.4 Keep `run_worker` method for main worker lifecycle
- [ ] 7.5 Keep `clean_exit` and `keep_ice_alive` connection management methods
- [ ] 7.6 Remove legacy/debug methods (`send_worker_messages`)

## 8. Update Imports and Integration
- [ ] 8.1 Update `sleap_rtc/cli/worker.py` imports if needed
- [ ] 8.2 Verify backward compatibility of public API
- [ ] 8.3 Run `black` and `ruff` on all new modules
- [ ] 8.4 Add module-level docstrings to all new files

## 9. Testing and Validation
- [ ] 9.1 Manual test: Worker startup and registration
- [ ] 9.2 Manual test: Client connection and job submission
- [ ] 9.3 Manual test: Training job execution with progress reporting
- [ ] 9.4 Manual test: Inference job execution
- [ ] 9.5 Manual test: Shared storage transfer (if configured)
- [ ] 9.6 Manual test: Worker reconnection after client disconnect
- [ ] 9.7 Verify no behavioral changes from original implementation

## 10. Documentation
- [ ] 10.1 Add architecture diagram showing module relationships
- [ ] 10.2 Update README if worker setup instructions changed
- [ ] 10.3 Document module responsibilities in code comments
- [ ] 10.4 Add inline comments for complex delegation logic
