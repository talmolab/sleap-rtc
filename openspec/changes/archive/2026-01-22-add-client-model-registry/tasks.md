# Implementation Tasks

## 1. Client Registry Infrastructure

- [ ] 1.1 Create `sleap_rtc/client/client_model_registry.py` with `ClientModelRegistry` class
  - [ ] 1.1.1 Implement `__init__()` with registry path at `~/.sleap-rtc/models/manifest.json`
  - [ ] 1.1.2 Implement `_load_registry()` to read JSON with corruption handling
  - [ ] 1.1.3 Implement `_save_registry()` with atomic write (temp file + rename)
  - [ ] 1.1.4 Implement `_expand_path()` helper to resolve `~` in paths
  - [ ] 1.1.5 Create `~/.sleap-rtc/models/` directory on first initialization
- [ ] 1.2 Implement core registry methods
  - [ ] 1.2.1 `register(model_info: dict) -> str` - Add model entry
  - [ ] 1.2.2 `get(model_id: str) -> dict | None` - Retrieve by ID
  - [ ] 1.2.3 `list(filters: dict = None) -> list[dict]` - List with filtering
  - [ ] 1.2.4 `update(model_id: str, updates: dict) -> None` - Update metadata
  - [ ] 1.2.5 `delete(model_id: str) -> None` - Remove entry (optionally delete files)
  - [ ] 1.2.6 `exists(model_id: str) -> bool` - Check if model exists
- [ ] 1.3 Add unit tests for `ClientModelRegistry`
  - [ ] 1.3.1 Test registry initialization (fresh and existing)
  - [ ] 1.3.2 Test model registration with various sources
  - [ ] 1.3.3 Test listing and filtering operations
  - [ ] 1.3.4 Test update and delete operations
  - [ ] 1.3.5 Test corrupted registry recovery
  - [ ] 1.3.6 Test path expansion and directory creation

## 2. Alias Management System

- [ ] 2.1 Add alias methods to `ClientModelRegistry`
  - [ ] 2.1.1 `set_alias(model_id: str, alias: str, force: bool = False) -> bool` - Set alias with collision detection
  - [ ] 2.1.2 `get_by_alias(alias: str) -> dict | None` - Retrieve model by alias
  - [ ] 2.1.3 `resolve(identifier: str) -> str | None` - Resolve ID or alias to ID
  - [ ] 2.1.4 `remove_alias(alias: str) -> None` - Remove alias (keep model)
  - [ ] 2.1.5 `list_aliases() -> dict[str, str]` - Get all alias mappings
- [ ] 2.2 Add alias methods to worker `ModelRegistry` (extend base proposal)
  - [ ] 2.2.1 Add same alias methods as client registry
  - [ ] 2.2.2 Update registry schema to include `aliases` dict
  - [ ] 2.2.3 Migrate existing registries (add empty `aliases` dict if missing)
- [ ] 2.3 Add unit tests for alias system
  - [ ] 2.3.1 Test alias creation and collision handling
  - [ ] 2.3.2 Test alias resolution (ID vs alias)
  - [ ] 2.3.3 Test alias removal and reassignment
  - [ ] 2.3.4 Test case-sensitivity and special characters in aliases
  - [ ] 2.3.5 Test alias persistence across registry reloads

## 3. Model Import Command

- [ ] 3.1 Implement `import-model` command in `cli.py`
  - [ ] 3.1.1 Add `@cli.command()` for `import-model` with path and alias options
  - [ ] 3.1.2 Validate source directory exists and contains model files
  - [ ] 3.1.3 Detect model type from `training_config.yaml` if present
  - [ ] 3.1.4 Prompt user for model type if not auto-detected
  - [ ] 3.1.5 Prompt user for alias if not provided via flag
  - [ ] 3.1.6 Generate model ID from config hash (or random if no config)
  - [ ] 3.1.7 Create symlink by default (`~/.sleap-rtc/models/{type}_{id}/ -> source`)
  - [ ] 3.1.8 Support `--copy` flag to duplicate files instead of symlink
  - [ ] 3.1.9 Register model in client registry with source="local-import"
  - [ ] 3.1.10 Display import summary with model ID, alias, and local path
- [ ] 3.2 Add model file detection helpers
  - [ ] 3.2.1 `find_checkpoint_files(path: Path) -> list[Path]` - Find .ckpt and .h5 files
  - [ ] 3.2.2 `detect_model_type(path: Path) -> str | None` - Parse training_config.yaml
  - [ ] 3.2.3 `calculate_model_size(path: Path) -> int` - Sum checkpoint file sizes
  - [ ] 3.2.4 Validate checkpoint files are not corrupted (basic file open test)
- [ ] 3.3 Add integration tests for import command
  - [ ] 3.3.1 Test import with auto-detected model type
  - [ ] 3.3.2 Test import with manual model type specification
  - [ ] 3.3.3 Test symlink vs copy modes
  - [ ] 3.3.4 Test import of model without training_config.yaml
  - [ ] 3.3.5 Test error handling (missing directory, no checkpoint files)

## 4. Enhanced List and Info Commands

- [ ] 4.1 Implement `list-models` command for client
  - [ ] 4.1.1 Update existing `list-models` or create new client-specific command
  - [ ] 4.1.2 Add filters: `--status`, `--type`, `--location` (local/worker/both)
  - [ ] 4.1.3 Display table with columns: ID/Alias, Type, Location, Loss, Downloaded
  - [ ] 4.1.4 Show location status: "local only", "worker only", "local + worker"
  - [ ] 4.1.5 Add `--format` option for JSON output
  - [ ] 4.1.6 Sort by download date (newest first) by default
  - [ ] 4.1.7 Add `--sort-by` option (date, name, type, loss)
- [ ] 4.2 Implement `model-info` command
  - [ ] 4.2.1 Create `@cli.command()` for `model-info <identifier>`
  - [ ] 4.2.2 Resolve identifier (ID or alias) to model
  - [ ] 4.2.3 Display detailed formatted output with all metadata fields
  - [ ] 4.2.4 Show locations (local path, worker path if applicable)
  - [ ] 4.2.5 Validate checkpoint files exist and show size
  - [ ] 4.2.6 Display training hyperparameters if available
  - [ ] 4.2.7 Show usage examples (local and remote inference commands)
  - [ ] 4.2.8 Add `--json` flag for machine-readable output
- [ ] 4.3 Implement `compare-models` command
  - [ ] 4.3.1 Create `@cli.command()` accepting multiple model identifiers
  - [ ] 4.3.2 Resolve all identifiers to models
  - [ ] 4.3.3 Create comparison table with key attributes (type, loss, epochs, etc.)
  - [ ] 4.3.4 Highlight best values (lowest loss, highest epochs, etc.)
  - [ ] 4.3.5 Show side-by-side hyperparameter differences
  - [ ] 4.3.6 Display location availability for each model
- [ ] 4.4 Add table formatting helpers
  - [ ] 4.4.1 Implement `format_table()` using basic string formatting or `tabulate` library
  - [ ] 4.4.2 Add column alignment and truncation for long values
  - [ ] 4.4.3 Support color output using Click's style utilities
  - [ ] 4.4.4 Add pagination for long lists (or recommend piping to `less`)

## 5. Model Tagging and Metadata Commands

- [ ] 5.1 Implement `tag-model` command
  - [ ] 5.1.1 Create `@cli.command()` for `tag-model <identifier> <alias>`
  - [ ] 5.1.2 Resolve identifier to model ID
  - [ ] 5.1.3 Set alias with collision detection and user prompt
  - [ ] 5.1.4 Display success message with old and new alias
  - [ ] 5.1.5 Support `--force` flag to overwrite without prompt
- [ ] 5.2 Implement `update-model` command for metadata
  - [ ] 5.2.1 Create `@cli.command()` for `update-model <identifier>`
  - [ ] 5.2.2 Add options: `--notes`, `--tags`, `--add-tag`, `--remove-tag`
  - [ ] 5.2.3 Update model metadata in registry
  - [ ] 5.2.4 Display updated model info after changes
- [ ] 5.3 Add extended metadata tracking
  - [ ] 5.3.1 Update registry schema to include optional fields (tags, notes, hyperparameters)
  - [ ] 5.3.2 Extract hyperparameters from training_config.yaml during training
  - [ ] 5.3.3 Store sleap-nn version and git commit if available
  - [ ] 5.3.4 Support user-provided tags as list of strings

## 6. WebRTC Registry Query Protocol

- [ ] 6.1 Add RTC message handlers in `worker_class.py`
  - [ ] 6.1.1 Implement `handle_registry_query()` message handler
  - [ ] 6.1.2 Support `list_models` command with filters
  - [ ] 6.1.3 Support `get_model_info` command with model ID/alias
  - [ ] 6.1.4 Support `check_model_exists` command
  - [ ] 6.1.5 Return `registry_response` messages with requested data
  - [ ] 6.1.6 Add error handling for invalid queries or missing models
- [ ] 6.2 Add RTC query methods in `client_class.py`
  - [ ] 6.2.1 Implement `query_worker_registry(filters: dict) -> list[dict]`
  - [ ] 6.2.2 Implement `get_worker_model_info(model_id: str) -> dict | None`
  - [ ] 6.2.3 Implement `check_worker_model(model_id: str) -> bool`
  - [ ] 6.2.4 Add timeout handling for queries (default 10 seconds)
  - [ ] 6.2.5 Cache query results with TTL (avoid repeated queries)
- [ ] 6.3 Implement `worker list-models` CLI command
  - [ ] 6.3.1 Create command that connects to worker and queries registry
  - [ ] 6.3.2 Display results in same table format as client list
  - [ ] 6.3.3 Add `--session` option to specify worker connection
  - [ ] 6.3.4 Support same filters as client list command
- [ ] 6.4 Add integration tests for query protocol
  - [ ] 6.4.1 Test list query with various filters
  - [ ] 6.4.2 Test model info query for existing and missing models
  - [ ] 6.4.3 Test existence check
  - [ ] 6.4.4 Test timeout handling
  - [ ] 6.4.5 Test error cases (disconnected, invalid query)

## 7. Model Transfer Infrastructure

- [ ] 7.1 Add model packaging utilities
  - [ ] 7.1.1 Create `sleap_rtc/models/model_package.py` module
  - [ ] 7.1.2 Implement `package_model(model_path: Path) -> dict` - Create file manifest
  - [ ] 7.1.3 Implement `calculate_checksums(files: list[Path]) -> dict[str, str]` - MD5 hashes
  - [ ] 7.1.4 Implement `validate_package(manifest: dict, path: Path) -> bool` - Verify integrity
  - [ ] 7.1.5 Support packaging checkpoint + config + optional metadata
- [ ] 7.2 Extend chunked transfer for model files
  - [ ] 7.2.1 Add `model_file_chunk` message type to existing transfer code
  - [ ] 7.2.2 Implement `send_model_chunks()` method for streaming files
  - [ ] 7.2.3 Implement `receive_model_chunks()` method for reassembly
  - [ ] 7.2.4 Add progress tracking (bytes sent/received, percentage)
  - [ ] 7.2.5 Support resume from failed transfers (track completed chunks)
  - [ ] 7.2.6 Validate checksums after transfer completion
- [ ] 7.3 Add atomic file operations
  - [ ] 7.3.1 Implement `atomic_write_model()` - Write to temp dir, validate, then move
  - [ ] 7.3.2 Add disk space check before starting transfer
  - [ ] 7.3.3 Clean up temp files on failure or cancellation
  - [ ] 7.3.4 Handle partial transfers (delete incomplete files)

## 8. Push Model Command (Client → Worker)

- [ ] 8.1 Implement `push-model` command in `cli.py`
  - [ ] 8.1.1 Create `@cli.command()` for `push-model <identifier> --worker <session>`
  - [ ] 8.1.2 Resolve identifier to local model
  - [ ] 8.1.3 Validate model exists locally and has checkpoint files
  - [ ] 8.1.4 Connect to worker using session token
  - [ ] 8.1.5 Query worker to check if model already exists
  - [ ] 8.1.6 Prompt user if model exists on worker (overwrite/skip)
  - [ ] 8.1.7 Package model files and calculate checksums
  - [ ] 8.1.8 Send `model_transfer` initiation message with manifest
  - [ ] 8.1.9 Stream chunks with progress bar
  - [ ] 8.1.10 Wait for worker confirmation and registration
  - [ ] 8.1.11 Update client registry with `on_worker: true` status
  - [ ] 8.1.12 Display success message with worker path
- [ ] 8.2 Add worker-side push handler
  - [ ] 8.2.1 Implement `handle_model_push()` in `worker_class.py`
  - [ ] 8.2.2 Validate disk space available
  - [ ] 8.2.3 Create temp directory for incoming transfer
  - [ ] 8.2.4 Receive and reassemble chunks
  - [ ] 8.2.5 Validate checksums match manifest
  - [ ] 8.2.6 Move to final location `models/{type}_{id}/`
  - [ ] 8.2.7 Register in worker registry with source="client-upload"
  - [ ] 8.2.8 Send confirmation message to client
  - [ ] 8.2.9 Clean up temp files
- [ ] 8.3 Add integration tests for push
  - [ ] 8.3.1 Test successful push of new model
  - [ ] 8.3.2 Test push when model already exists (overwrite scenario)
  - [ ] 8.3.3 Test push failure (network interruption, simulate mid-transfer)
  - [ ] 8.3.4 Test checksum validation failure
  - [ ] 8.3.5 Test insufficient disk space on worker

## 9. Pull Model Command (Worker → Client)

- [ ] 9.1 Implement `pull-model` command in `cli.py`
  - [ ] 9.1.1 Create `@cli.command()` for `pull-model <identifier> --worker <session>`
  - [ ] 9.1.2 Connect to worker using session token
  - [ ] 9.1.3 Query worker for model by identifier (resolve alias on worker)
  - [ ] 9.1.4 Check if model already exists locally
  - [ ] 9.1.5 Prompt user if model exists locally (overwrite/skip)
  - [ ] 9.1.6 Send `model_transfer` request with `command: "pull"`
  - [ ] 9.1.7 Receive file manifest from worker
  - [ ] 9.1.8 Validate local disk space
  - [ ] 9.1.9 Receive chunks with progress bar
  - [ ] 9.1.10 Reassemble files to `~/.sleap-rtc/models/{type}_{id}/`
  - [ ] 9.1.11 Validate checksums
  - [ ] 9.1.12 Register in client registry with source="worker-pull"
  - [ ] 9.1.13 Display success message with local path
- [ ] 9.2 Add worker-side pull handler
  - [ ] 9.2.1 Implement `handle_model_pull()` in `worker_class.py`
  - [ ] 9.2.2 Resolve model identifier to registry entry
  - [ ] 9.2.3 Validate checkpoint files exist on worker
  - [ ] 9.2.4 Package model files and calculate checksums
  - [ ] 9.2.5 Send manifest to client
  - [ ] 9.2.6 Stream chunks to client with flow control
  - [ ] 9.2.7 Wait for client confirmation
  - [ ] 9.2.8 Log transfer completion
- [ ] 9.3 Add integration tests for pull
  - [ ] 9.3.1 Test successful pull of worker model
  - [ ] 9.3.2 Test pull when model already exists locally
  - [ ] 9.3.3 Test pull failure (network interruption)
  - [ ] 9.3.4 Test pull of non-existent model (error handling)
  - [ ] 9.3.5 Test insufficient disk space on client

## 10. Client Registry Integration with Training Flow

- [ ] 10.1 Update client training workflow
  - [ ] 10.1.1 After training completes on worker, automatically download model metadata
  - [ ] 10.1.2 Prompt user: "Download trained model? [Y/n]"
  - [ ] 10.1.3 If yes, trigger automatic pull operation
  - [ ] 10.1.4 Register model in client registry with source="worker-training"
  - [ ] 10.1.5 Prompt for alias: "Give it a friendly name? [y/N]"
  - [ ] 10.1.6 Set alias if user provides one
  - [ ] 10.1.7 Display model info summary (ID, alias, location)
- [ ] 10.2 Update client registry on training events
  - [ ] 10.2.1 Create client registry entry when training starts (status="training")
  - [ ] 10.2.2 Update status to "completed" when training finishes
  - [ ] 10.2.3 Store training metrics from worker in client registry
  - [ ] 10.2.4 Mark `on_worker: true` immediately after training

## 11. Update Track Command for Alias Support

- [ ] 11.1 Modify `track` command in `cli.py`
  - [ ] 11.1.1 Update `--model` option to accept ID or alias
  - [ ] 11.1.2 Add `resolve_model_identifier()` helper to check client registry
  - [ ] 11.1.3 If alias, resolve to model ID, then to checkpoint path
  - [ ] 11.1.4 Support `--remote` flag to use worker model instead of local
  - [ ] 11.1.5 If `--remote`, query worker to verify model exists
  - [ ] 11.1.6 Display resolved model info before starting inference
- [ ] 11.2 Update `client_track_class.py` for alias resolution
  - [ ] 11.2.1 Add `resolve_model_path(identifier: str, remote: bool) -> Path` method
  - [ ] 11.2.2 Check client registry first for local models
  - [ ] 11.2.3 Query worker registry if remote flag set
  - [ ] 11.2.4 Fall back to path-based reference if not in registry
  - [ ] 11.2.5 Validate checkpoint exists before starting inference

## 12. Sync and Maintenance Commands

- [ ] 12.1 Implement `sync` command for registry reconciliation
  - [ ] 12.1.1 Create `@cli.command()` for `sync --worker <session>`
  - [ ] 12.1.2 Query worker registry for all models
  - [ ] 12.1.3 Compare with client registry
  - [ ] 12.1.4 Update `on_worker` status for each model
  - [ ] 12.1.5 Mark models as missing if worker no longer has them
  - [ ] 12.1.6 Display sync summary (updated, removed, added)
- [ ] 12.2 Implement `repair-model` command
  - [ ] 12.2.1 Create `@cli.command()` for `repair-model <identifier>`
  - [ ] 12.2.2 Check if local files exist for model
  - [ ] 12.2.3 If symlink broken, prompt for new source path
  - [ ] 12.2.4 If files missing, offer to pull from worker
  - [ ] 12.2.5 Update registry with repaired paths
  - [ ] 12.2.6 Validate checkpoints after repair
- [ ] 12.3 Implement `clean-models` command
  - [ ] 12.3.1 Create `@cli.command()` for `clean-models`
  - [ ] 12.3.2 Find models with missing checkpoint files
  - [ ] 12.3.3 Find registry entries for deleted files
  - [ ] 12.3.4 Display cleanup candidates with size information
  - [ ] 12.3.5 Prompt user for confirmation before deletion
  - [ ] 12.3.6 Remove files and/or registry entries based on user choice
  - [ ] 12.3.7 Add `--dry-run` flag to show what would be cleaned

## 13. Error Handling and Validation

- [ ] 13.1 Add comprehensive error handling
  - [ ] 13.1.1 Handle registry file corruption gracefully
  - [ ] 13.1.2 Handle missing checkpoint files with clear error messages
  - [ ] 13.1.3 Handle network failures during transfer with retry logic
  - [ ] 13.1.4 Handle disk space exhaustion before starting transfers
  - [ ] 13.1.5 Handle permission errors on file operations
  - [ ] 13.1.6 Add timeout handling for all worker queries
- [ ] 13.2 Add input validation
  - [ ] 13.2.1 Validate model identifiers (ID format, alias characters)
  - [ ] 13.2.2 Validate paths provided by user (exist, readable, correct file types)
  - [ ] 13.2.3 Validate session tokens before operations
  - [ ] 13.2.4 Validate filter parameters in list commands
- [ ] 13.3 Add logging
  - [ ] 13.3.1 Log all registry operations (create, update, delete)
  - [ ] 13.3.2 Log transfer operations (start, progress, complete, fail)
  - [ ] 13.3.3 Log worker queries and responses
  - [ ] 13.3.4 Use loguru with appropriate log levels
  - [ ] 13.3.5 Add `--debug` flag to CLI for verbose logging

## 14. Testing

- [ ] 14.1 Unit tests for client registry
  - [ ] 14.1.1 Test all CRUD operations
  - [ ] 14.1.2 Test alias management
  - [ ] 14.1.3 Test filtering and sorting
  - [ ] 14.1.4 Test corruption recovery
  - [ ] 14.1.5 Test concurrent access (if applicable)
- [ ] 14.2 Integration tests for transfer protocol
  - [ ] 14.2.1 Test push operation end-to-end
  - [ ] 14.2.2 Test pull operation end-to-end
  - [ ] 14.2.3 Test interrupted transfers with resume
  - [ ] 14.2.4 Test checksum validation failure scenarios
  - [ ] 14.2.5 Test large model transfers (>500MB)
- [ ] 14.3 Integration tests for CLI commands
  - [ ] 14.3.1 Test import-model with various model types
  - [ ] 14.3.2 Test list-models with filters
  - [ ] 14.3.3 Test model-info display
  - [ ] 14.3.4 Test tag-model alias operations
  - [ ] 14.3.5 Test track command with alias resolution
- [ ] 14.4 End-to-end workflow tests
  - [ ] 14.4.1 Test full training workflow with client registry
  - [ ] 14.4.2 Test import → push → use on worker workflow
  - [ ] 14.4.3 Test train on worker → pull → use locally workflow
  - [ ] 14.4.4 Test multi-model management scenarios
- [ ] 14.5 Edge case tests
  - [ ] 14.5.1 Test alias collision handling
  - [ ] 14.5.2 Test model ID collision handling
  - [ ] 14.5.3 Test registry desync scenarios
  - [ ] 14.5.4 Test broken symlinks in imported models
  - [ ] 14.5.5 Test operations with missing worker connection

## 15. Documentation

- [ ] 15.1 Update README.md
  - [ ] 15.1.1 Add "Model Management" section
  - [ ] 15.1.2 Document client registry concept and location
  - [ ] 15.1.3 Document all new CLI commands with examples
  - [ ] 15.1.4 Add workflow diagrams for common scenarios
  - [ ] 15.1.5 Document alias system and naming conventions
- [ ] 15.2 Add inline code documentation
  - [ ] 15.2.1 Google-style docstrings for all `ClientModelRegistry` methods
  - [ ] 15.2.2 Docstrings for all transfer protocol functions
  - [ ] 15.2.3 Docstrings for all new CLI commands
  - [ ] 15.2.4 Add module-level docstrings explaining architecture
- [ ] 15.3 Create user guide
  - [ ] 15.3.1 "Getting Started with Model Management" tutorial
  - [ ] 15.3.2 "Importing Pre-Trained Models" guide
  - [ ] 15.3.3 "Working with Multiple Workers" guide
  - [ ] 15.3.4 "Model Naming Best Practices" guide
- [ ] 15.4 Create troubleshooting guide
  - [ ] 15.4.1 Registry corruption recovery steps
  - [ ] 15.4.2 Transfer failure recovery
  - [ ] 15.4.3 Broken symlink repair
  - [ ] 15.4.4 Desync resolution steps
- [ ] 15.5 Add example scripts
  - [ ] 15.5.1 Batch import script example
  - [ ] 15.5.2 Model backup script example
  - [ ] 15.5.3 Multi-worker sync script example

## 16. Performance Optimization

- [ ] 16.1 Optimize registry operations
  - [ ] 16.1.1 Add in-memory caching for frequently accessed models
  - [ ] 16.1.2 Implement lazy loading for large registries
  - [ ] 16.1.3 Add pagination for list operations with 100+ models
  - [ ] 16.1.4 Optimize JSON serialization for large registries
- [ ] 16.2 Optimize transfer operations
  - [ ] 16.2.1 Tune chunk size for optimal throughput (test 64KB vs 256KB)
  - [ ] 16.2.2 Add parallel chunk transfers if supported by WebRTC
  - [ ] 16.2.3 Implement compression for config files (not checkpoints)
  - [ ] 16.2.4 Add transfer rate limiting to prevent bandwidth saturation
- [ ] 16.3 Add performance metrics
  - [ ] 16.3.1 Track and log transfer speeds
  - [ ] 16.3.2 Track registry operation latencies
  - [ ] 16.3.3 Add `--benchmark` flag to measure performance

## 17. Deployment and Validation

- [ ] 17.1 Ensure backward compatibility
  - [ ] 17.1.1 Verify existing workflows without registry still work
  - [ ] 17.1.2 Verify path-based model references still work
  - [ ] 17.1.3 Test mixed environment (some users with registry, some without)
  - [ ] 17.1.4 Verify worker without base registry handles queries gracefully
- [ ] 17.2 Create migration guide
  - [ ] 17.2.1 Document upgrade path from pre-registry version
  - [ ] 17.2.2 Document how to import existing models
  - [ ] 17.2.3 Document registry location and backup procedures
- [ ] 17.3 Monitor initial deployment
  - [ ] 17.3.1 Add telemetry for feature usage (opt-in)
  - [ ] 17.3.2 Track error rates for new commands
  - [ ] 17.3.3 Monitor transfer success rates
  - [ ] 17.3.4 Collect user feedback on alias naming conventions
