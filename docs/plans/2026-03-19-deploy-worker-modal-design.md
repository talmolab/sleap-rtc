# Deploy Worker Modal Design

**Date:** 2026-03-19
**Goal:** Add a "Deploy Worker" button to the dashboard that opens a modal with a form to generate a Docker `run` command for starting a worker.

---

## Placement

New "Deploy Worker" button in the room action bar, between "View Workers" and "Invite". Uses a plus icon. Opens a dedicated modal (separate from the workers modal).

```
[ Submit Job ] [ View Workers ] [ + Deploy Worker ] [ Invite ]
```

**Insertion point:** `dashboard/app.js` line ~963, after the View Workers button, before the conditional Invite button.

## Modal Structure

- **Title:** "Deploy Worker"
- **Subtitle:** "Generate a Docker command to start a worker on your GPU machine"
- **Form** with real-time command preview that updates on every input change
- **Copy button** for the generated command
- **Info note** about RunAI/K8s mount handling
- **Done button** to close

## Form Fields

| Field | Type | Default | Required | Maps to |
|-------|------|---------|----------|---------|
| Account Key | Dropdown (user's active keys) | First active key | Yes | `-e SLEAP_RTC_ACCOUNT_KEY=...` |
| Worker Name | Text input | empty | No | `--name` |
| Working Directory | Text input | `/mnt/data` | No | `--working-dir` |
| Max Reconnect Time | Dropdown (30m, 1h, 2h, forever) | forever | No | `--max-reconnect-time` |
| GPU | Checkbox | checked | No | `--gpus all` |
| Auto-restart | Checkbox | checked | No | `--restart unless-stopped` |
| Data Mounts | Repeatable path input (+/- buttons) | empty | No | `-v path:path` |

## Command Generation

A `updateDeployWorkerCommand()` function reads all form values and builds the command string. Every input/select/checkbox gets an event listener that calls this function. The command updates in a `<pre>` block below the form in real-time.

Mounts use identical host and container paths (`-v /path:/path`) to keep file references consistent.

## Info Note

Displayed below the mounts section:

> If using RunAI or Kubernetes, configure storage mounts through your cluster UI instead of the Docker `-v` flag.

## Example Output

```bash
docker run -d \
  --gpus all \
  --restart unless-stopped \
  -e SLEAP_RTC_ACCOUNT_KEY=slp_acct_7f3a9b2c1d4e5f6a \
  -v /root/vast:/root/vast \
  ghcr.io/talmolab/sleap-rtc-worker:latest \
  worker --name salk-a100-node-1 --working-dir /root/vast --max-reconnect-time 2h
```

## Files Changed

| File | Change |
|------|--------|
| `dashboard/index.html` | Add deploy-worker-modal HTML |
| `dashboard/app.js` | Add Deploy Worker button to room card, modal open/close, command generation logic |
| `dashboard/styles.css` | Styles for the new modal (reuse existing patterns) |

## Prototype

Interactive prototype at `scratch/deploy-worker-prototype.html` with 4 test scenarios:
1. Basic (defaults only)
2. HPC cluster (mounts, name, reconnect time)
3. Minimal (no GPU, no restart)
4. Multiple mounts

## Future

This modal is the foundation for more advanced deployment options (RunAI API integration, Slurm batch script generation) if needed later.
