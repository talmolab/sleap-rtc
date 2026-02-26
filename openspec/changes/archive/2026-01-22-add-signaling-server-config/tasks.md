## 1. Configuration Module

- [x] 1.1 Create `sleap_RTC/config.py` module with config loading logic
- [x] 1.2 Use built-in `tomllib` for TOML parsing (Python 3.11+ built-in, no dependency needed)
- [x] 1.3 Implement SLEAP_RTC_ENV environment selector (development, staging, production)
- [x] 1.4 Implement config file discovery (sleap-rtc.toml in CWD, ~/.sleap-rtc/config.toml)
- [x] 1.5 Implement environment-specific config loading from [environments.<env>] sections
- [x] 1.6 Implement [default] section support for shared settings
- [x] 1.7 Implement environment variable overrides (SLEAP_RTC_SIGNALING_WS, SLEAP_RTC_SIGNALING_HTTP)
- [x] 1.8 Define default values for production environment (backward compatibility)

## 2. Code Updates

- [x] 2.1 Update `sleap_RTC/client/client_class.py` to use config
- [x] 2.2 Update `sleap_RTC/worker/worker_class.py` to use config
- [x] 2.3 Update `sleap_RTC/RTCclient.py` to use config
- [x] 2.4 Update `sleap_RTC/RTCworker.py` to use config
- [x] 2.5 Update `sleap_RTC/worker/worker.py` to use config
- [x] 2.6 Update `sleap_RTC/client/client.py` CLI argument handling

## 3. Documentation

- [x] 3.1 Create example config file (`config.example.toml`) with all three environment sections
- [x] 3.2 Update README with configuration instructions
- [x] 3.3 Document SLEAP_RTC_ENV environment selector
- [x] 3.4 Document environment variable override options (SLEAP_RTC_SIGNALING_WS, SLEAP_RTC_SIGNALING_HTTP)
- [x] 3.5 Add usage examples for each environment

## 4. Testing

- [x] 4.1 Test SLEAP_RTC_ENV=development with config file
- [x] 4.2 Test SLEAP_RTC_ENV=staging with config file
- [x] 4.3 Test SLEAP_RTC_ENV=production with config file
- [x] 4.4 Test default environment (no SLEAP_RTC_ENV set)
- [x] 4.5 Test environment variable overrides (SLEAP_RTC_SIGNALING_WS, SLEAP_RTC_SIGNALING_HTTP)
- [x] 4.6 Test CLI arguments override all
- [x] 4.7 Test missing config file fallback
- [x] 4.8 Test missing environment section fallback
- [x] 4.9 Test [default] section inheritance
- [x] 4.10 Verify backward compatibility (no config = production defaults)
