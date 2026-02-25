# Implementation Tasks

## 1. Registry Infrastructure

- [ ] 1.1 Create `sleap_rtc/worker/model_registry.py` with `ModelRegistry` class
  - [ ] 1.1.1 Implement `__init__()` with registry path initialization and file creation
  - [ ] 1.1.2 Implement `_load_registry()` to read JSON file with corruption handling
  - [ ] 1.1.3 Implement `_save_registry()` with atomic write (temp file + rename pattern)
  - [ ] 1.1.4 Implement `generate_model_id()` for SHA256-based hash generation
- [ ] 1.2 Implement core registry methods
  - [ ] 1.2.1 `register(model_info: dict) -> str` - Add new model entry
  - [ ] 1.2.2 `get(model_id: str) -> dict | None` - Retrieve model by ID
  - [ ] 1.2.3 `list(filters: dict = None) -> list[dict]` - List models with optional filtering
  - [ ] 1.2.4 `mark_completed(model_id: str, metrics: dict) -> None` - Update to completed status
  - [ ] 1.2.5 `mark_interrupted(model_id: str, checkpoint_path: str, epoch: int) -> None` - Mark as interrupted
  - [ ] 1.2.6 `get_interrupted() -> list[dict]` - Get all interrupted jobs
  - [ ] 1.2.7 `get_checkpoint_path(model_id: str) -> Path` - Resolve checkpoint path
- [ ] 1.3 Add unit tests for `ModelRegistry` class
  - [ ] 1.3.1 Test registry initialization (fresh and existing)
  - [ ] 1.3.2 Test model registration and ID generation
  - [ ] 1.3.3 Test hash collision handling (append "-2" suffix)
  - [ ] 1.3.4 Test listing and filtering operations
  - [ ] 1.3.5 Test status transitions (training → completed, training → interrupted)
  - [ ] 1.3.6 Test corrupted registry recovery
  - [ ] 1.3.7 Test atomic write operations

## 2. Worker Integration

- [ ] 2.1 Update `worker_class.py` to integrate registry
  - [ ] 2.1.1 Import `ModelRegistry` and initialize in `__init__()`
  - [ ] 2.1.2 Modify `run_all_training_jobs()` to generate model ID at job start
  - [ ] 2.1.3 Call `registry.register()` when training begins (before `sleap-nn train`)
  - [ ] 2.1.4 Update model directory naming from `run_name` to `{model_type}_{model_id}`
  - [ ] 2.1.5 Call `registry.mark_completed()` after successful training with metrics
  - [ ] 2.1.6 Extract and store final validation loss, epochs completed from training logs
- [ ] 2.2 Implement checkpoint recovery in connection handling
  - [ ] 2.2.1 Modify `on_iceconnectionstatechange()` to detect connection drops during training
  - [ ] 2.2.2 Call `registry.mark_interrupted()` when connection lost during active job
  - [ ] 2.2.3 Add logic in `run_all_training_jobs()` to check for interrupted jobs at start
  - [ ] 2.2.4 Pass `trainer_config.resume_ckpt_path` to `sleap-nn train` command when resuming
  - [ ] 2.2.5 Handle checkpoint file validation (log warning if missing)
- [ ] 2.3 Update metadata collection
  - [ ] 2.3.1 Collect dataset name from uploaded package filename
  - [ ] 2.3.2 Collect GPU model from existing `self.gpu_model`
  - [ ] 2.3.3 Calculate training duration (end time - start time)
  - [ ] 2.3.4 Store training job hash (MD5 of uploaded zip file)

## 3. CLI Commands

- [ ] 3.1 Add `list-models` command to `cli.py`
  - [ ] 3.1.1 Create `@cli.command()` decorator for `list-models`
  - [ ] 3.1.2 Add options: `--status` (filter), `--model-type` (filter), `--format` (table/json)
  - [ ] 3.1.3 Query registry and display results in formatted table (use `tabulate` or manual formatting)
  - [ ] 3.1.4 Show: model ID, type, status, created date, validation loss
- [ ] 3.2 Add `model-info` command to `cli.py`
  - [ ] 3.2.1 Create `@cli.command()` decorator for `model-info <model-id>`
  - [ ] 3.2.2 Query registry for full model details
  - [ ] 3.2.3 Display formatted output with all metadata fields
  - [ ] 3.2.4 Show checkpoint path and file existence status
- [ ] 3.3 Update `track` command to support model ID
  - [ ] 3.3.1 Add `--model <model-id>` option to `track` command (mutually exclusive with `--checkpoint`)
  - [ ] 3.3.2 Resolve model ID to checkpoint path using registry
  - [ ] 3.3.3 Update inference script generation to use resolved path
  - [ ] 3.3.4 Validate model exists before starting inference

## 4. Testing and Validation

- [ ] 4.1 Integration testing
  - [ ] 4.1.1 Test full training flow with registry tracking (start → complete)
  - [ ] 4.1.2 Test simulated connection drop and interrupted job marking
  - [ ] 4.1.3 Test training resumption from checkpoint
  - [ ] 4.1.4 Test multiple training runs creating unique model IDs
  - [ ] 4.1.5 Test hash collision scenario (same config, manually triggered)
- [ ] 4.2 CLI testing
  - [ ] 4.2.1 Test `list-models` with various filters
  - [ ] 4.2.2 Test `model-info` for existing and non-existent IDs
  - [ ] 4.2.3 Test `track --model <id>` for inference workflow
- [ ] 4.3 Edge case testing
  - [ ] 4.3.1 Test registry corruption recovery
  - [ ] 4.3.2 Test checkpoint file deleted but registry entry exists
  - [ ] 4.3.3 Test concurrent registry access (if multi-job support added)
  - [ ] 4.3.4 Test registry migration across worker restarts

## 5. Documentation

- [ ] 5.1 Update `README.md` with model registry usage
  - [ ] 5.1.1 Add section on model identification and tracking
  - [ ] 5.1.2 Document CLI commands (`list-models`, `model-info`, `track --model`)
  - [ ] 5.1.3 Explain checkpoint recovery workflow
- [ ] 5.2 Add inline code documentation
  - [ ] 5.2.1 Add Google-style docstrings to all `ModelRegistry` methods
  - [ ] 5.2.2 Add docstrings to new worker methods
  - [ ] 5.2.3 Add docstrings to new CLI commands
- [ ] 5.3 Create troubleshooting guide
  - [ ] 5.3.1 Document registry corruption recovery steps
  - [ ] 5.3.2 Document how to manually resume interrupted training
  - [ ] 5.3.3 Document how to clean up old models

## 6. Deployment and Migration

- [ ] 6.1 Ensure backward compatibility
  - [ ] 6.1.1 Verify existing workers without registry continue to function
  - [ ] 6.1.2 Verify old model directories are not affected
  - [ ] 6.1.3 Test mixed environment (some workers with registry, some without)
- [ ] 6.2 Monitor initial deployment
  - [ ] 6.2.1 Add logging for registry operations (creation, updates, errors)
  - [ ] 6.2.2 Monitor for hash collisions in production
  - [ ] 6.2.3 Track checkpoint recovery success rate
- [ ] 6.3 Performance validation
  - [ ] 6.3.1 Measure registry write overhead (<10ms target)
  - [ ] 6.3.2 Verify no training performance degradation
  - [ ] 6.3.3 Test registry lookup performance with 100+ models
