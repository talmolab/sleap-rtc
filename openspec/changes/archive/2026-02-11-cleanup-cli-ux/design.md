# Design: Training Log Streaming Improvements

## Problem

Current training output looks like this:
```
INFO:root:Client received: |---|
INFO:root:Client received: | 0 | model           | Model       | 1.3 M | train |    0 |
INFO:root:Client received: Trainable params: 1.3 M
INFO:root:Client received: Non-trainable params: 0
...
INFO:root:Client received: Sanity Checking: | 0/? [00:00<?, ?it/s]
INFO:root:Client received: Training: | 0/? [00:00<?, ?it/s]
INFO:root:Client received: Epoch 0:   0%|          | 0/100 [00:00<?, ?it/s]
INFO:root:Client received: Epoch 0:   1%|          | 1/100 [00:00<01:10, 1.40it/s]
INFO:root:Client received: Epoch 0:   1%|          | 1/100 [00:00<01:10, 1.40it/s, loss=0.0039]
```

**Issues:**
1. `INFO:root:Client received:` prefix on every line
2. tqdm progress bars rendered as multiple lines instead of updating in-place
3. Model summary tables broken across lines
4. No visual distinction between different log types

## Proposed Solution

### 1. Log Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│ Log Levels for CLI Output                                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│ --quiet (-q):     ERRORS only                                   │
│                   └── Connection failures, job failures         │
│                                                                 │
│ Default:          PROGRESS + WARNINGS + ERRORS                  │
│                   └── Epoch progress, validation metrics        │
│                   └── Path validation warnings                  │
│                   └── Connection errors                         │
│                                                                 │
│ --verbose (-v):   ALL (DEBUG + INFO + PROGRESS + WARN + ERROR)  │
│                   └── ICE state changes                         │
│                   └── Keep-alive messages                       │
│                   └── File transfer details                     │
│                   └── Full model summaries                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Log Message Classification

Worker-streamed logs will be classified into categories:

| Category | Pattern | Default Visibility |
|----------|---------|-------------------|
| SETUP_LOGS | Model summary, params, sanity check | ✅ Show (streaming) |
| PROGRESS | `Epoch \d+:`, progress bars | ✅ Show (in-place update) |
| METRICS | `loss=`, `val_loss=`, `accuracy=` | ✅ Show (with progress) |
| DEBUG | Keep-alive, ICE state, file transfer | ❌ Hide (--verbose only) |

**Key distinction:** Setup logs (model tables, sanity checking) stream normally as separate lines. Progress bars update in-place.

### 3. tqdm Progress Bar Handling

**Option A: Server-side parsing (Recommended)**

Worker parses tqdm output and sends structured progress:
```python
# Worker side
if is_tqdm_line(line):
    progress = parse_tqdm(line)  # {current: 5, total: 100, rate: "2.1it/s", metrics: {...}}
    channel.send(f"PROGRESS::{json.dumps(progress)}")
else:
    channel.send(f"LOG::{line}")
```

Client renders progress bar using rich or simple format:
```
Epoch 1/100 [████████░░░░░░░░░░░░]  42% | 42/100 | 2.1 it/s | loss=0.0034
```

**Option B: Client-side ANSI passthrough**

Worker sends raw ANSI escape codes, client terminal renders them.
- Simpler implementation
- Depends on terminal support
- May not work in all environments

**Recommendation:** Option A for better control and cross-platform support.

### 4. Structured Log Protocol

Extend the existing message protocol:

```
LOG::{level}::{message}      # General log with level
PROGRESS::{json}             # Structured progress update
TABLE_START::                # Begin table (buffer until TABLE_END)
TABLE_END::                  # End table, format and display
SECTION::{name}              # Visual section divider
```

### 5. Improved Output Format

**Default mode (no flags):**
```
Connecting to worker lab-gpu-1...
✓ Connected

Validating job specification...
✓ Paths verified

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Training centroid model
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

┌───────────────────────────────────────────────────────────────┐
│   │ Name                    │ Type             │ Params │
├───────────────────────────────────────────────────────────────┤
│ 0 │ model                   │ Model            │ 1.3 M  │
│ 1 │ instance_peaks_inf_layer│ FindInstancePeaks│ 0      │
└───────────────────────────────────────────────────────────────┘
Trainable params: 1.3 M
Non-trainable params: 0
Total params: 1.3 M

Sanity Checking DataLoader 0: 100% 1/1 [00:00<00:00, 3.32it/s]

Epoch 1/100 [████████░░░░░░░░░░░░]  42% | 42/100 | 2.1 it/s | loss=0.0034
                                                      ↑
                                        (this line updates in-place)
```

**Key behavior:**
- Setup logs (model table, params, sanity check) stream as normal lines
- Once epoch progress starts, progress bar updates in-place on single line
- Distinction: detect `Epoch \d+:` pattern to switch to in-place mode

**Verbose mode (-v):**
```
Connecting to worker lab-gpu-1...
  ICE connection state: checking
  ICE connection state: connected
✓ Connected

Validating job specification...
✓ Paths verified

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Training centroid model
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

... (same setup logs as default) ...

Epoch 1/100 [████████░░░░░░░░░░░░]  42% | loss=0.0034

Keep-alive received
Keep-alive received
...
```

**Quiet mode (-q):**
```
✓ Connected to lab-gpu-1
✓ Training started

Training complete. Best model: /vast/models/centroid/best.ckpt
```

## Implementation Approach

### Phase 1: Verbosity Flags
1. Add `--verbose/-v` and `--quiet/-q` to train/track commands
2. Configure logging level based on flags
3. Filter local logs (ICE, keep-alive, etc.)

### Phase 2: Log Prefix Cleanup
1. Remove `INFO:root:Client received:` prefix when displaying streamed logs
2. Just print the message content directly

### Phase 3: Structured Progress (Optional Enhancement)
1. Worker classifies and tags outgoing log lines
2. Client parses tags and formats appropriately
3. Implement progress bar rendering

## Alternatives Considered

1. **Use rich library for all output** - Heavy dependency, may conflict with existing logging
2. **Full TUI for training** - Too complex, changes user expectations
3. **Suppress all worker logs** - Loses useful debugging info

## Decision

Start with Phase 1 and 2 (verbosity flags + prefix removal) as they provide immediate value with minimal risk. Phase 3 (structured progress) can be a follow-up enhancement if needed.
