# Scaling Strategy Guide

This document provides comprehensive guidance for scaling the Speech-to-Text service based on performance profiling and benchmarking results.

## Table of Contents

1. [Overview](#overview)
2. [Vertical Scaling (Scale Up)](#vertical-scaling-scale-up)
3. [Horizontal Scaling (Scale Out)](#horizontal-scaling-scale-out)
4. [Decision Matrix](#decision-matrix)
5. [Metrics Thresholds](#metrics-thresholds)
6. [Cost Optimization](#cost-optimization)
7. [Troubleshooting](#troubleshooting)

## Overview

The STT service can be scaled in two ways:

| Strategy | Description | When to Use |
|----------|-------------|-------------|
| **Vertical Scaling** | Increase CPU/Memory per pod | Single request latency too high |
| **Horizontal Scaling** | Increase number of pods | System throughput too low |

### Key Metrics

- **Latency**: Time to process a single request (ms)
- **RPS**: Requests per second (throughput)
- **RTF**: Real-Time Factor (processing_time / audio_duration)
- **CPU Utilization**: Percentage of allocated CPU used
- **Memory Usage**: RAM consumption per pod

## Vertical Scaling (Scale Up)

### When to Scale Vertically

Use vertical scaling when:

1. **Single request latency exceeds SLA**
   - Current latency > target latency
   - CPU utilization < 70% (room for more cores)
   
2. **CPU scaling efficiency is good**
   - Efficiency > 70% at target core count
   - Linear or sub-linear scaling observed

3. **Memory is sufficient**
   - Peak memory < 80% of allocated
   - No OOM events

### How to Scale Vertically

#### Increase CPU

```yaml
# k8s/deployment.yaml
resources:
  requests:
    cpu: "2.5"      # Increase from current
    memory: "2Gi"
  limits:
    cpu: "4"        # Increase proportionally
    memory: "4Gi"
```

**Expected Impact:**
- 2.5 → 4 cores: ~40% latency reduction (if efficiency > 70%)
- Cost increase: ~60% per pod

#### Increase Memory

Only increase memory if:
- Processing large audio files (>10 minutes)
- OOM errors observed
- Using larger models (medium, large)

```yaml
resources:
  requests:
    memory: "4Gi"   # Increase for larger models
  limits:
    memory: "6Gi"
```

### Thread Tuning

Optimize `WHISPER_N_THREADS` based on CPU allocation:

| CPU Cores | Recommended Threads | Notes |
|-----------|---------------------|-------|
| 1 | 1 | Avoid over-subscription |
| 2 | 2 | Match core count |
| 4 | 4 | Optimal for most workloads |
| 8+ | 4-6 | Diminishing returns beyond 4 |

```yaml
env:
  - name: WHISPER_N_THREADS
    value: "4"
```

## Horizontal Scaling (Scale Out)

### When to Scale Horizontally

Use horizontal scaling when:

1. **System throughput is insufficient**
   - Total RPS < demand
   - Request queue building up
   
2. **CPU utilization is high across all pods**
   - Average CPU > 70%
   - All pods are busy

3. **Vertical scaling has diminishing returns**
   - Efficiency < 50% at current core count
   - Cost per performance is poor

### How to Scale Horizontally

#### Manual Scaling

```bash
kubectl scale deployment stt-api --replicas=5
```

#### HPA Configuration

```yaml
# k8s/deployment.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: stt-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: stt-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 60
      policies:
        - type: Pods
          value: 2
          periodSeconds: 60
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
        - type: Pods
          value: 1
          periodSeconds: 120
```

### Capacity Planning

Calculate required pods:

```
Required Pods = Target RPS / RPS per Pod

Example:
- Target: 10 RPS
- Single pod RPS: 2 RPS
- Required pods: 10 / 2 = 5 pods
```

## Decision Matrix

### Scaling Decision Flowchart

```
Is single request latency too high?
├── YES → Check CPU efficiency
│         ├── Efficiency > 70% → Vertical Scale (add CPU)
│         └── Efficiency < 70% → Consider smaller model or optimize
│
└── NO → Is system throughput too low?
          ├── YES → Check CPU utilization
          │         ├── CPU > 70% → Horizontal Scale (add pods)
          │         └── CPU < 70% → Check for bottlenecks
          │
          └── NO → System is healthy ✓
```

### Quick Reference Table

| Symptom | CPU Util | Efficiency | Action |
|---------|----------|------------|--------|
| High latency | < 70% | > 70% | Add CPU per pod |
| High latency | < 70% | < 70% | Use smaller model |
| Low throughput | > 70% | Any | Add more pods |
| Low throughput | < 70% | Any | Check bottlenecks |
| OOM errors | Any | Any | Add memory |

## Metrics Thresholds

### Recommended Thresholds

| Metric | Warning | Critical | Action |
|--------|---------|----------|--------|
| CPU Utilization | > 70% | > 85% | Scale out |
| Memory Usage | > 70% | > 85% | Increase memory |
| Request Latency | > 2s | > 5s | Scale up/out |
| RTF | > 0.5 | > 1.0 | Optimize or scale |
| Error Rate | > 1% | > 5% | Investigate |

### Prometheus Alerts

```yaml
groups:
  - name: stt-scaling
    rules:
      - alert: HighCPUUtilization
        expr: avg(rate(container_cpu_usage_seconds_total{pod=~"stt-api.*"}[5m])) > 0.7
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High CPU utilization - consider scaling"
          
      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{path="/transcribe"}[5m])) > 2
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High request latency - consider scaling"
```

## Cost Optimization

### Cost vs Performance Trade-offs

| Configuration | Cost | Latency | Throughput | Use Case |
|---------------|------|---------|------------|----------|
| 2 pods × 2 CPU | $$ | Medium | Low | Development |
| 2 pods × 4 CPU | $$$ | Low | Low | Low traffic, fast response |
| 4 pods × 2 CPU | $$$$ | Medium | Medium | Balanced |
| 4 pods × 4 CPU | $$$$$ | Low | High | Production |

### Recommendations by Traffic Level

| Daily Requests | Recommended Config | Estimated Cost |
|----------------|-------------------|----------------|
| < 1,000 | 2 pods × 2 CPU | $ |
| 1,000 - 10,000 | 2 pods × 4 CPU | $$ |
| 10,000 - 50,000 | 4 pods × 4 CPU | $$$ |
| > 50,000 | 8+ pods × 4 CPU + HPA | $$$$ |

### Cost Saving Tips

1. **Use HPA with conservative settings**
   - Scale down slowly (5 min stabilization)
   - Scale up quickly (1 min stabilization)

2. **Right-size resources**
   - Start small, scale based on metrics
   - Review and adjust monthly

3. **Use spot/preemptible instances**
   - For non-critical workloads
   - With proper pod disruption budgets

## Troubleshooting

### Common Issues

#### High Latency Despite Low CPU

**Possible causes:**
- Thread contention (too many threads)
- Memory pressure (swapping)
- I/O bottleneck (audio download)

**Solutions:**
1. Reduce `WHISPER_N_THREADS`
2. Increase memory allocation
3. Check network latency to audio sources

#### Pods Not Scaling

**Possible causes:**
- HPA metrics not available
- Resource limits too low
- Cluster capacity exhausted

**Solutions:**
1. Verify metrics-server is running
2. Check HPA status: `kubectl describe hpa stt-api-hpa`
3. Check cluster capacity: `kubectl describe nodes`

#### Uneven Load Distribution

**Possible causes:**
- Sticky sessions enabled
- Long-running requests
- Pod startup time

**Solutions:**
1. Disable session affinity
2. Implement request timeouts
3. Use readiness probes

### Diagnostic Commands

```bash
# Check HPA status
kubectl get hpa stt-api-hpa

# Check pod resource usage
kubectl top pods -l app=stt-api

# Check pod logs
kubectl logs -l app=stt-api --tail=100

# Describe deployment
kubectl describe deployment stt-api
```

## Appendix: Benchmark Results

See the following reports for detailed benchmark data:

- `scripts/benchmark_results/cpu_scaling_report.md` - CPU scaling analysis
- `scripts/benchmark_results/audio_benchmark_report.md` - Audio file benchmarks
- `docs/PERFORMANCE_REPORT.md` - Comprehensive performance report
