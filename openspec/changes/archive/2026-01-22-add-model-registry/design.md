# Model Registry and Checkpoint Recovery - Design Document

## Context

sleap-RTC enables remote training of SLEAP pose estimation models on GPU workers via WebRTC. Training is orchestrated by `sleap-nn train` (PyTorch Lightning-based) which inherently supports checkpointing. However, the current implementation has no visibility into checkpoint state and cannot recover from connection interruptions.

**Current Training Flow:**
1. Client packages training data → worker receives via WebRTC data channel
2. Worker extracts to `./labels.v929.pkg.slp.training_job/`
3. Worker runs `sleap-nn train --config-name centroid.yaml trainer_config.run_name=centroid_251024_152308`
4. Models saved to `models/{run_name}/` with `best.ckpt`, `training_config.yaml`, etc.
5. Results zipped and sent back to client

**Pain Points:**
- No tracking of which models exist or their training parameters
- Connection drops waste GPU time (must restart training from epoch 0)
- No easy way to reference models for inference by anything other than directory path
- Multiple runs create numbered variants (`centroid-1`, `centroid-2`) with no distinguishing info

**Stakeholders:**
- Users running remote training (need reliability and visibility)
- Workers with limited GPU resources (need efficient resumption)
- Inference workflows (need stable model references)

## Goals / Non-Goals

### Goals
1. **Model Identification**: Unique, deterministic IDs for trained models based on configuration + data
2. **Metadata Tracking**: Store training parameters, status, metrics, and paths in structured registry
3. **Checkpoint Recovery**: Automatically detect interruptions and enable seamless training resumption
4. **User Visibility**: CLI commands to list, inspect, and reference models by ID
5. **Backward Compatibility**: Existing workflows continue to function without migration

### Non-Goals
- Distributed registry across multiple workers (local-only for now)
- Model versioning or A/B comparison (future enhancement)
- Automatic model cleanup or retention policies (manual for now)
- Cloud storage integration for checkpoints (local filesystem only)
- Retroactive registration of pre-existing models (can be added later via import command)

## Decisions

### 1. Registry Storage Format: JSON

**Decision:** Use a single JSON file (`models/.registry/manifest.json`) for the registry.

**Rationale:**
- **Simplicity**: No database dependencies, easy to inspect/debug
- **Portability**: JSON is human-readable and version-controllable
- **Performance**: Sufficient for expected model count (<1000 models per worker)
- **Atomicity**: Python's `json.dump()` is atomic on POSIX systems with temp file + rename pattern

**Alternatives Considered:**
- SQLite: Overkill for simple key-value lookups; adds dependency complexity
- YAML: Slower parsing, less standard library support
- Directory-based metadata: Harder to query/search across models

**Structure:**
```json
{
  "version": "1.0",
  "models": {
    "a3f5e8c9": {
      "id": "a3f5e8c9",
      "full_hash": "a3f5e8c9d2b1f4e6c7a8b9d0e1f2a3b4c5d6e7f8",
      "run_name": "centroid_251024_152308",
      "model_type": "centroid",
      "training_job_hash": "b4c3d2e1",
      "created_at": "2024-10-25T15:23:08Z",
      "completed_at": "2024-10-25T15:30:45Z",
      "status": "completed",
      "checkpoint_path": "models/centroid_a3f5e8c9/best.ckpt",
      "config_path": "models/centroid_a3f5e8c9/training_config.yaml",
      "metrics": {
        "final_val_loss": 0.0234,
        "epochs_completed": 5,
        "best_epoch": 4
      },
      "metadata": {
        "dataset": "labels.v929.pkg.slp",
        "gpu_model": "NVIDIA RTX 3090",
        "training_duration_minutes": 7.62
      }
    }
  },
  "interrupted": ["a3f5e8c9"]
}
```

### 2. Hash Algorithm: SHA256 (first 8 hex chars)

**Decision:** Generate model IDs using SHA256 hash of `{model_config, data_hash, run_name}`, truncated to 8 characters.

**Rationale:**
- **Uniqueness**: SHA256 collision probability negligible for expected model count
- **Determinism**: Same config + data + timestamp = same hash (reproducible)
- **Readability**: 8 chars balances uniqueness with human usability (e.g., `a3f5e8c9`)
- **Compatibility**: Git-style short hashes are familiar to developers

**Hash Input:**
```python
import hashlib
import json

def generate_model_id(config: dict, labels_path: str, run_name: str) -> str:
    """Generate deterministic 8-char model ID."""
    # Hash input includes key discriminators
    hash_input = {
        "model_type": list(config['model_config']['head_configs'].keys()),
        "backbone": config['model_config']['backbone_config'],
        "run_name": run_name,
        "labels_md5": hashlib.md5(open(labels_path, 'rb').read()).hexdigest()
    }
    content = json.dumps(hash_input, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:8]
```

**Alternatives Considered:**
- MD5: Faster but cryptographically broken (SHA256 is standard library anyway)
- UUID: Non-deterministic, longer, less meaningful
- Timestamp-based: Not reproducible, subject to clock skew

### 3. Directory Naming: `{model_type}_{short_hash}`

**Decision:** Save models to `models/{model_type}_{short_hash}/` (e.g., `models/centroid_a3f5e8c9/`).

**Rationale:**
- **Human-Readable**: Type prefix helps identify model purpose at a glance
- **Unique**: Hash suffix prevents collisions across runs
- **Sortable**: Alphabetical sorting groups models by type
- **Compatible**: Follows existing `models/{run_name}/` pattern

**Migration from Current Naming:**
- Old: `models/centroid_251024_152308/` (timestamp-based run_name)
- New: `models/centroid_a3f5e8c9/` (type + hash)
- Worker still accepts `run_name` from client but appends hash internally

### 4. Checkpoint Recovery Mechanism

**Decision:** Track training state in registry; on connection loss, mark as "interrupted"; on reconnection, pass `resume_ckpt_path` to `sleap-nn train`.

**Flow:**
```
1. Training starts → registry.register(model_id, status="training")
2. Connection drops → registry.mark_interrupted(model_id, last_checkpoint="best.ckpt")
3. User reconnects → worker queries registry.get_interrupted()
4. Worker launches: sleap-nn train ... trainer_config.resume_ckpt_path=models/centroid_a3f5e8c9/best.ckpt
5. Training completes → registry.mark_completed(model_id, metrics={...})
```

**PyTorch Lightning Checkpoint Format:**
- `best.ckpt` contains model weights + optimizer state + epoch counter
- Passing `resume_ckpt_path` to `sleap-nn train` automatically continues from saved epoch
- No manual state reconstruction needed (Lightning handles it)

**Alternatives Considered:**
- Manual epoch tracking: Complex, error-prone, redundant with Lightning checkpoints
- External checkpoint storage: Unnecessary complexity for local worker scenario
- Automatic resumption without user confirmation: Risky if user wants fresh training

### 5. Registry API Design

**Decision:** Implement `ModelRegistry` class with simple synchronous methods (no async, no locking).

**Interface:**
```python
class ModelRegistry:
    def __init__(self, registry_path: Path = Path("models/.registry/manifest.json")):
        """Initialize registry, create if missing."""

    def register(self, model_info: dict) -> str:
        """Add new model to registry, return model_id."""

    def get(self, model_id: str) -> dict | None:
        """Get model metadata by ID."""

    def list(self, filters: dict = None) -> list[dict]:
        """List models with optional filters (status, model_type, etc.)."""

    def mark_completed(self, model_id: str, metrics: dict) -> None:
        """Mark training completed and save metrics."""

    def mark_interrupted(self, model_id: str, checkpoint_path: str, epoch: int) -> None:
        """Mark training interrupted with resumable state."""

    def get_interrupted(self) -> list[dict]:
        """Get all interrupted jobs."""

    def get_checkpoint_path(self, model_id: str) -> Path:
        """Resolve model ID to checkpoint path for inference."""
```

**Rationale:**
- **Simplicity**: Synchronous methods match current worker implementation (no asyncio needed for file I/O)
- **Testability**: Pure functions with clear inputs/outputs
- **Thread Safety**: Single-worker assumption (no concurrent training jobs)
- **Extensibility**: Easy to add methods like `delete()`, `update_metadata()` later

**Concurrency Considerations:**
- Current worker implementation runs one job at a time (`max_concurrent_jobs = 1`)
- Registry writes only happen at job lifecycle events (start, complete, interrupt)
- If future multi-job support added, can introduce file locking (`fcntl` on POSIX, `msvcrt` on Windows)

## Risks / Trade-offs

### Risk: Hash Collisions
- **Probability**: ~1 in 4 billion for 8-char SHA256 truncation
- **Mitigation**: Check for existing ID on registration; if collision detected, append `-2`, `-3`, etc.
- **Trade-off**: Accepted risk for simplicity (full 64-char hashes are overkill)

### Risk: Registry Corruption
- **Scenario**: Worker crashes mid-write, leaving invalid JSON
- **Mitigation**: Write to temp file + atomic rename pattern; keep backup of last valid state
- **Trade-off**: Small performance overhead (~5ms per write) for reliability

### Risk: Disk Space Exhaustion
- **Scenario**: Hundreds of models accumulate over time
- **Mitigation**: Document manual cleanup process; future enhancement for retention policies
- **Trade-off**: Manual management vs automatic cleanup complexity

### Risk: Checkpoint Compatibility
- **Scenario**: `sleap-nn` version mismatch between checkpoint and current environment
- **Mitigation**: Store `sleap_nn_version` in registry metadata; warn on version mismatch
- **Trade-off**: Warning only (not blocking) to allow manual intervention

### Trade-off: Local-Only Registry
- **Limitation**: Registry is per-worker, not shared across distributed workers
- **Benefit**: Simplicity, no network coordination, no consensus protocol needed
- **Future**: Can add registry sync protocol if multi-worker deployments become common

## Migration Plan

### Phase 1: Registry Infrastructure (Week 1)
1. Implement `ModelRegistry` class with core operations
2. Add unit tests for registry CRUD operations
3. Update worker to call `registry.register()` at training start
4. Verify registry creation and model entries

### Phase 2: Checkpoint Recovery (Week 1-2)
1. Add connection drop detection in `worker_class.py::on_iceconnectionstatechange()`
2. Implement `registry.mark_interrupted()` on connection loss
3. Query interrupted jobs on worker startup
4. Pass `resume_ckpt_path` to `sleap-nn train` if resuming
5. Test recovery with simulated connection drops

### Phase 3: CLI Integration (Week 2)
1. Add `sleap-rtc client list-models` command
2. Add `sleap-rtc client model-info <id>` command
3. Update `track` command to accept `--model <id>` alongside `--checkpoint`
4. Document CLI usage in README

### Rollback Plan
- Registry is opt-in; if disabled, worker falls back to current behavior
- No schema migrations needed (JSON is schema-free)
- Deleting `models/.registry/` disables feature entirely

### Backward Compatibility
- Existing `sleap-rtc` clients and workers continue to work
- Models trained without registry can still be used via direct path references
- No breaking changes to CLI arguments or WebRTC protocol

## Open Questions

1. **Should we support resuming from specific epochs?**
   - Current: Resume from `best.ckpt` only
   - Alternative: Support `last.ckpt` or epoch-specific checkpoints
   - Decision: Start with `best.ckpt` only; add epoch selection if users request it

2. **How to handle interrupted jobs when user wants fresh training?**
   - Option A: Always prompt user: "Resume interrupted training? [y/N]"
   - Option B: Add `--no-resume` flag to force fresh start
   - Option C: Auto-resume unless `--fresh` flag provided
   - **Recommendation**: Option B (prompt on reconnection, skip if `--no-resume` passed)

3. **Should registry track client-side model copies?**
   - Current: Registry is worker-only
   - Alternative: Client also maintains registry of downloaded models
   - Decision: Worker-only for now; client-side registry can be separate proposal

4. **How to handle model deletion?**
   - Registry entry remains even if checkpoint files deleted
   - Should `list-models` hide models with missing checkpoints?
   - **Recommendation**: Show all models but indicate `status: "checkpoint_missing"`

5. **Should we expose registry as HTTP API for remote queries?**
   - Use case: External tools querying available models
   - Complexity: Requires HTTP server on worker
   - Decision: CLI-only for now; HTTP API can be future enhancement
