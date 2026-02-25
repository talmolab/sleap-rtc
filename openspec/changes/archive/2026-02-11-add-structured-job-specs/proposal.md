# Proposal: Add Structured Job Specifications

## Summary

Replace shell script-based job execution with structured job specifications that map directly to sleap-nn CLI, enabling users to train and track with regular `.slp` files and config YAMLs on shared storage.

## Motivation

Currently, `sleap-rtc train` requires:
1. A `.pkg.slp` file with embedded frames
2. A pre-baked `train-script.sh` inside the package
3. No ability to customize sleap-nn CLI flags

This creates friction for users who:
- Have regular `.slp` files with external videos on shared storage
- Want to use configs exported from SLEAP GUI or written for sleap-nn
- Need to adjust training parameters without re-exporting packages

The sleap-nn CLI supports flexible training via:
```bash
sleap-nn train --config-name centroid.yaml --config-dir /path/to/configs
```

sleap-rtc should provide equivalent flexibility for remote training.

## Goals

1. **Minimal friction**: CLI should feel like running `sleap-nn train` locally, just with `--room` added
2. **Security**: No shell injection possible - structured command building only
3. **Path correction**: Interactive directory browser when paths are invalid
4. **Backward compatibility**: Existing `--pkg-path` workflow continues to work
5. **GUI-ready**: Architecture supports future SLEAP GUI integration

## Non-Goals

- Full sleap-nn CLI parity in v1 (start with common flags, add more incrementally)
- TUI job configuration screen (CLI-first for v1)
- Python API extraction (let CLI stabilize first)
- Non-shared filesystem support (requires file transfer, defer)

## Design

### Assumptions

- Both client and worker have access to the same shared filesystem (e.g., `/vast`)
- Config and data files are on shared storage
- No file transfer needed (unlike `.pkg.slp` workflow)

### New CLI Interfaces

**Training:**
```bash
sleap-rtc train --room ROOM \
  --config /path/to/config.yaml \        # Required: config on shared storage
  [--labels /path/to/labels.slp] \       # Override train_labels_path in config
  [--val-labels /path/to/val.slp] \      # Override val_labels_path in config
  [--max-epochs N] \
  [--batch-size N] \
  [--learning-rate F] \
  [--run-name NAME] \
  [--resume /path/to/checkpoint.ckpt]
```

**Inference:**
```bash
sleap-rtc track --room ROOM \
  --data-path /path/to/data.slp \        # Required
  --model-paths /path/to/model1 \        # Required (can repeat)
  [--output /path/to/predictions.slp] \
  [--batch-size N] \
  [--peak-threshold F] \
  [--only-suggested-frames] \
  [--frames "0-100,200-300"]
```

### Structured Job Specifications

Jobs are submitted as validated JSON structures instead of shell scripts:

```python
@dataclass
class TrainJobSpec:
    config_path: str                    # Full path to config YAML
    labels_path: Optional[str]          # Override train_labels_path
    val_labels_path: Optional[str]      # Override val_labels_path
    max_epochs: Optional[int]
    batch_size: Optional[int]
    learning_rate: Optional[float]
    run_name: Optional[str]
    resume_ckpt_path: Optional[str]
```

### Path Validation & Interactive Correction

1. Worker validates all paths exist and are within allowed mounts
2. If paths are invalid (including `--labels` path), worker returns `JOB_REJECTED` with details
3. Client prompts user to correct via CLI directory browser
4. Path correction is a **fallback** - user should provide correct paths via flags

### CLI Directory Browser

When path validation fails, an interactive browser allows correction:

```
Error: Labels file not found: /vast/project/labesl.slp

Select correct labels file:
  Current: /vast/project/

  ..                          [parent]
  configs/                    [dir]
> labels.slp                  (2.3 MB)
  old_labels.slp              (1.8 MB)
  videos/                     [dir]

[↑/↓] Navigate  [Enter] Select/Open  [Backspace] Back  [Esc] Cancel
```

### Security Model

| Concern | Mitigation |
|---------|------------|
| Path traversal | All paths validated against allowed mounts, resolved |
| Command injection | No shell execution - structured command building |
| Parameter tampering | Strict type validation + range constraints |
| Arbitrary execution | Only sleap-nn commands, allowlisted parameters |

## Capabilities Affected

### New Capabilities

- **job-specification**: Structured job spec data types, validation, and command building
- **cli-job-submission**: New CLI flags for train/track commands
- **cli-directory-browser**: Interactive path correction in CLI

### Modified Capabilities

- **worker-job-execution**: Execute from JobSpec instead of shell scripts
- **cli**: New flags, backward compatibility with `--pkg-path`

## Risks

1. **Config path issues**: Users may have configs with local paths that don't work on worker
   - Mitigation: `--labels` and `--val-labels` flags override config paths

2. **Breaking changes**: Changing CLI interface could break scripts
   - Mitigation: Full backward compatibility, `--pkg-path` still works

3. **Scope creep**: Full sleap-nn parity is large
   - Mitigation: v1 has common flags only, add more incrementally
