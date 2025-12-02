# Design: Deployment Benchmark System

## Context

Dự án STT API cần deploy từ môi trường dev (Mac M4) lên production (K8s Xeon). Vấn đề:
- Whisper model được compile cho Linux, không chạy native trên macOS
- Hiệu năng giữa M4 (ARM64, Apple Silicon) và Xeon (x86_64) khác nhau đáng kể
- Cần quy trình chuẩn để sizing resource K8s dựa trên benchmark thực tế

## Goals / Non-Goals

### Goals
- Tạo benchmark tool đo hiệu năng thực tế với Whisper inference
- Tính Normalization Ratio giữa M4 và Xeon
- Cung cấp sizing recommendations cho K8s deployment
- Phát hiện CPU throttling khi dùng multi-thread

### Non-Goals
- Không benchmark các model khác ngoài Whisper (base/small/medium)
- Không tự động deploy - chỉ cung cấp recommendations
- Không benchmark GPU (chỉ CPU)

## Decisions

### Decision 1: Sử dụng actual inference code thay vì synthetic benchmark
**Rationale**: Mỗi model dùng tập lệnh CPU khác nhau (AVX, NEON). Chỉ có chạy code thật mới ra con số thật.

### Decision 2: CPU isolation với `--cpus="1"` 
**Rationale**: Đảm bảo so sánh công bằng 1 core M4 vs 1 core Xeon. Không dùng `--cpus` sẽ dùng hết tất cả cores.

### Decision 3: QoS Guaranteed cho benchmark Pod
**Rationale**: Đặt requests=limits để K8s cấp dedicated CPU, tránh tranh chấp với pods khác.

### Decision 4: JSON output format
**Rationale**: Dễ parse, compare, và tích hợp với CI/CD pipelines.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Benchmark Workflow                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │  Mac M4 Dev  │    │  K8s Xeon    │    │  Analyzer        │   │
│  │  (Docker)    │    │  (Pod)       │    │                  │   │
│  ├──────────────┤    ├──────────────┤    ├──────────────────┤   │
│  │ benchmark.py │───▶│ benchmark.py │───▶│ analyze_bench.py │   │
│  │ --cpus="1"   │    │ cpu: "1"     │    │                  │   │
│  └──────────────┘    └──────────────┘    └──────────────────┘   │
│         │                   │                     │              │
│         ▼                   ▼                     ▼              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────┐   │
│  │ m4_result.   │    │ xeon_result. │    │ sizing_report.md │   │
│  │ json         │    │ json         │    │ ratio_config.json│   │
│  └──────────────┘    └──────────────┘    └──────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. Benchmark Script (`scripts/benchmark.py`)

```python
# Key functions:
def load_model(model_size: str) -> WhisperModel
def run_warmup(model, audio_data) -> None
def run_benchmark(model, audio_data, iterations: int) -> BenchmarkResult
def detect_architecture() -> str  # ARM64 or x86_64
def detect_cpu_model() -> str
def save_results(result: BenchmarkResult, output_path: str) -> None
```

**Output JSON Schema:**
```json
{
  "timestamp": "2024-12-02T10:30:00Z",
  "architecture": "x86_64",
  "cpu_model": "Intel Xeon E5-2680 v4",
  "model_size": "base",
  "iterations": 50,
  "avg_latency_ms": 500.0,
  "total_time_s": 25.0,
  "rps": 2.0,
  "cpu_limit": 1,
  "memory_mb": 1024
}
```

### 2. K8s Benchmark Pod (`k8s/bench-pod.yaml`)

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: benchmark-xeon
spec:
  containers:
  - name: bench
    image: your-registry/stt-api:latest
    command: ["python", "scripts/benchmark.py", "--output", "/results/xeon_result.json"]
    resources:
      limits:
        cpu: "1"
        memory: "2Gi"
      requests:
        cpu: "1"
        memory: "2Gi"
  restartPolicy: Never
```

### 3. Analyzer Script (`scripts/analyze_benchmark.py`)

```python
# Key functions:
def load_results(m4_path: str, xeon_path: str) -> Tuple[Result, Result]
def calculate_ratio(m4: Result, xeon: Result) -> float
def calculate_sizing(target_rps: float, ratio: float, m4_rps: float) -> SizingRecommendation
def generate_report(m4: Result, xeon: Result, ratio: float, sizing: SizingRecommendation) -> str
```

### 4. Stress Test (`scripts/benchmark.py --stress`)

Test với thread counts [1, 2, 4] và CPU limit = 1:
- Nếu latency tăng >2x khi tăng threads → Throttling detected
- Output comparison table

## File Structure

```
scripts/
├── benchmark.py           # Main benchmark tool
├── analyze_benchmark.py   # Results analyzer
└── benchmark_results/     # Results storage
    ├── m4_base_2024-12-02.json
    ├── xeon_base_2024-12-02.json
    └── ratio_config.json

k8s/
├── bench-pod.yaml         # Benchmark Pod manifest
└── deployment.yaml        # Updated with benchmark-based sizing
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Benchmark results vary between runs | Run 50+ iterations, use average |
| Different audio samples give different results | Use standardized test audio (30s sample) |
| Network latency affects audio download | Use local test audio file |
| Model loading time varies | Exclude from measurement, run warmup |

## Migration Plan

1. **Phase 1**: Implement benchmark tool và test trên Mac M4
2. **Phase 2**: Deploy benchmark Pod lên K8s, collect Xeon results
3. **Phase 3**: Calculate ratio, update K8s deployment.yaml
4. **Phase 4**: Document quy trình trong README

## Open Questions

- [ ] Nên dùng audio sample nào làm chuẩn? (Đề xuất: 30s Vietnamese speech)
- [ ] Có cần benchmark với different audio lengths không?
- [ ] Có cần tích hợp vào CI/CD để auto-benchmark khi build image mới?
