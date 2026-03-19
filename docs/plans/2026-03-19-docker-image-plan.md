# Docker Image Update Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update the worker Docker image to install the full `sleap-rtc` package so `sleap-rtc worker` works as the container entrypoint.

**Architecture:** Two Dockerfiles — `Dockerfile` (production, PyPI install) and `Dockerfile.test` (test, source install). CI workflows updated to match. Root `.dockerignore` added for clean build context.

**Tech Stack:** Docker, GitHub Actions CI, `uv` package manager

---

## Task 1: Rewrite production Dockerfile

**Files:**
- Modify: `sleap_rtc/worker/Dockerfile`

**Step 1: Rewrite Dockerfile**

Replace contents of `sleap_rtc/worker/Dockerfile` with:

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

**Step 2: Commit**

```bash
git add sleap_rtc/worker/Dockerfile
git commit -m "feat: rewrite worker Dockerfile with sleap-rtc CLI entrypoint (PyPI)"
```

---

## Task 2: Create test Dockerfile

**Files:**
- Create: `sleap_rtc/worker/Dockerfile.test`

**Step 1: Create Dockerfile.test**

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

**Step 2: Commit**

```bash
git add sleap_rtc/worker/Dockerfile.test
git commit -m "feat: add test Dockerfile for source-based worker image builds"
```

---

## Task 3: Add root .dockerignore

**Files:**
- Create: `.dockerignore`

**Step 1: Create .dockerignore**

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

**Step 2: Commit**

```bash
git add .dockerignore
git commit -m "chore: add root .dockerignore for test workflow build context"
```

---

## Task 4: Update CI workflows

**Files:**
- Modify: `.github/workflows/worker_test.yml`
- Modify: `.github/workflows/worker_production.yml`

**Step 1: Update worker_test.yml**

Change trigger paths:
```yaml
paths:
  - sleap_rtc/worker/**
  - sleap_rtc/**/*.py
  - pyproject.toml
  - .github/workflows/worker_test.yml
```

Change build step:
```yaml
context: .
file: ./sleap_rtc/worker/Dockerfile.test
```

**Step 2: Update worker_production.yml**

Add explicit file reference:
```yaml
file: ./sleap_rtc/worker/Dockerfile
```

**Step 3: Commit**

```bash
git add .github/workflows/worker_test.yml .github/workflows/worker_production.yml
git commit -m "ci: update worker workflows for dual Dockerfile setup"
```

---

## Task 5: Push and verify CI

**Step 1: Push branch**

```bash
git push -u origin amick/docker-worker-bootstrap
```

**Step 2: Verify CI triggers and builds pass**
