## ADDED Requirements

### Requirement: Docker Image Optimization

The worker Dockerfile SHALL only include dependencies that are used by the worker code, removing unused packages to minimize image size and build time.

#### Scenario: boto3 removed from dependencies
- **WHEN** building the worker Docker image
- **THEN** boto3 is not installed (not used in worker code)

#### Scenario: System zip packages removed
- **WHEN** building the worker Docker image
- **THEN** zip and unzip system packages are not installed (Python's shutil handles archiving)

#### Scenario: apt-get layer eliminated
- **WHEN** building the worker Docker image
- **THEN** no apt-get commands run (no system packages needed)

#### Scenario: Smaller image size
- **WHEN** comparing image sizes before and after optimization
- **THEN** image is 60-90MB smaller

### Requirement: Docker Layer Caching

The GitHub Actions workflows SHALL use Docker layer caching to reuse unchanged layers across builds, significantly reducing build time for subsequent builds.

#### Scenario: Layer cache enabled for test workflow
- **WHEN** building in the test workflow
- **THEN** cache-from and cache-to are configured with type=gha

#### Scenario: Layer cache enabled for production workflow
- **WHEN** building in the production workflow
- **THEN** cache-from and cache-to are configured with type=gha

#### Scenario: Cached rebuild performance
- **WHEN** rebuilding with unchanged base layers
- **THEN** build completes 50-70% faster than uncached build

### Requirement: Disk Space Management

The GitHub Actions workflows SHALL implement minimal necessary disk cleanup and monitor disk usage to ensure builds have sufficient space without excessive cleanup overhead.

#### Scenario: Optimized cleanup configuration
- **WHEN** running disk cleanup step
- **THEN** only essential cleanup operations are enabled (Android, .NET, large-packages, docker-images)

#### Scenario: Disk usage monitoring
- **WHEN** workflow executes
- **THEN** disk usage is logged before cleanup, after cleanup, and after build

#### Scenario: Sufficient disk space maintained
- **WHEN** building Docker images
- **THEN** at least 20GB free space remains after cleanup

### Requirement: Build Time Performance

The CI/CD builds SHALL complete within target timeframes to minimize CI costs and developer wait time.

#### Scenario: First build performance
- **WHEN** building with no cache (first build or cache miss)
- **THEN** build completes in 7-12 minutes (improved from 12-21 minutes)

#### Scenario: Cached build performance
- **WHEN** rebuilding with layer cache hits
- **THEN** build completes in 2-5 minutes (50-70% improvement)

#### Scenario: Build time monitoring
- **WHEN** workflow completes
- **THEN** individual step timings are visible in GitHub Actions UI

### Requirement: Simplified Workflow Configuration

The GitHub Actions workflows SHALL be simplified by removing unnecessary complexity for single-platform builds.

#### Scenario: Matrix strategy removed
- **WHEN** test workflow runs
- **THEN** no matrix strategy is used (single platform: linux/amd64)

#### Scenario: Platform sanitization removed
- **WHEN** workflow generates image tags
- **THEN** no platform sanitization steps execute (static platform name)

#### Scenario: Workflow readability
- **WHEN** reviewing workflow files
- **THEN** configuration is clear and straightforward without unnecessary steps

### Requirement: Backward Compatibility

The optimizations SHALL maintain full backward compatibility with existing worker functionality and deployment processes.

#### Scenario: Worker functionality unchanged
- **WHEN** worker container starts
- **THEN** all features work identically to pre-optimization (RTC, ZMQ, file zipping, SLEAP training)

#### Scenario: Container registry compatibility
- **WHEN** pushing optimized images
- **THEN** images are compatible with existing deployment scripts and infrastructure

#### Scenario: No runtime dependencies broken
- **WHEN** worker code executes
- **THEN** no import errors or missing dependency errors occur
