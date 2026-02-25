# Proposal: cleanup-cli-ux

## Summary

Clean up the CLI user experience by removing deprecated log messages, adding verbosity controls, introducing credential/config management subcommands, and improving training log streaming presentation.

## Motivation

Based on investigation `scratch/2025-02-10-train-track-cli-review/`, several UX issues were identified:

1. **Deprecated log messages** - References to DynamoDB, Cognito, and legacy room tokens clutter output
2. **No verbosity control** - All INFO-level logs shown by default (keep-alive, ICE state, file transfers)
3. **No credential/config management** - Users must manually edit JSON/TOML files to view or modify settings
4. **Poor training log presentation** - Raw `INFO:root:Client received:` prefixes make logs hard to read (see investigation screenshot)

## Scope

### In Scope

1. **Remove deprecated messages**
   - Remove "Cleaning up DynamoDB entries..." logs (5 occurrences)
   - Remove "Cleaning up Cognito..." logs
   - Update CLI help text referencing legacy `--token` patterns

2. **Add verbosity flags**
   - Add `--verbose/-v` flag to train/track commands (show all logs)
   - Add `--quiet/-q` flag (show only errors and progress)
   - Default: show progress + warnings + errors

3. **Credential management subcommand**
   - `sleap-rtc credentials list` - Show stored rooms, tokens, secrets (redacted)
   - `sleap-rtc credentials show` - Show full credentials.json path and contents
   - `sleap-rtc credentials clear` - Clear all credentials (with confirmation)
   - `sleap-rtc credentials remove-secret --room X` - Remove specific room secret
   - `sleap-rtc credentials remove-token --room X` - Remove specific API token

4. **Config management subcommand**
   - `sleap-rtc config show` - Show current merged config (TOML sources)
   - `sleap-rtc config path` - Show config file locations
   - `sleap-rtc config add-mount PATH LABEL` - Add mount point interactively
   - `sleap-rtc config remove-mount LABEL` - Remove mount point

5. **Training log streaming improvements**
   - Remove `INFO:root:Client received:` prefix from streamed logs
   - Parse and format tqdm progress bars properly
   - Distinguish training progress (epoch/loss) from model info dumps
   - Add visual separation between log sections

### Out of Scope

- GUI authentication integration (separate proposal)
- Python API for programmatic access (separate proposal)
- Additional track CLI options (separate proposal)

## Dependencies

- None - this is a standalone UX improvement

## Risks

- **Low risk**: Changes are additive (new flags, new commands) or cosmetic (log formatting)
- **Migration**: Deprecated log messages may be expected by scripts parsing output (low likelihood)
