## Why

The signaling server URLs are currently hardcoded throughout the codebase to specific AWS EC2 instances. This makes it difficult to:
- Switch between development, staging, and production environments
- Deploy to different regions or use custom signaling servers
- Test with local signaling servers

## What Changes

- Add environment-aware configuration system for signaling server URLs (WebSocket and HTTP endpoints)
- Use TOML config file with environment sections: `[environments.development]`, `[environments.staging]`, `[environments.production]`
- Environment selection via `SLEAP_RTC_ENV` environment variable (defaults to `production`)
- Support multiple configuration sources in priority order:
  1. CLI arguments (where they exist)
  2. Environment-specific variables (`SLEAP_RTC_SIGNALING_WS`, `SLEAP_RTC_SIGNALING_HTTP`)
  3. TOML configuration file (`~/.sleap-rtc/config.toml` or `sleap-rtc.toml` in project dir)
  4. Sensible defaults (production environment)
- Replace all hardcoded AWS URLs with config lookups
- Use built-in `tomllib` (Python 3.11+) - no extra dependencies
- Document configuration options in README with example config file

## Impact

- Affected specs: signaling-configuration (new capability)
- Affected code:
  - `sleap_RTC/RTCclient.py:19`
  - `sleap_RTC/RTCworker.py:23`
  - `sleap_RTC/worker/worker_class.py:54,80,96,849`
  - `sleap_RTC/worker/worker.py:600`
  - `sleap_RTC/client/client_class.py:31,73,91`
  - `sleap_RTC/client/client.py:562`
- Backward compatible: defaults to current production server
- No breaking changes
