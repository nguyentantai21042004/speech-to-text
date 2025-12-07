# Performance Report

## Executive Summary

| Metric              | Status            | Details                                          |
| ------------------- | ----------------- | ------------------------------------------------ |
| System Tests        | ✅ 114/114 passed | All tests passing                                |
| CPU Characteristics | ✅ Analyzed       | Poor multi-core scaling - "ít cores mạnh"        |
| Scaling Strategy    | ✅ Documented     | See [SCALING_STRATEGY.md](./SCALING_STRATEGY.md) |

## 1. System Testing Results

### Test Execution Summary

```
Total Tests: 114
Passed: 114 (100%)
Failed: 0 (0%)
Skipped: 0
Errors: 0
Execution Time: ~4s
```

### Test Report Location

- HTML Report: `scripts/test_reports/test_report.html`
- JSON Results: `scripts/test_reports/results.json`
- Summary: `scripts/test_reports/summary.json`
- Testing Guide: [TESTING.md](./TESTING.md)

### Test Categories

| Category      | Tests | Description                               |
| ------------- | ----- | ----------------------------------------- |
| API Tests     | 15    | Endpoint validation, auth, error handling |
| Service Tests | 7     | TranscribeService business logic          |
| Config Tests  | 11    | Chunking configuration & validation       |
| Whisper Tests | 14    | Library adapter, model configs            |
| Logging Tests | 18    | Logger configuration & exports            |
| Audio Tests   | 49    | Validation, merge quality, thread safety  |

## 2. CPU Characteristics

### Profiling Results

| Cores | Latency (ms) | RPS    | Speedup | Efficiency |
| ----- | ------------ | ------ | ------- | ---------- |
| 1     | 10095.84     | 0.0991 | 1.00x   | 100%       |
| 2     | 10487.42     | 0.0954 | 0.96x   | 48%        |
| 4     | 11666.77     | 0.0857 | 0.87x   | 22%        |

### Analysis

- **Scaling Type**: Poor
- **Optimal Cores**: 1
- **Diminishing Returns**: At 2 cores

### Answer: "Nhiều cores yếu hay ít cores mạnh?"

**Answer: Ít cores mạnh** (Fewer but stronger cores)

The Whisper service does NOT scale well with multiple cores in this environment. Adding more cores actually increases latency due to:

1. Thread contention
2. Memory bandwidth limitations
3. Emulation overhead (Docker on ARM)

**Note**: These results were obtained in Docker emulation (VirtualApple @ 2.50GHz). Real Xeon performance may differ.

### Recommendations

1. **For single request speed**: Use 1-2 cores per pod with high clock speed
2. **For throughput**: Scale horizontally (more pods) rather than vertically (more cores per pod)
3. **Thread tuning**: Set `WHISPER_N_THREADS=1` or `2` for optimal performance

## 3. Scaling Strategy

### When to Scale Vertically (Scale Up)

Use vertical scaling when:

- Single request latency exceeds SLA
- CPU utilization is low (<50%)
- Memory is the bottleneck

Actions:

- Increase memory (for larger models)
- Use faster CPU (higher clock speed)
- Do NOT add more cores (poor scaling)

### When to Scale Horizontally (Scale Out)

Use horizontal scaling when:

- System throughput is insufficient
- CPU utilization is high (>70%)
- Request queue is building up

Actions:

- Add more pods via HPA
- Keep 1-2 cores per pod
- Ensure load balancing is working

### Decision Matrix

| Symptom        | CPU Util | Action                   |
| -------------- | -------- | ------------------------ |
| High latency   | Low      | Increase CPU clock speed |
| High latency   | High     | Add more pods            |
| Low throughput | Low      | Check bottlenecks        |
| Low throughput | High     | Add more pods            |

## 4. Benchmark Scripts

### Available Scripts

| Script                   | Purpose              | Usage                                   |
| ------------------------ | -------------------- | --------------------------------------- |
| `run_all_tests.py`       | Run test suite       | `python scripts/run_all_tests.py`       |
| `profile_cpu_scaling.py` | CPU scaling analysis | `python scripts/profile_cpu_scaling.py` |
| `benchmark.py`           | Single benchmark     | `python scripts/benchmark.py`           |
| `benchmark_all_audio.sh` | All audio files      | `./scripts/benchmark_all_audio.sh`      |

### Running Benchmarks

```bash
# Run in Docker for accurate results
docker run --rm -v $(pwd):/app -w /app \
  -e WHISPER_ARTIFACTS_DIR=models \
  python:3.12-slim-bookworm \
  python scripts/profile_cpu_scaling.py
```

## 5. Recommendations

### Resource Configuration

```yaml
# Recommended K8s resources
resources:
  requests:
    cpu: "1000m" # 1 core (optimal for this workload)
    memory: "1Gi"
  limits:
    cpu: "2000m" # Allow burst to 2 cores
    memory: "2Gi"
```

### Environment Variables

```bash
WHISPER_N_THREADS=1        # Optimal thread count
WHISPER_MODEL_SIZE=base    # Balance speed/accuracy
WHISPER_CHUNK_ENABLED=true # For long audio
```

### HPA Configuration

```yaml
# Scale based on CPU, not cores
minReplicas: 2
maxReplicas: 10
targetCPUUtilization: 70%
```

## Appendix: Report Files

- CPU Scaling Report: `scripts/benchmark_results/cpu_scaling_report.md`
- Test Summary: `scripts/test_reports/summary.json`
- Scaling Strategy: `docs/SCALING_STRATEGY.md`
