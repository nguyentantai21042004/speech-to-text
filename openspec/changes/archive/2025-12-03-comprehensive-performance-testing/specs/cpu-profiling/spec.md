# CPU Profiling Specification

## ADDED Requirements

### Requirement: Multi-Core Scaling Analysis
The system SHALL analyze CPU scaling efficiency to determine optimal core count and answer whether the service benefits from many weak cores or few strong cores.

#### Scenario: Profile with different CPU counts
**Given** Docker is available with `--cpus` flag support  
**When** CPU profiling runs  
**Then** benchmarks SHALL run with 1, 2, 4, and 8 CPU cores  
**And** latency SHALL be measured for each configuration  
**And** throughput (RPS) SHALL be measured for each configuration  
**And** CPU utilization SHALL be measured for each configuration

#### Scenario: Calculate scaling efficiency
**Given** benchmark results for 1, 2, 4, 8 cores  
**When** scaling efficiency is calculated  
**Then** speedup SHALL be calculated as: baseline_latency / current_latency  
**And** efficiency SHALL be calculated as: speedup / core_count  
**And** linear scaling SHALL be identified when efficiency > 0.9  
**And** sub-linear scaling SHALL be identified when efficiency < 0.8

#### Scenario: Determine CPU characteristics
**Given** scaling efficiency has been calculated  
**When** analyzing CPU characteristics  
**Then** if efficiency > 0.8 at 4 cores, answer SHALL be "many weak cores"  
**And** if efficiency < 0.5 at 4 cores, answer SHALL be "few strong cores"  
**And** diminishing returns point SHALL be identified  
**And** optimal core count SHALL be recommended

#### Scenario: Identify diminishing returns
**Given** scaling efficiency for multiple core counts  
**When** analyzing efficiency curve  
**Then** diminishing returns SHALL be identified when adding cores gives <20% improvement  
**And** the point SHALL be documented in the report  
**And** recommendations SHALL advise against exceeding this point

### Requirement: Thread Optimization
The system SHALL determine optimal thread count per CPU core for maximum performance.

#### Scenario: Test different thread counts
**Given** a fixed CPU core count  
**When** testing different WHISPER_N_THREADS values  
**Then** thread counts [1, 2, 4, 8] SHALL be tested  
**And** latency SHALL be measured for each  
**And** CPU utilization SHALL be measured for each  
**And** optimal thread count SHALL be identified

#### Scenario: Optimal thread recommendation
**Given** thread count test results  
**When** determining optimal configuration  
**Then** the thread count with lowest latency SHALL be recommended  
**And** CPU utilization SHALL be considered (avoid over-subscription)  
**And** the recommendation SHALL be documented

### Requirement: Architecture Comparison
The system SHALL compare performance between different CPU architectures (ARM vs x86).

#### Scenario: Compare ARM and x86 performance
**Given** benchmarks run on Mac M4 (ARM) and K8s Xeon (x86)  
**When** comparing results  
**Then** latency SHALL be compared between architectures  
**And** scaling efficiency SHALL be compared  
**And** normalization ratio SHALL be calculated  
**And** architecture-specific recommendations SHALL be provided
