# Client-Side Model Registry and Transfer Protocol - Design Document

## Context

Building on the worker-side model registry from `add-model-registry`, users need client-side capabilities to manage models locally, use human-readable names, and transfer models between client and worker nodes. The current system only tracks models on the worker, making it difficult for users to:
- Know which models they have locally vs remotely
- Reference models with memorable names
- Import pre-trained models from other sources
- Share models across different workers

**Current State (after add-model-registry):**
- Worker has registry at `models/.registry/manifest.json`
- Models identified by 8-char hash (e.g., `a3f5e8c9`)
- Training automatically registers models on worker
- No client-side tracking or transfer capabilities

**Stakeholders:**
- End users who train and use models for inference
- Users with pre-trained models from other sources
- Users working with multiple workers
- Users who want memorable model names

## Goals / Non-Goals

### Goals
1. **Client Registry**: Local tracking of downloaded and imported models with sync status
2. **Human-Friendly Names**: Alias system for memorable model references
3. **Model Discovery**: Query worker registries via WebRTC without filesystem access
4. **Bidirectional Transfer**: Upload local models to workers, download worker models to client
5. **Seamless Integration**: All existing CLI commands work with aliases transparently

### Non-Goals
- Cloud storage or remote backup of models (local/worker only)
- Automatic model synchronization (manual push/pull)
- Multi-worker model federation (future enhancement)
- Model versioning or Git-like branching (future enhancement)
- Automatic model cleanup or retention policies

## Decisions

### 1. Client Registry Storage: JSON at ~/.sleap-rtc/models/manifest.json

**Decision:** Use same JSON format as worker registry, stored in user home directory.

**Rationale:**
- **Consistency**: Same structure as worker registry reduces complexity
- **User-Specific**: `~/.sleap-rtc/` is conventional for CLI tool data
- **Cross-Session**: Persists across terminal sessions and project directories
- **Portable**: User can backup/restore by copying directory
- **No Conflicts**: Per-user isolation prevents multi-user conflicts on shared systems

**Structure:**
```json
{
  "version": "1.0",
  "models": {
    "a3f5e8c9": {
      "id": "a3f5e8c9",
      "model_type": "centroid",
      "alias": "good-mouse-v1",
      "source": "worker-training",
      "downloaded_at": "2025-11-10T14:30:50Z",
      "local_path": "~/.sleap-rtc/models/centroid_a3f5e8c9/",
      "checkpoint_path": "~/.sleap-rtc/models/centroid_a3f5e8c9/best.ckpt",
      "on_worker": true,
      "worker_last_seen": "2025-11-10T14:30:45Z",
      "worker_path": "models/centroid_a3f5e8c9/",
      "metrics": {
        "final_val_loss": 0.0234,
        "epochs_completed": 5
      }
    }
  },
  "aliases": {
    "good-mouse-v1": "a3f5e8c9"
  }
}
```

**Alternatives Considered:**
- Project-local registry (`./.sleap-rtc/models/`): Confusing when working across projects
- SQLite database: Overkill for simple key-value storage
- Separate alias file: Adds complexity with two files to keep in sync

### 2. Alias System: Global Namespace with Collision Detection

**Decision:** Aliases are unique per registry (client or worker), with automatic collision detection and user prompts.

**Rationale:**
- **Simplicity**: One alias → one model, no ambiguity
- **User Control**: System prompts on collision, user decides resolution
- **Searchable**: Fast O(1) lookup via separate `aliases` dict
- **Mutable**: Users can rename aliases (unlike immutable IDs)

**Collision Handling:**
```python
def set_alias(model_id: str, alias: str) -> bool:
    """Set alias for model, handling collisions."""
    if alias in self.aliases and self.aliases[alias] != model_id:
        existing_id = self.aliases[alias]
        print(f"Alias '{alias}' already used by model {existing_id}")
        choice = prompt("Overwrite? [y/N]: ")
        if choice.lower() != 'y':
            return False

    self.aliases[alias] = model_id
    self.models[model_id]["alias"] = alias
    return True
```

**Alternatives Considered:**
- Scoped aliases (per-project): Users would need to re-alias in each project
- Multiple aliases per model: Adds complexity, unclear primary name
- Automatic numbering (good-mouse-v1, good-mouse-v2): Requires version tracking

### 3. Model Transfer Protocol: WebRTC Data Channels with Chunked Transfer

**Decision:** Use existing RTC data channel infrastructure with new message types for registry queries and model transfer.

**Rationale:**
- **Reuses Infrastructure**: Leverages existing chunked file transfer code
- **No New Ports**: Works within established WebRTC connection
- **Firewall Friendly**: Same NAT traversal as existing system
- **Bidirectional**: Same channel for push and pull operations

**Protocol Messages:**
```python
# Registry Query Messages
{
    "type": "registry_query",
    "command": "list_models",
    "filters": {"status": "completed", "model_type": "centroid"}
}

{
    "type": "registry_response",
    "models": [
        {"id": "a3f5e8c9", "model_type": "centroid", "alias": "good-mouse-v1", ...}
    ]
}

# Model Transfer Messages
{
    "type": "model_transfer",
    "command": "push",
    "model_id": "a3f5e8c9",
    "model_type": "centroid",
    "files": {
        "best.ckpt": {"size": 91234567, "chunks": 1394},
        "training_config.yaml": {"size": 2048, "chunks": 1}
    }
}

# Chunked File Data (reuses existing CHUNK_SIZE=64KB)
{
    "type": "model_file_chunk",
    "model_id": "a3f5e8c9",
    "filename": "best.ckpt",
    "chunk_index": 0,
    "total_chunks": 1394,
    "data": "<base64-encoded-bytes>"
}

{
    "type": "model_transfer_complete",
    "model_id": "a3f5e8c9",
    "status": "success"
}
```

**Flow for Push (Client → Worker):**
1. Client: Send `model_transfer` with file manifest
2. Worker: Validate space, respond with "ready"
3. Client: Stream chunks via `model_file_chunk` messages
4. Worker: Reassemble files, validate checksums, register model
5. Worker: Send `model_transfer_complete`

**Flow for Pull (Worker → Client):**
1. Client: Send `model_transfer` with `command: "pull"`
2. Worker: Load model files, send manifest
3. Worker: Stream chunks to client
4. Client: Reassemble, validate, register locally
5. Client: Send acknowledgment

**Alternatives Considered:**
- HTTP API for transfers: Requires additional port, more complex firewall rules
- FTP/SCP: Requires separate credentials, not firewall-friendly
- Separate WebSocket: Unnecessary complexity, duplicate connection management

### 4. Model Import: Path-Based with Auto-Detection

**Decision:** Import command accepts directory path, auto-detects model type from config file, prompts for alias.

**Rationale:**
- **User-Friendly**: Single command for any model directory
- **Flexible**: Works with various checkpoint formats (.ckpt, .h5)
- **Safe**: Validates files exist before importing
- **Metadata Preservation**: Reads training_config.yaml if present

**Import Flow:**
```bash
$ sleap-rtc client import-model ~/my-models/old_centroid/ --alias legacy-2023

# System:
# 1. Validates directory exists
# 2. Searches for checkpoint files (best.ckpt, *.ckpt, *.h5)
# 3. Reads training_config.yaml if present (extract model_type)
# 4. Prompts for model_type if not found
# 5. Generates model_id from config (or uses random if unknown)
# 6. Prompts for alias if not provided
# 7. Creates symlink or copies to ~/.sleap-rtc/models/{type}_{id}/
# 8. Registers in client registry
```

**Copy vs Symlink:**
- Default: **Symlink** (preserves disk space, keeps original location)
- Option: `--copy` flag to duplicate files (safer for ephemeral sources)

**Alternatives Considered:**
- Automatic scanning: Too invasive, users should explicitly import
- In-place registration: Breaks if user moves original directory
- Mandatory metadata: Too restrictive, some models lack configs

### 5. Synchronization Strategy: Manual with Status Tracking

**Decision:** Client registry tracks `on_worker: true/false` and `worker_last_seen` timestamp, but does not auto-sync.

**Rationale:**
- **Explicit Control**: Users decide when to push/pull
- **Bandwidth Conscious**: Avoids unexpected large transfers
- **Conflict Avoidance**: No automatic overwrites or merges
- **Simple Logic**: Clear ownership (local vs worker vs both)

**Status Tracking:**
```python
# After training on worker
{
    "on_worker": true,
    "worker_last_seen": "2025-11-10T14:30:45Z",
    "local": true  # if downloaded
}

# After push to worker
{
    "on_worker": true,
    "worker_last_seen": "2025-11-10T15:20:10Z",
    "local": true
}

# After local import (not yet pushed)
{
    "on_worker": false,
    "worker_last_seen": null,
    "local": true
}
```

**List Output Shows Location:**
```
╭───────────┬──────────────────┬────────────┬──────────────╮
│ ID/Alias  │ Type             │ Location   │ Loss         │
├───────────┼──────────────────┼────────────┼──────────────┤
│ a3f5e8c9  │ centroid         │ local +    │ 0.0234       │
│ good-m... │                  │ worker     │              │
├───────────┼──────────────────┼────────────┼──────────────┤
│ 7f2a1b3c  │ centroid         │ local only │ unknown      │
│ legacy... │                  │            │              │
╰───────────┴──────────────────┴────────────┴──────────────╯
```

**Alternatives Considered:**
- Auto-sync on connect: Expensive, unpredictable bandwidth usage
- Differential sync: Complex, requires version tracking
- Cloud-based sync: Out of scope, requires external service

### 6. Enhanced Metadata: Optional Extended Fields

**Decision:** Add optional metadata fields for training hyperparameters, versioning, and user notes.

**Fields Added:**
```json
{
  "id": "a3f5e8c9",
  "alias": "good-mouse-v1",
  "training_hyperparameters": {
    "learning_rate": 0.001,
    "batch_size": 4,
    "optimizer": "Adam",
    "max_epochs": 5
  },
  "sleap_nn_version": "1.2.3",
  "git_commit": "abc123def",
  "tags": ["mouse", "production", "validated"],
  "notes": "Best performing model for C57BL/6 mice, validated 2025-11-10"
}
```

**Rationale:**
- **Optional**: Old models without metadata still work
- **Extensible**: Easy to add new fields without breaking changes
- **Searchable**: Can filter by tags in list commands
- **Auditable**: Git commit + version enables reproducibility

**Population:**
- Automatically extracted from training_config.yaml during training
- Manually added via `sleap-rtc client update-model <id> --notes "..."`
- Imported models have minimal metadata (can be added later)

## Risks / Trade-offs

### Risk: Alias Conflicts Between Users
- **Scenario**: User A names model "good-model", User B imports model with same alias
- **Mitigation**: Aliases are per-client registry (no cross-user conflicts)
- **Trade-off**: Different users may use different aliases for same model ID

### Risk: Registry Desynchronization
- **Scenario**: Model deleted on worker but client registry still shows `on_worker: true`
- **Mitigation**:
  - Worker queries return 404 if model missing, client updates status
  - `sleap-rtc client sync` command to reconcile state
- **Trade-off**: Manual sync required, not real-time

### Risk: Large Model Transfer Failures
- **Scenario**: 500MB model transfer interrupted mid-transfer
- **Mitigation**:
  - Chunked transfer with resume capability
  - Checksum validation on completion
  - Atomic file operations (temp file + rename)
- **Trade-off**: Extra disk space during transfer (temp files)

### Risk: Import Path Changes
- **Scenario**: User imports model via symlink, then moves original directory
- **Mitigation**:
  - Default to symlink but offer `--copy` option
  - Validate path on use, warn if missing
  - `sleap-rtc client repair-model <id>` command to fix broken paths
- **Trade-off**: Some models may become "orphaned" if source moved

### Trade-off: Manual vs Automatic Synchronization
- **Limitation**: Users must explicitly push/pull models
- **Benefit**: Predictable bandwidth, explicit control, no conflicts
- **Future**: Could add `--auto-sync` flag for power users

## Migration Plan

### Phase 1: Client Registry Core (Week 1)
1. Implement `ClientModelRegistry` class with CRUD operations
2. Create `~/.sleap-rtc/models/` directory on first use
3. Add alias management methods
4. Unit tests for registry operations

### Phase 2: Import and Local Management (Week 1-2)
1. Implement `import-model` command with auto-detection
2. Implement `tag-model` command for aliasing
3. Add `list-models` with location status display
4. Add `model-info` with detailed view
5. Implement `compare-models` functionality

### Phase 3: WebRTC Protocol (Week 2-3)
1. Add RTC message handlers for registry queries
2. Implement worker-side query endpoints
3. Add model file packaging for transfer
4. Implement chunked transfer with resume
5. Add checksum validation

### Phase 4: Push/Pull Commands (Week 3-4)
1. Implement `push-model` command (client → worker)
2. Implement `pull-model` command (worker → client)
3. Add progress bars for transfers
4. Implement automatic registration on both sides
5. Update existing `track` command to resolve aliases

### Phase 5: Integration and Polish (Week 4)
1. Update training flow to auto-register on client after download
2. Add sync status tracking
3. Implement `sync` command for reconciliation
4. Add comprehensive error handling
5. Update documentation and examples

### Rollback Plan
- Client registry is opt-in; deleting `~/.sleap-rtc/` disables feature
- All commands degrade to path-based references if registry missing
- Worker queries return empty if base registry not implemented
- No breaking changes to existing workflows

### Backward Compatibility
- Existing model references by path continue to work
- Commands accept both IDs and aliases (alias lookup is best-effort)
- Worker registry works independently if client registry not used
- All new commands are additive (no modified existing commands)

## Open Questions

1. **Should aliases be shared across client and worker?**
   - Current: Client and worker have independent alias namespaces
   - Alternative: Sync aliases during model transfer
   - **Recommendation**: Start independent, add sync if users request

2. **How to handle model updates (re-training same config)?**
   - Option A: Create new model ID with version suffix
   - Option B: Allow overwriting with confirmation
   - Option C: Keep both with timestamps
   - **Recommendation**: Option A (new ID, user can alias both)

3. **Should transfer support differential sync (only changed files)?**
   - Use case: Large models with small config changes
   - Complexity: Requires file-level diffing and checksums
   - **Recommendation**: Full transfer for now, optimize later if needed

4. **How to handle multi-worker scenarios?**
   - Current: Client tracks `on_worker: true` (binary)
   - Alternative: Track multiple worker IDs: `on_workers: ["worker-1", "worker-2"]`
   - **Recommendation**: Start simple (binary), extend if multi-worker common

5. **Should import support batch operations?**
   - Use case: Import directory with 10+ models at once
   - Command: `sleap-rtc client import-models ~/models/* --prefix legacy-`
   - **Recommendation**: Add if users have bulk import needs

6. **Should there be a "model marketplace" or sharing feature?**
   - Use case: Share validated models with colleagues
   - Requires: Authentication, access control, model provenance
   - **Recommendation**: Out of scope, future proposal if needed
