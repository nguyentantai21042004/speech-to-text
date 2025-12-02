# Deployment Benchmark Specification

## ADDED Requirements

### Requirement: Benchmark Tool
The system SHALL provide a benchmark script that uses actual Whisper inference code to measure real-world performance instead of synthetic benchmarks.

#### Scenario: Benchmark initialization
- **WHEN** the benchmark script starts
- **THEN** the system SHALL load the Whisper model and prepare test audio data without counting this time in measurements

#### Scenario: Running benchmark iterations
- **WHEN** running benchmark iterations
- **THEN** the system SHALL execute a configurable number of inference runs (default 50) and calculate average latency

#### Scenario: Benchmark output
- **WHEN** benchmark completes
- **THEN** the system SHALL output average latency (seconds), total time, and estimated single-thread RPS in JSON format

#### Scenario: Custom iterations
- **WHEN** the benchmark script is invoked with `--iterations` flag
- **THEN** the system SHALL use the specified number of iterations

#### Scenario: Model selection
- **WHEN** the benchmark script is invoked with `--model-size` flag
- **THEN** the system SHALL load and benchmark the specified model (base/small/medium)

### Requirement: CPU Isolation Testing
The system SHALL support running benchmarks with CPU isolation to ensure accurate cross-platform comparison.

#### Scenario: Mac M4 Docker isolation
- **WHEN** running benchmark on Mac M4
- **THEN** the benchmark SHALL be executed inside a Docker container with `--cpus="1"` flag to isolate exactly 1 CPU core

#### Scenario: Architecture detection
- **WHEN** Docker container starts
- **THEN** the system SHALL detect and log the CPU architecture (ARM64/x86_64)

#### Scenario: Results persistence
- **WHEN** benchmark completes
- **THEN** the system SHALL save results to a JSON file with timestamp, architecture, model_size, and metrics

#### Scenario: Warning for non-isolated runs
- **WHEN** the benchmark is run without Docker isolation
- **THEN** the system SHALL display a warning about potential inaccurate results

### Requirement: K8s Benchmark Pod
The system SHALL provide a Kubernetes Pod manifest for running benchmarks on Xeon cluster with proper resource isolation.

#### Scenario: QoS Guaranteed configuration
- **WHEN** deploying benchmark Pod to K8s
- **THEN** the Pod SHALL use resource limits of exactly 1 CPU core with requests=limits for QoS Guaranteed class

#### Scenario: CPU model detection
- **WHEN** benchmark Pod runs on Xeon
- **THEN** the system SHALL detect and log the CPU model and architecture

#### Scenario: Consistent output format
- **WHEN** benchmark completes on Xeon
- **THEN** the system SHALL output results in the same JSON format as Mac M4 for comparison

#### Scenario: No restart policy
- **WHEN** benchmark Pod completes
- **THEN** the Pod SHALL have restartPolicy set to Never to prevent re-runs

### Requirement: Normalization Ratio Calculation
The system SHALL calculate performance ratio between M4 and Xeon for accurate K8s resource sizing.

#### Scenario: Ratio calculation
- **WHEN** both Mac M4 and Xeon benchmark results are available
- **THEN** the system SHALL calculate the Normalization Ratio as (Latency_Xeon / Latency_Mac)

#### Scenario: Resource sizing
- **WHEN** calculating resource requirements for a target RPS
- **THEN** the system SHALL multiply required M4 cores by the Normalization Ratio to get Xeon cores needed

#### Scenario: Sizing recommendations output
- **WHEN** generating sizing recommendations
- **THEN** the system SHALL output recommended CPU requests/limits for the target RPS

#### Scenario: Ratio persistence
- **WHEN** Normalization Ratio is calculated
- **THEN** the system SHALL persist the ratio to a configuration file for future reference

### Requirement: Multi-thread Stress Test
The system SHALL detect CPU throttling issues when using multiple threads.

#### Scenario: Thread count testing
- **WHEN** running stress test
- **THEN** the system SHALL test with configurable thread counts (1, 2, 4) while keeping CPU limit at 1 core

#### Scenario: Throttling detection
- **WHEN** latency increases significantly (>2x) with more threads
- **THEN** the system SHALL flag this as throttling detected

#### Scenario: Throttling recommendations
- **WHEN** throttling is detected
- **THEN** the system SHALL recommend either reducing threads or increasing CPU limits

#### Scenario: Comparison output
- **WHEN** stress test completes
- **THEN** the system SHALL output a comparison table of latency vs thread count

### Requirement: Benchmark Results Management
The system SHALL store benchmark results in a structured format for tracking performance over time.

#### Scenario: JSON schema
- **WHEN** saving benchmark results
- **THEN** the system SHALL use JSON format with schema including: timestamp, architecture, cpu_model, model_size, iterations, avg_latency_ms, rps, cpu_limit

#### Scenario: Results history
- **WHEN** running multiple benchmarks
- **THEN** the system SHALL append results to a history file without overwriting previous results

#### Scenario: Results comparison
- **WHEN** comparing results
- **THEN** the system SHALL support loading and comparing multiple benchmark result files

#### Scenario: Markdown report
- **WHEN** generating reports
- **THEN** the system SHALL output a markdown summary comparing Mac M4 vs Xeon performance with sizing recommendations
