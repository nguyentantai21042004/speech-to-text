# Comprehensive Performance Testing and Scaling Strategy

## Why

Although we have a basic benchmark system from the previous proposal (`2025-12-02-add-deployment-benchmark`), there are still many unanswered questions about performance characteristics and scaling strategy:

**1. Lack of Comprehensive Test Coverage:**
- 91 tests exist but no unified process to run all tests and verify system stability
- No comprehensive test report to assess quality
- No regression testing after each change

**2. CPU Characteristics Not Determined:**
- Current benchmarks only measure latency and RPS
- Unknown whether service needs **many weak CPU cores** or **few strong CPU cores**
- Unknown CPU scaling behavior (linear vs sub-linear)
- Unknown optimal thread count for different CPU configurations

**3. Missing Clear Scaling Strategy:**
- No specific guidance to improve **single request** speed (vertical scaling)
- No specific guidance to improve **system throughput** (horizontal scaling)
- Unknown when to scale up vs scale out
- No metrics to decide scaling strategy

## What Changes

This proposal will create a comprehensive testing and benchmarking system to answer the above questions:

### 1. System-Wide Testing Suite
- **Test runner script** to run all 91 tests with reporting
- **CI/CD integration** to auto-run tests
- **Test coverage report** to track quality
- **Regression detection** to catch performance degradation

### 2. CPU Characteristics Profiling
- **Multi-core benchmark** to test with 1, 2, 4, 8 cores
- **CPU scaling analysis** to determine linear vs sub-linear scaling
- **Thread optimization** to find optimal thread count
- **CPU type comparison** (M4 ARM vs Xeon x86) to understand architecture differences
- **Answer the question**: Does service need many weak cores or few strong cores?

### 3. Comprehensive Audio Benchmarking
- **Benchmark with audio files under 10 minutes** from existing test files (260KB - 26MB)
- **Duration analysis** to understand relationship between audio length and processing time
- **Memory profiling** to track RAM usage with different audio sizes
- **Concurrent request testing** to measure system throughput
- **Note**: Only test files under 10 minutes duration to save time

### 4. Scaling Strategy Documentation
- **Vertical scaling guide**: When and how to increase CPU/Memory per pod
- **Horizontal scaling guide**: When and how to increase pod count
- **Decision matrix**: Metrics to decide scale up vs scale out
- **Cost optimization**: Trade-offs between performance and cost

## User Review Required

> [!IMPORTANT]
> **Benchmark Duration**: Comprehensive benchmarking with audio files under 10 minutes x multiple CPU configs will take approximately 1-2 hours (reduced from 2-4 hours by limiting audio duration).

> [!WARNING]
> **Resource Requirements**: CPU profiling requires access to machines with different CPU counts (1, 2, 4, 8 cores). Confirm ability to provision these resources (Docker with `--cpus` or K8s with resource limits).

## Proposed Changes

### Testing Infrastructure

#### [NEW] [run_all_tests.py](file:///Users/tantai/Workspaces/tools/speech-to-text/scripts/run_all_tests.py)

Create comprehensive test runner:
- Run all 91 tests with pytest
- Generate HTML coverage report
- Generate JSON test results
- Track test execution time
- Detect slow tests (>5s)
- Fail on any test failure

#### [NEW] [test_report.html](file:///Users/tantai/Workspaces/tools/speech-to-text/scripts/test_reports/test_report.html)

Auto-generated test report showing:
- Total tests: 91
- Pass/Fail breakdown
- Coverage percentage
- Slow tests list
- Failed test details

---

### CPU Profiling

#### [NEW] [profile_cpu_scaling.py](file:///Users/tantai/Workspaces/tools/speech-to-text/scripts/profile_cpu_scaling.py)

CPU scaling profiler:
- Run benchmark with 1, 2, 4, 8 CPU cores
- Measure latency and throughput for each config
- Calculate scaling efficiency (speedup / cores)
- Determine if scaling is linear or sub-linear
- Generate CPU scaling report

#### [NEW] [cpu_scaling_report.md](file:///Users/tantai/Workspaces/tools/speech-to-text/scripts/benchmark_results/cpu_scaling_report.md)

Report answering:
- **Question 1**: Service cần nhiều cores yếu hay ít cores mạnh?
- **Question 2**: CPU scaling efficiency (linear vs sub-linear)?
- **Question 3**: Optimal thread count per CPU core?
- **Question 4**: Diminishing returns point (khi nào thêm cores không hiệu quả)?

---

### Audio Benchmarking

#### [MODIFY] [benchmark.py](file:///Users/tantai/Workspaces/tools/speech-to-text/scripts/benchmark.py)

Enhance existing benchmark script:
- Add `--all-audio` flag to benchmark all audio files under 10 minutes
- Add `--max-duration` parameter (default: 600 seconds / 10 minutes)
- Add `--cpu-profile` flag to run multi-core profiling
- Add memory profiling with `tracemalloc`
- Add concurrent request simulation
- Generate comprehensive benchmark report

#### [NEW] [benchmark_all_audio.sh](file:///Users/tantai/Workspaces/tools/speech-to-text/scripts/benchmark_all_audio.sh)

Shell script to:
- Benchmark all audio files under 10 minutes duration
- Filter out long files (>10 minutes) to save time
- Test with base, small, medium models
- Generate comparison report
- Calculate RTF (Real-Time Factor) for each

---

### Scaling Strategy Documentation

#### [NEW] [SCALING_STRATEGY.md](file:///Users/tantai/Workspaces/tools/speech-to-text/docs/SCALING_STRATEGY.md)

Comprehensive scaling guide:
- **When to Scale Vertically** (increase CPU/Memory per pod)
- **When to Scale Horizontally** (increase pod count)
- **Decision Matrix** with metrics thresholds
- **Cost Optimization** strategies
- **Performance Tuning** tips

#### [MODIFY] [deployment.yaml](file:///Users/tantai/Workspaces/tools/speech-to-text/k8s/deployment.yaml)

Update with benchmark-based recommendations:
- CPU requests/limits based on profiling results
- Memory requests/limits based on audio benchmarking
- HPA thresholds based on scaling strategy
- Comments explaining sizing decisions

---

### Reporting and Analysis

#### [NEW] [generate_performance_report.py](file:///Users/tantai/Workspaces/tools/speech-to-text/scripts/generate_performance_report.py)

Unified report generator:
- Combine test results
- Combine benchmark results
- Combine CPU profiling results
- Generate executive summary
- Answer all 3 user questions

#### [NEW] [PERFORMANCE_REPORT.md](file:///Users/tantai/Workspaces/tools/speech-to-text/docs/PERFORMANCE_REPORT.md)

Final report answering:
1. ✅ **System Test Results**: All 91 tests passing?
2. ✅ **CPU Characteristics**: Nhiều cores yếu hay ít cores mạnh?
3. ✅ **Scaling Strategy**: Vertical vs Horizontal scaling guide

## Verification Plan

### Automated Tests

1. **Run Full Test Suite**
   ```bash
   python scripts/run_all_tests.py
   ```
   - Verify all 91 tests pass
   - Check coverage report generated
   - Verify no slow tests (>10s)

2. **CPU Profiling**
   ```bash
   python scripts/profile_cpu_scaling.py --model base
   ```
   - Verify runs with 1, 2, 4, 8 cores
   - Check scaling report generated
   - Verify scaling efficiency calculated

3. **Audio Benchmarking**
   ```bash
   ./scripts/benchmark_all_audio.sh
   ```
   - Verify only audio files under 10 minutes are benchmarked
   - Check RTF calculated for each
   - Verify memory profiling data collected
   - Confirm long files (>10 min) are skipped

### Manual Verification

1. **Review Test Report**
   - Open `scripts/test_reports/test_report.html`
   - Verify all tests shown with pass/fail status
   - Check coverage percentage is >80%

2. **Review CPU Scaling Report**
   - Open `scripts/benchmark_results/cpu_scaling_report.md`
   - Verify answers question: "Nhiều cores yếu hay ít cores mạnh?"
   - Check scaling efficiency graph included

3. **Review Performance Report**
   - Open `docs/PERFORMANCE_REPORT.md`
   - Verify all 3 questions answered:
     1. System stability (test results)
     2. CPU characteristics
     3. Scaling strategy

4. **Review Scaling Strategy**
   - Open `docs/SCALING_STRATEGY.md`
   - Verify clear guidance for vertical scaling
   - Verify clear guidance for horizontal scaling
   - Check decision matrix is actionable
