## Context

The SLEAP GUI integration (PR #45) added widgets, API, and presubmission stubs. The missing piece is: when the user clicks "Run Remotely", the training config must travel over WebRTC (not shared filesystem) and all paths must be validated on the worker before the job is submitted.

Currently:
- `TrainJobSpec.config_path` points to a filesystem path the worker reads directly
- The CLI workflow assumes shared storage for both configs and data
- The GUI presubmission.py has stubs for auth/config/path checks but passes `config_path`

The GUI workflow differs: the config is built in-memory from the dialog form and should be sent inline over the datachannel.

## Goals / Non-Goals

**Goals:**
- Send training config as inline content over WebRTC datachannel
- Validate SLP and video paths on the worker before submission
- Show PathResolutionDialog when paths are missing
- Keep the dialog open until all checks pass or user cancels
- Clean up temp config files on the worker after job completion

**Non-Goals:**
- Changing the CLI workflow (it continues to use `config_path` on shared storage)
- Adding new path resolution strategies (existing mount alias + filename search is sufficient)
- Modifying the signaling server or WebRTC protocol

## Decisions

### Decision 1: `config_content` as optional field on TrainJobSpec

Add `config_content: Optional[str] = None` to `TrainJobSpec`. When present, the worker writes it to a temp file and uses that as the config. The existing `config_path`/`config_paths` fields remain for CLI use.

**Alternatives considered:**
- Separate `GUITrainJobSpec` subclass — rejected: unnecessary duplication, same validation/execution logic applies
- Always write config to shared storage first — rejected: defeats the purpose; GUI client may not have shared storage access for configs

### Decision 2: Worker writes config_content to temp file

The worker writes `config_content` to `tempfile.NamedTemporaryFile(suffix='.yaml')` in its working directory, sets `config_paths = [temp_path]`, then continues with the existing validation and execution flow. Cleanup happens in a `finally` block.

**Why temp file:** sleap-nn expects a config file path argument. Writing to temp is simpler and more reliable than modifying sleap-nn to accept inline config.

### Decision 3: Presubmission runs synchronously on Run click

The presubmission flow runs when the user clicks "Run Remotely". Each step blocks the dialog (with a progress indicator). If any step fails or is cancelled, the dialog stays open.

**Alternatives considered:**
- Eager validation (check paths when room/worker selected) — rejected per design brainstorm: wastes resources, paths may change between selection and run
- Background validation — rejected: adds complexity for little benefit since the user is waiting anyway

## Risks / Trade-offs

- **Large config strings over datachannel**: Training configs are typically <100KB YAML, well within datachannel limits (64KB chunks already supported). No risk for normal usage.
- **Temp file cleanup on crash**: If the worker process crashes, temp files won't be cleaned up. Mitigation: use the system temp directory which is cleaned on reboot.
- **Validation requires existing `__post_init__`**: Need `config_paths OR config_content` validation without breaking existing specs that only provide `config_paths`.

## Open Questions

None — all design decisions were resolved during the brainstorming session (see docs/plans/2026-02-12-presubmission-flow-design.md).
