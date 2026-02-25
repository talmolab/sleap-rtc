# Add Model Registry and Checkpoint Recovery

## Why

Remote training on workers currently lacks robust model lifecycle management. When models complete training, they are saved to directories named after the `run_name` (e.g., `models/centroid_251024_152308/`), but there is no systematic way to:

1. **Distinguish between models**: Multiple training runs create ambiguous directories like `centroid`, `centroid-1`, `centroid-2` with no metadata to differentiate them
2. **Recover from interruptions**: If the WebRTC connection drops during training, all progress is lost even though PyTorch Lightning saves checkpoints locally on the worker
3. **Reference models for inference**: Users need specific checkpoint paths for `sleap-nn track` commands but have no easy way to identify which model to use

This creates significant usability issues and wastes compute resources when training must restart from scratch after connection failures.

## What Changes

This proposal introduces a **model registry system** with **checkpoint recovery** capabilities:

### Model Registry
- Hash-based model identification using SHA256 of training configuration + dataset
- Local JSON-based registry (`models/.registry/manifest.json`) tracking all trained models
- Metadata storage including: model type, training job hash, completion status, metrics, timestamps, and checkpoint paths
- Registry operations: register, list, get info, mark completed/interrupted
- Human-readable model directory names combining type and short hash (e.g., `centroid_a3f5e8c9/`)

### Checkpoint Recovery
- Track training state (job ID, current model, last checkpoint, epoch progress) in registry
- Detect connection drops and mark models as "interrupted" with resumable checkpoint paths
- On reconnection, query registry for interrupted jobs and offer resumption
- Pass `trainer_config.resume_ckpt_path={checkpoint_path}` to `sleap-nn train` for seamless continuation
- Automatic transition from "interrupted" to "training" to "completed" status

### CLI Integration
- `sleap-rtc client list-models` - List all trained models with metadata
- `sleap-rtc client model-info <model-id>` - Show detailed model information
- `sleap-rtc client track --model <model-id>` - Use model by ID instead of path
- `sleap-rtc client train --resume <model-id>` - Resume interrupted training (future enhancement)

## Impact

### Affected Specs
- **NEW**: `model-registry` - Model lifecycle management and metadata tracking
- **NEW**: `checkpoint-recovery` - Interruption detection and training resumption

### Affected Code
- `sleap_rtc/worker/worker_class.py` - Integration of registry operations during training workflow
- `sleap_rtc/worker/model_registry.py` - **NEW** - Core registry implementation
- `sleap_rtc/cli.py` - **NEW** CLI commands for model management
- `sleap_rtc/client/client_track_class.py` - Model ID resolution for inference

### Breaking Changes
None. This is an additive feature that maintains backward compatibility with existing directory-based workflows.

### Dependencies
- Standard library only (`json`, `hashlib`, `pathlib`, `datetime`)
- No new external dependencies required

### Migration Path
Existing models in `models/` directory are not automatically registered. Users can continue using path-based references. Future enhancement could add `sleap-rtc client import-models` to register existing models retroactively.
