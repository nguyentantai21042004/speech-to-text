# Design: Comprehensive Performance Testing and Scaling Strategy

## Overview

This change creates a comprehensive performance testing and analysis system to answer 3 critical questions:
1. **System Stability**: Are all 91 tests passing reliably?
2. **CPU Characteristics**: Does the service need many weak cores or few strong cores?
3. **Scaling Strategy**: How to scale for single request speed vs system throughput?

## Problem Statement

Current state:
- ✅ Basic benchmark system exists (`benchmark.py`, `analyze_benchmark.py`)
- ✅ 91 tests exist but no unified test runner
- ✅ 9 audio files available for testing
- ❌ No CPU scaling analysis (don't know if service benefits from more cores)
- ❌ No clear scaling strategy (when to scale up vs scale out)
- ❌ No comprehensive performance report

## Technical Approach

### 1. Testing Infrastructure

**Design Decision**: Use pytest with plugins for comprehensive reporting

```
┌─────────────────────────────────────────────────────────┐
│                   Test Runner Flow                      │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  run_all_tests.py                                       │
│       │                                                 │
│       ├──▶ pytest (91 tests)                            │
│       │       │                                         │
│       │       ├──▶ pytest-html (HTML report)            │
│       │       ├──▶ pytest-cov (coverage report)         │
│       │       └──▶ pytest-json (JSON results)           │
│       │                                                 │
│       └──▶ Test Summary                                 │
│             - Total: 91                                 │
│             - Passed: X                                 │
│             - Failed: Y                                 │
│             - Coverage: Z%                              │
│             - Slow tests: [list]                        │
└─────────────────────────────────────────────────────────┘
```

**Why pytest plugins?**
- `pytest-html`: Beautiful HTML reports with test details
- `pytest-cov`: Code coverage analysis
- `pytest-json`: Machine-readable results for automation
- `pytest-timeout`: Detect hanging tests

### 2. CPU Profiling System

**Design Decision**: Test with Docker `--cpus` for precise CPU limiting

```
┌─────────────────────────────────────────────────────────┐
│              CPU Scaling Profiler                       │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  For each CPU count in [1, 2, 4, 8]:                    │
│    │                                                    │
│    ├──▶ docker run --cpus="N" benchmark.py              │
│    │         │                                          │
│    │         ├──▶ Measure latency                       │
│    │         ├──▶ Measure throughput (RPS)              │
│    │         └──▶ Measure CPU utilization               │
│    │                                                    │
│    └──▶ Calculate scaling efficiency:                   │
│          - Speedup = Latency(1 core) / Latency(N cores) │
│          - Efficiency = Speedup / N                     │
│          - Linear if Efficiency ≈ 1.0                   │
│          - Sub-linear if Efficiency < 0.8               │
│                                                         │
│  Answer: "Nhiều cores yếu hay ít cores mạnh?"           │
│    - If Efficiency > 0.8 for 8 cores: "Nhiều cores"     │
│    - If Efficiency < 0.5 for 4 cores: "Ít cores mạnh"   │
└─────────────────────────────────────────────────────────┘
```

**CPU Scaling Metrics:**
- **Speedup**: How much faster with N cores vs 1 core
- **Efficiency**: Speedup / N (1.0 = perfect linear scaling)
- **Diminishing Returns Point**: Where adding cores gives <20% improvement

**Example Analysis:**
```
CPU Cores | Latency (ms) | Speedup | Efficiency | Recommendation
----------|--------------|---------|------------|---------------
1         | 1000         | 1.0x    | 100%       | Baseline
2         | 550          | 1.8x    | 90%        | Excellent
4         | 300          | 3.3x    | 83%        | Good
8         | 180          | 5.6x    | 70%        | Diminishing returns

Answer: Service benefits from "nhiều cores" (up to 4 cores efficient)
```

### 3. Audio Benchmarking

**Design Decision**: Benchmark all 9 audio files to understand duration vs processing time relationship

```
Audio Files (sorted by size):
1. 7553444429583944980.mp3 - 241KB
2. 7314151385635867905.mp3 - 260KB
3. 7505589215749475602.mp3 - 877KB
4. 7553209676272291073.mp3 - 942KB
5. 7555007631912406273.mp3 - 1.4MB
6. 7495363253598506247.mp3 - 1.9MB
7. 7533882162861411602.mp3 - 2.7MB
8. 7551063747725364487.mp3 - 26MB
9. benchmark_30s.wav - 935KB (standardized)

For each file:
  - Measure audio duration (ffprobe)
  - Measure processing time
  - Calculate RTF (Real-Time Factor) = processing_time / audio_duration
  - Measure peak memory usage
  - Test with base, small, medium models
```

**RTF Analysis:**
- RTF < 0.1: Excellent (10x faster than real-time)
- RTF < 0.5: Good (2x faster than real-time)
- RTF < 1.0: Acceptable (faster than real-time)
- RTF > 1.0: Problematic (slower than real-time)

### 4. Scaling Strategy Decision Matrix

**Design Decision**: Create clear decision matrix based on metrics

```
┌─────────────────────────────────────────────────────────┐
│              Scaling Decision Matrix                    │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Scenario 1: Tăng tốc độ 1 request (Vertical Scaling)   │
│  ────────────────────────────────────────────────────   │
│  When:                                                  │
│    - Single request latency > SLA                       │
│    - CPU utilization < 70% per pod                      │
│    - Memory available for larger model                  │
│                                                         │
│  Actions:                                               │
│    1. Increase CPU cores per pod (if efficiency > 0.7)  │
│    2. Switch to smaller model (base → small)            │
│    3. Optimize thread count (WHISPER_N_THREADS)         │
│                                                         │
│  Example:                                               │
│    Current: 2.5 cores, 500ms latency                    │
│    Target: 250ms latency                                │
│    Solution: Increase to 4 cores (if efficiency 0.8+)   │
│                                                         │
│ ─────────────────────────────────────────────────────   │
│  Scenario 2: Tăng throughput hệ thống (Horizontal)      │
│  ────────────────────────────────────────────────────   │
│  When:                                                  │
│    - System RPS < demand                                │
│    - CPU utilization > 70% across all pods              │
│    - Request queue building up                          │
│                                                         │
│  Actions:                                               │
│    1. Increase pod count (HPA)                          │
│    2. Verify load balancing working                     │
│    3. Check for bottlenecks (DB, storage)               │
│                                                         │
│  Example:                                               │
│    Current: 2 pods × 2 RPS = 4 RPS total                │
│    Target: 10 RPS total                                 │
│    Solution: Scale to 5 pods (10 / 2 = 5)               │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

**Decision Flowchart:**
```
Is single request too slow?
  ├─ Yes → Vertical Scaling
  │         ├─ Check CPU efficiency
  │         ├─ Increase cores if efficient
  │         └─ Or switch to smaller model
  │
  └─ No → Is system throughput too low?
            ├─ Yes → Horizontal Scaling
            │         ├─ Check CPU utilization
            │         ├─ Scale pods if high CPU
            │         └─ Check for bottlenecks
            │
            └─ No → System is healthy
```

### 5. Performance Report Structure

```markdown
# PERFORMANCE_REPORT.md

## Executive Summary
- System Status: ✅ All 91 tests passing
- CPU Characteristics: Nhiều cores (efficient up to 4 cores)
- Recommended Scaling: Horizontal (add pods for throughput)

## 1. System Testing Results
- Total Tests: 91
- Pass Rate: 100%
- Coverage: 85%
- Slow Tests: 3 (>5s)

## 2. CPU Characteristics
- Scaling Efficiency: 83% at 4 cores
- Answer: Service benefits from "nhiều cores yếu"
- Optimal: 4 cores per pod
- Diminishing returns: >4 cores

## 3. Audio Benchmarking
- RTF Range: 0.07 - 0.11 (excellent)
- Memory Usage: 500MB - 1.2GB
- Model Comparison: base 3x faster than small

## 4. Scaling Strategy
### Vertical Scaling (Single Request Speed)
- Increase CPU: 2.5 → 4 cores
- Expected: 40% latency reduction
- Cost: +60% per pod

### Horizontal Scaling (System Throughput)
- Increase Pods: 2 → 5
- Expected: 2.5x throughput
- Cost: +150% total

### Recommendation
- For <10 RPS: Vertical (4 cores/pod, 2 pods)
- For >10 RPS: Horizontal (2.5 cores/pod, 5+ pods)
```

## Implementation Details

### CPU Profiling Script

```python
# scripts/profile_cpu_scaling.py

def profile_cpu_scaling(model_size: str, audio_path: str):
    """Profile CPU scaling efficiency."""
    results = {}
    
    for cpu_count in [1, 2, 4, 8]:
        # Run benchmark in Docker with CPU limit
        cmd = [
            "docker", "run", "--rm",
            f"--cpus={cpu_count}",
            "stt-api",
            "python", "scripts/benchmark.py",
            "--model-size", model_size,
            "--audio", audio_path,
            "--iterations", "50"
        ]
        
        result = subprocess.run(cmd, capture_output=True)
        data = json.loads(result.stdout)
        
        results[cpu_count] = {
            "latency_ms": data["avg_latency_ms"],
            "rps": data["rps"],
            "cpu_utilization": measure_cpu_usage()
        }
    
    # Calculate scaling efficiency
    baseline = results[1]["latency_ms"]
    for cpu_count, data in results.items():
        speedup = baseline / data["latency_ms"]
        efficiency = speedup / cpu_count
        data["speedup"] = speedup
        data["efficiency"] = efficiency
    
    return results
```

### Test Runner Script

```python
# scripts/run_all_tests.py

def run_all_tests():
    """Run all tests with comprehensive reporting."""
    import pytest
    
    args = [
        "tests/",
        "--html=scripts/test_reports/test_report.html",
        "--self-contained-html",
        "--cov=.",
        "--cov-report=html:scripts/test_reports/coverage",
        "--json-report",
        "--json-report-file=scripts/test_reports/results.json",
        "-v"
    ]
    
    exit_code = pytest.main(args)
    
    # Generate summary
    with open("scripts/test_reports/results.json") as f:
        results = json.load(f)
    
    summary = {
        "total": results["summary"]["total"],
        "passed": results["summary"]["passed"],
        "failed": results["summary"]["failed"],
        "coverage": get_coverage_percentage(),
        "slow_tests": find_slow_tests(results, threshold=5.0)
    }
    
    print(json.dumps(summary, indent=2))
    return exit_code
```

## Trade-offs and Decisions

| Decision | Alternative | Rationale |
|----------|-------------|-----------|
| Use Docker `--cpus` for CPU limiting | Use K8s resource limits | Docker easier to test locally, reproducible |
| Benchmark all 9 audio files | Use only benchmark_30s.wav | Need to understand duration vs processing time relationship |
| Test up to 8 cores | Test up to 16 cores | Diminishing returns typically appear at 4-8 cores |
| Generate markdown reports | Use Grafana dashboards | Markdown easier to version control and review |

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Benchmark takes 2-4 hours | High | Run overnight, parallelize where possible |
| CPU profiling requires different machines | Medium | Use Docker `--cpus` for local testing |
| Results vary between runs | Medium | Run 50+ iterations, use averages |
| Memory profiling overhead | Low | Use `tracemalloc` which has minimal overhead |

## Success Criteria

1. ✅ All 91 tests pass with >80% coverage
2. ✅ CPU scaling report answers: "Nhiều cores yếu hay ít cores mạnh?"
3. ✅ Scaling strategy document provides clear guidance
4. ✅ Performance report answers all 3 user questions
5. ✅ K8s deployment updated with benchmark-based sizing
