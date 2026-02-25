# Worker Capabilities Specification

## ADDED Requirements

### Requirement: GPU Hardware Detection

The worker capabilities module SHALL detect and report GPU hardware specifications including memory, model name, and CUDA version.

#### Scenario: GPU available with CUDA

- **WHEN** worker initializes on a system with CUDA-enabled GPU
- **THEN** capabilities SHALL report GPU memory in MB, GPU model name, and CUDA version string

#### Scenario: No GPU available

- **WHEN** worker initializes on a system without GPU or CUDA
- **THEN** capabilities SHALL report 0 MB memory, "CPU" as model, and "N/A" as CUDA version

#### Scenario: GPU detection failure

- **WHEN** GPU detection raises ImportError or RuntimeError
- **THEN** capabilities SHALL log warning and gracefully fall back to CPU values

### Requirement: Job Compatibility Checking

The worker capabilities module SHALL evaluate whether a worker can handle a submitted job based on hardware requirements and supported features.

#### Scenario: Sufficient GPU memory

- **WHEN** job requires 8000 MB GPU memory and worker has 16000 MB
- **THEN** compatibility check SHALL return True

#### Scenario: Insufficient GPU memory

- **WHEN** job requires 16000 MB GPU memory and worker has 8000 MB
- **THEN** compatibility check SHALL return False and log reason

#### Scenario: Unsupported model type

- **WHEN** job requires "topdown" model and worker only supports ["base", "centroid"]
- **THEN** compatibility check SHALL return False and log unsupported model type

#### Scenario: Unsupported job type

- **WHEN** job is "inference" type and worker only supports ["training"]
- **THEN** compatibility check SHALL return False and log unsupported job type

### Requirement: Job Duration Estimation

The worker capabilities module SHALL estimate job completion time in minutes based on job type and configuration.

#### Scenario: Training job estimation

- **WHEN** job is training type with 100 epochs configured
- **THEN** estimator SHALL return approximately 50 minutes (0.5 minutes per epoch)

#### Scenario: Inference job estimation

- **WHEN** job is inference type with 1000 frames in dataset
- **THEN** estimator SHALL return approximately 10 minutes (100 frames per minute)

#### Scenario: Unknown job type

- **WHEN** job type is not recognized
- **THEN** estimator SHALL return default 60 minutes

### Requirement: Resource Utilization Reporting

The worker capabilities module SHALL report current GPU utilization and available memory for job assignment decisions.

#### Scenario: Worker available

- **WHEN** worker status is "available" and GPU is idle
- **THEN** GPU utilization SHALL report 0.0 and available memory SHALL match total GPU memory

#### Scenario: Worker busy

- **WHEN** worker status is "busy" with active job
- **THEN** GPU utilization SHALL report 0.9 and available memory SHALL reflect current free memory

#### Scenario: CPU-only worker

- **WHEN** worker has no GPU (CPU mode)
- **THEN** utilization SHALL return 0.0 and available memory SHALL return configured total memory
