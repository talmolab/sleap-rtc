# Tasks: cleanup-cli-ux

## Phase 1: Remove Deprecated Messages and Legacy References

### Task 1.1: Remove DynamoDB/Cognito log messages
- [ ] Remove `logging.info("Cleaning up DynamoDB entries...")` from:
  - `sleap_rtc/client/client_class.py:259`
  - `sleap_rtc/client/client_class.py:2454`
  - `sleap_rtc/client/client_track_class.py:276`
  - `sleap_rtc/client/client_track_class.py:648`
  - `sleap_rtc/worker/worker_class.py:237`
- [ ] Remove or update any "Cognito" references in log messages
- [ ] Verify no functional code depends on these messages

**Validation:** `rg -n "DynamoDB|Cognito" sleap_rtc/` returns no logging statements

### Task 1.2: Remove legacy room token references
- [ ] Remove `--token` flag from CLI commands (train, track, worker, browse)
- [ ] Remove room token handling code from client and worker
- [ ] Update CLI help text to remove `--token` examples
- [ ] Remove `room_token` references from worker output messages
- [ ] Update any documentation referencing room tokens

**Note:** Room tokens are superseded by worker API keys (`--api-key`). API keys are the only supported worker authentication method.

**Validation:**
- `rg -n "room.*token|--token" sleap_rtc/cli.py` returns no hits (except possibly in deprecation warnings)
- `sleap-rtc train --help` does not show `--token` option
- `sleap-rtc worker --help` does not show `--token` option

---

## Phase 2: Add Verbosity Flags

### Task 2.1: Add --verbose and --quiet flags to train command
- [ ] Add `--verbose/-v` flag to `train` command in `cli.py`
- [ ] Add `--quiet/-q` flag to `train` command in `cli.py`
- [ ] Implement mutual exclusion (can't use both)
- [ ] Pass verbosity setting to client

**Validation:** `sleap-rtc train --help` shows new flags

### Task 2.2: Add --verbose and --quiet flags to track command
- [ ] Add same flags to `track` command
- [ ] Reuse verbosity logic from train

**Validation:** `sleap-rtc track --help` shows new flags

### Task 2.3: Implement log filtering in client
- [ ] Create log level configuration based on verbosity flag
- [ ] Filter keep-alive messages in non-verbose mode
- [ ] Filter ICE state messages in non-verbose mode
- [ ] Filter file transfer details in non-verbose mode
- [ ] Always show errors and progress

**Validation:** Run `sleap-rtc train -q` and verify minimal output; run `-v` and verify detailed output

### Task 2.4: Add verbosity flag to worker command
- [ ] Add `--verbose/-v` flag to `worker` command
- [ ] Filter worker-side logs based on flag

**Validation:** `sleap-rtc worker --help` shows new flag

---

## Phase 3: Clean Up Log Streaming Display

### Task 3.1: Remove INFO:root:Client received: prefix
- [ ] Identify where streamed logs are printed to terminal
- [ ] Strip `INFO:root:Client received:` prefix before display
- [ ] Print raw message content

**Validation:** Training output no longer shows `INFO:root:Client received:` prefix

### Task 3.2: Add visual structure to training output
- [ ] Add "Connecting to worker..." status message
- [ ] Add "Training started" section header
- [ ] Add visual separator between phases (connecting, validating, training)

**Validation:** Training output has clear visual sections

---

## Phase 4: Credential Management Commands

### Task 4.1: Add `sleap-rtc credentials list` command
- [ ] Create `credentials` command group in `cli.py`
- [ ] Implement `list` subcommand showing:
  - Logged in user (if any)
  - Rooms with saved secrets (redacted)
  - Rooms with saved tokens (redacted)
- [ ] Format output as readable table

**Validation:** `sleap-rtc credentials list` shows stored credentials

### Task 4.2: Add `sleap-rtc credentials show` command
- [ ] Implement `show` subcommand displaying:
  - Credentials file path
  - Full contents (with option to redact secrets)
- [ ] Add `--reveal` flag to show full secrets

**Validation:** `sleap-rtc credentials show` displays file contents

### Task 4.3: Add `sleap-rtc credentials clear` command
- [ ] Implement `clear` subcommand
- [ ] Add confirmation prompt before clearing
- [ ] Add `--yes` flag to skip confirmation

**Validation:** `sleap-rtc credentials clear --yes` removes credentials file

### Task 4.4: Add credential removal commands
- [ ] Implement `sleap-rtc credentials remove-secret --room ROOM`
- [ ] Implement `sleap-rtc credentials remove-token --room ROOM`
- [ ] Update credentials.json without affecting other entries

**Validation:** Can remove specific room secrets/tokens

---

## Phase 5: Config Management Commands

### Task 5.1: Add `sleap-rtc config show` command
- [ ] Create `config` command group in `cli.py`
- [ ] Implement `show` subcommand displaying:
  - Merged config from all sources
  - Source file for each setting
- [ ] Add `--json` flag for machine-readable output

**Validation:** `sleap-rtc config show` displays current config

### Task 5.2: Add `sleap-rtc config path` command
- [ ] Implement `path` subcommand showing:
  - CWD config path (`./sleap-rtc.toml`)
  - Home config path (`~/.sleap-rtc/config.toml`)
  - Which files exist

**Validation:** `sleap-rtc config path` shows config locations

### Task 5.3: Add mount management commands
- [ ] Implement `sleap-rtc config add-mount PATH LABEL`
  - Add mount to appropriate config file
  - Create config file if needed
- [ ] Implement `sleap-rtc config remove-mount LABEL`
  - Remove mount from config file
- [ ] Add `--global` flag to modify home config vs CWD config

**Validation:** Can add/remove mounts via CLI

---

## Phase 6: Documentation & Tests

### Task 6.1: Update CLI documentation
- [ ] Update README with new commands
- [ ] Add examples for verbosity flags
- [ ] Add examples for credential/config management

### Task 6.2: Add tests for new commands
- [ ] Test verbosity flag parsing
- [ ] Test credential list/show/clear commands
- [ ] Test config show/path commands
- [ ] Test mount add/remove commands

**Validation:** `pytest tests/test_cli.py` passes

---

## Parallel Work

Tasks that can be done in parallel:
- Phase 1 (deprecated messages) + Phase 2 (verbosity flags)
- Phase 4 (credentials) + Phase 5 (config) - independent command groups
- Phase 3 (log streaming) depends on Phase 2 (verbosity infrastructure)

## Priority Order

1. **High Priority (immediate UX win):**
   - Task 1.1: Remove deprecated messages
   - Task 3.1: Remove INFO:root prefix
   - Task 2.1-2.3: Verbosity flags

2. **Medium Priority (useful additions):**
   - Task 4.1-4.2: Credentials list/show
   - Task 5.1-5.2: Config show/path

3. **Lower Priority (nice to have):**
   - Task 4.3-4.4: Credentials clear/remove
   - Task 5.3: Mount management
   - Task 3.2: Visual structure
