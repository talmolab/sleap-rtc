## 1. Dockerfile Optimization

- [ ] 1.1 Remove boto3 from `sleap_RTC/worker/pyproject.toml`
- [ ] 1.2 Update Dockerfile to remove boto3 from `uv add` command
- [ ] 1.3 Remove `apt-get` layer entirely (zip/unzip not needed)
- [ ] 1.4 Clean up comments and simplify structure
- [ ] 1.5 Verify Python's shutil handles zipping (no external tools needed)

## 2. Test Workflow Optimization

- [ ] 2.1 Add disk usage monitoring (before cleanup, after cleanup, after build)
- [ ] 2.2 Optimize disk cleanup to minimal settings (keep essential cleanup)
- [ ] 2.3 Add Docker layer caching (`cache-from: type=gha`, `cache-to: type=gha,mode=max`)
- [ ] 2.4 Remove unnecessary matrix strategy (single platform)
- [ ] 2.5 Remove platform sanitization steps (not needed for single platform)
- [ ] 2.6 Simplify tags (no sanitization needed)

## 3. Production Workflow Optimization

- [ ] 3.1 Add disk usage monitoring
- [ ] 3.2 Optimize disk cleanup to minimal settings
- [ ] 3.3 Add Docker layer caching
- [ ] 3.4 Apply same simplifications as test workflow

## 4. Verification and Testing

- [ ] 4.1 Verify worker code doesn't use boto3 (grep check)
- [ ] 4.2 Verify Python shutil.make_archive works without zip binary
- [ ] 4.3 Test Docker build locally
- [ ] 4.4 Monitor first CI build time
- [ ] 4.5 Monitor subsequent CI build time (verify caching works)
- [ ] 4.6 Check disk usage logs to verify cleanup is sufficient
- [ ] 4.7 Verify worker container starts and functions correctly

## 5. Documentation

- [ ] 5.1 Update comments in Dockerfile explaining optimizations
- [ ] 5.2 Add comments in workflow explaining layer caching
- [ ] 5.3 Document expected build times in workflow comments
