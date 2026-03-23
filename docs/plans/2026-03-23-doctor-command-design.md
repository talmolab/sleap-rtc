# Doctor Command Extension Design

**Date:** 2026-03-23
**PR:** 4 (Doctor command enhancements)
**Branch:** amick/0.0.6-version-precheck
**Goal:** Extend the existing `sleap-rtc doctor` command with worker-specific checks: account key, GPU, sleap-nn, and data mounts.

---

## Changes to Existing Sections

### Credentials (extended)

Add account key check after the existing "Logged in" check:
- Show whether an account key is found
- Show source: `(from env var)` or `(from credentials file)`
- Yellow warning with fix instructions if missing

## New Sections

### GPU

- `torch.cuda.is_available()` — if True, show GPU model, memory, CUDA version via `WorkerCapabilities`
- If False but torch installed: yellow warning "PyTorch installed but CUDA not available"
- If torch not importable: yellow warning "PyTorch not installed"
- Warn only — no failures. Workers can run on CPU.

### Training Dependencies

- Check `import sleap_nn` — show version if available
- Warn only if missing.

### Data Mounts & Working Directory

- Load `get_worker_io_config()` from config
- Check working directory exists (if configured)
- Check each configured mount path exists and is a directory
- Show pass/fail per mount with path

## Files Changed

| File | Change |
|------|--------|
| `sleap_rtc/cli.py` | Add new check sections to existing `doctor` command |
| `tests/test_doctor.py` | New tests for the added checks |
