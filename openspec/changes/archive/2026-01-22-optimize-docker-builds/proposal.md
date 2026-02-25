## Why

Docker builds for sleap-rtc-worker are slow (12-21 minutes) and inefficient due to:
- Unnecessary dependencies (boto3, zip/unzip) adding ~60-90MB and 30-60s build time
- Missing layer caching causing full rebuilds every time (5-10 min wasted)
- No build time monitoring to identify bottlenecks

Analysis shows:
- `boto3` is installed but never imported in worker code
- `zip`/`unzip` system packages are unnecessary (Python's `shutil` handles zipping)
- GitHub Actions layer caching is not enabled (can save 50-70% on rebuilds)
- Current builds: 12-21 minutes
- Target builds: 7-10 minutes (first build), 2-4 minutes (cached rebuilds)

## What Changes

### Dockerfile Optimizations
- Remove unused `boto3` dependency (~50-80MB, ~20-40s build time)
- Remove unused `zip` and `unzip` system packages (~5-10MB, ~10-30s)
- Eliminate entire apt-get layer (no system packages needed)
- Simplify RUN commands and remove redundant comments

### GitHub Actions Workflow Optimizations
- Add Docker layer caching (`cache-from`/`cache-to: type=gha`)
- Optimize disk cleanup to minimal necessary components
- Add disk usage monitoring to track space consumption
- Simplify workflow (remove unnecessary matrix/sanitization for single platform)

### Benefits
- **60-90MB smaller images**
- **50-90s faster first builds**
- **50-70% faster subsequent builds** (layer caching)
- **More reliable builds** (optimized disk cleanup)
- **Better observability** (disk usage monitoring)

## Impact

- Affected files:
  - `sleap_RTC/worker/Dockerfile` - Remove dependencies, simplify layers
  - `sleap_RTC/worker/pyproject.toml` - Remove boto3 from dependencies
  - `.github/workflows/worker_test.yml` - Add caching, optimize cleanup
  - `.github/workflows/worker_production.yml` - Same optimizations
- No breaking changes (removed deps are unused)
- No runtime behavior changes
- Fully backward compatible
- **Reduces CI costs** (faster builds = less compute time)
