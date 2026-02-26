# Add Client-Side Model Registry and Transfer Protocol

## Why

The existing `add-model-registry` proposal provides worker-side model tracking, but users need additional capabilities for a complete model lifecycle management experience:

1. **Client-side visibility**: Users cannot see which models they have downloaded locally without manually checking filesystem directories
2. **Model discovery**: No easy way to query what models are available on a worker before connecting or without SSH access
3. **Human-friendly references**: Hash-based model IDs (e.g., `a3f5e8c9`) are not memorable or meaningful to users
4. **Pre-trained model integration**: Users with models trained elsewhere have no way to import them into the system for use with workers
5. **Model distribution**: No mechanism to upload existing models to workers or download worker models to local machines

This proposal extends the model registry with client-side tracking, human-readable aliases, and bidirectional model transfer capabilities, creating a complete model management ecosystem.

## What Changes

This proposal introduces three major feature sets that build on the base `add-model-registry` proposal:

### 1. Client-Side Model Registry
- Local JSON-based registry at `~/.sleap-rtc/models/manifest.json` tracking downloaded and imported models
- Synchronization with worker registry state (tracking which models exist on which workers)
- Local model storage at `~/.sleap-rtc/models/{model_type}_{model_id}/`
- Metadata tracking: download timestamps, source (worker/local import), availability status

### 2. Model Aliases and Enhanced Metadata
- User-assignable human-readable aliases for models (e.g., `good-mouse-v1`, `legacy-rat-2023`)
- Support for aliases on both client and worker registries
- Alias resolution in all CLI commands (use alias instead of model ID)
- Additional metadata: user notes, tags, training hyperparameters, sleap-nn version
- Model comparison functionality to evaluate multiple models side-by-side

### 3. Model Transfer Protocol (WebRTC)
- **Worker Query Protocol**: RTC messages for clients to query worker registry without file system access
  - `list_models`: Get all models on worker with filters
  - `get_model_info`: Get detailed metadata for specific model
  - `check_model_exists`: Verify model availability by ID or alias
- **Model Upload (push)**: Client sends pre-trained model to worker
  - Package model checkpoint + config into transferable format
  - Upload via RTC data channel with chunked transfer
  - Register on worker with source="client-upload"
- **Model Download (pull)**: Client downloads worker model
  - Query worker for model by ID/alias
  - Transfer checkpoint files via RTC data channel
  - Register locally with source="worker-pull"

### 4. CLI Commands
- `sleap-rtc client list-models` - List local models with worker availability status
- `sleap-rtc client import-model <path> --alias <name>` - Import pre-trained model to local registry
- `sleap-rtc client push-model <model-id> --worker <session>` - Upload model to worker
- `sleap-rtc client pull-model <model-id> --worker <session>` - Download model from worker
- `sleap-rtc client tag-model <model-id> <alias>` - Assign alias to model
- `sleap-rtc client model-info <model-id>` - Show detailed model information
- `sleap-rtc client compare-models <model-id> [<model-id> ...]` - Compare multiple models
- `sleap-rtc worker list-models --session <token>` - Query worker registry from client
- Enhanced `track` command: `--model <alias>` works with aliases and auto-resolves

## Impact

### Affected Specs
- **NEW**: `client-model-registry` - Client-side model tracking and synchronization
- **NEW**: `model-aliases` - Human-readable model naming and resolution
- **NEW**: `model-transfer-protocol` - WebRTC-based model upload/download
- **MODIFIED**: `model-registry` (from base proposal) - Add alias field and extended metadata
- **MODIFIED**: CLI commands - Add model management commands

### Affected Code
- `sleap_rtc/client/client_model_registry.py` - **NEW** - Client registry implementation
- `sleap_rtc/worker/worker_class.py` - Add RTC message handlers for registry queries and model transfer
- `sleap_rtc/client/client_class.py` - Add model push/pull methods
- `sleap_rtc/cli.py` - Add new model management commands
- `sleap_rtc/client/client_track_class.py` - Update to resolve aliases
- `sleap_rtc/worker/model_registry.py` - Add alias support and extended metadata (extends base proposal)
- `sleap_rtc/models/` - **NEW** directory for shared model metadata schemas

### Breaking Changes
None. This is fully additive and backward compatible:
- Works with or without base `add-model-registry` (degrades gracefully)
- Existing path-based model references continue to work
- All new commands are opt-in

### Dependencies
- **Prerequisite**: `add-model-registry` proposal must be implemented first (worker-side registry)
- **External**: Standard library only (`json`, `hashlib`, `pathlib`, `shutil`)
- **Internal**: Uses existing RTC data channel infrastructure for file transfer

### Migration Path
1. Phase 1: Implement base `add-model-registry` (worker-side)
2. Phase 2: Implement client registry and aliases (this proposal)
3. Phase 3: Add transfer protocol and CLI commands
4. Existing users automatically get client registry on first model download/train
5. Pre-existing downloaded models can be imported retroactively via `import-model` command

## Dependencies and Sequencing

**MUST be implemented after:**
- `add-model-registry` - Provides worker-side registry infrastructure

**Can be implemented in parallel with:**
- `add-client-room-connection` - Independent features

**Enables future proposals:**
- Model versioning and A/B testing
- Multi-worker model federation
- Cloud storage integration for models
