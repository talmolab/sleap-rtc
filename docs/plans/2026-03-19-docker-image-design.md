# Docker Image Update Design

**Date:** 2026-03-19
**PR:** 3 (Worker Docker Image)
**Branch:** TBD
**Goal:** Make the worker Docker image usable as a one-command container with the full `sleap-rtc` CLI.

---

## Approach: Two Dockerfiles (Source + PyPI)

Two separate Dockerfiles to avoid conditional logic and wasted layers:

- **`Dockerfile`** (production) — installs `sleap-rtc` from PyPI. Used after releases.
- **`Dockerfile.test`** (test/branch) — copies source and installs locally. Used for testing unreleased code.

Both share the same entrypoint (`sleap-rtc`) and default command (`worker`).

## Files Changed

| File | Action | What |
|------|--------|------|
| `sleap_rtc/worker/Dockerfile` | Rewrite | PyPI install, `sleap-rtc` entrypoint, `worker` default CMD |
| `sleap_rtc/worker/Dockerfile.test` | New | Source install from repo, same entrypoint/CMD |
| `.dockerignore` | New | Exclude `.git`, tests, docs, scratch, caches from build context |
| `.github/workflows/worker_test.yml` | Edit | `context: .`, `file: Dockerfile.test`, expanded trigger paths |
| `.github/workflows/worker_production.yml` | Edit | Explicit `file: Dockerfile` |

No Python code changes.

## Dockerfiles

### Production (`sleap_rtc/worker/Dockerfile`)

```dockerfile
FROM ghcr.io/talmolab/sleap-nn-cuda:latest

WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive

RUN uv pip install sleap-rtc

RUN mkdir -p /app/shared_data && chmod 777 /app/shared_data

EXPOSE 8080 8001 5000 3478/udp 3478/tcp 9001/tcp 9000/tcp

ENTRYPOINT ["sleap-rtc"]
CMD ["worker"]
```

### Test (`sleap_rtc/worker/Dockerfile.test`)

```dockerfile
FROM ghcr.io/talmolab/sleap-nn-cuda:latest

WORKDIR /app
ENV DEBIAN_FRONTEND=noninteractive

COPY pyproject.toml /app/
COPY sleap_rtc/ /app/sleap_rtc/
RUN uv pip install .

RUN mkdir -p /app/shared_data && chmod 777 /app/shared_data

EXPOSE 8080 8001 5000 3478/udp 3478/tcp 9001/tcp 9000/tcp

ENTRYPOINT ["sleap-rtc"]
CMD ["worker"]
```

## CI Workflow Changes

### `worker_test.yml`

- `context: .` (repo root, so COPY can access source)
- `file: ./sleap_rtc/worker/Dockerfile.test`
- Expanded trigger paths:

```yaml
paths:
  - sleap_rtc/worker/**
  - sleap_rtc/**/*.py
  - pyproject.toml
  - .github/workflows/worker_test.yml
```

### `worker_production.yml`

- Add explicit `file: ./sleap_rtc/worker/Dockerfile`
- Trigger paths unchanged

## Root `.dockerignore`

Needed because test workflow uses `context: .` (whole repo):

```
.git/
tests/
docs/
scratch/
*.pyc
__pycache__/
*.egg-info/
.venv/
.ruff_cache/
.pytest_cache/
*.log
.env
*.md
openspec/
```

## Authentication

Container uses `SLEAP_RTC_ACCOUNT_KEY` env var — the CLI picks it up automatically via Click's `envvar` parameter. No volume mounts needed.

## Usage

```bash
# Basic (default: sleap-rtc worker)
docker run --gpus all \
  -e SLEAP_RTC_ACCOUNT_KEY=slp_acct_xxx... \
  ghcr.io/talmolab/sleap-rtc-worker:latest

# With options
docker run --gpus all \
  -e SLEAP_RTC_ACCOUNT_KEY=slp_acct_xxx... \
  -v /mnt/data:/mnt/data \
  ghcr.io/talmolab/sleap-rtc-worker:latest \
  worker --name my-gpu-1 --working-dir /mnt/data --max-reconnect-time 2h

# Other subcommands
docker run --rm ghcr.io/talmolab/sleap-rtc-worker:latest doctor
docker run --rm ghcr.io/talmolab/sleap-rtc-worker:latest key list
docker run -it --entrypoint bash ghcr.io/talmolab/sleap-rtc-worker:latest
```

## Future: Dashboard Docker Command Generator

A future PR could add a dashboard UI that generates the `docker run` command for users — pre-filling their account key from the dashboard session, with checkboxes/fields for name, working dir, mounts, etc.
