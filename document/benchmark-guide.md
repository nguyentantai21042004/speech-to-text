# Whisper Benchmark Guide

Hướng dẫn benchmark hiệu năng Whisper để tính Normalization Ratio giữa Mac M4 (dev) và K8s Xeon (prod).

## Tổng quan

Quy trình benchmark gồm 4 bước:

1. **Benchmark trên Mac M4** - Đo hiệu năng với CPU isolation
2. **Benchmark trên K8s Xeon** - Đo hiệu năng trên cluster production
3. **Tính Normalization Ratio** - So sánh M4 vs Xeon
4. **Sizing K8s Resources** - Tính CPU/Memory cho target RPS

## 1. Benchmark trên Mac M4

### Sử dụng Helper Script (Recommended)

```bash
# Basic benchmark (50 iterations, base model)
./scripts/run_benchmark_mac.sh

# Custom options
./scripts/run_benchmark_mac.sh -n 100 -m small

# Stress test để phát hiện throttling
./scripts/run_benchmark_mac.sh --stress
```

### Chạy Manual

```bash
# Build Docker image
docker build -t stt-api-bench -f cmd/api/Dockerfile .

# Chạy với CPU isolation (QUAN TRỌNG: --cpus="1")
docker run --rm \
    --cpus="1" \
    --memory="4g" \
    -e WHISPER_MODEL_SIZE=base \
    -v $(pwd)/scripts/benchmark_results:/app/scripts/benchmark_results \
    stt-api-bench \
    python scripts/benchmark.py --iterations 50 --model-size base
```

### Output

Kết quả được lưu tại `scripts/benchmark_results/m4_base_YYYYMMDD_HHMMSS.json`:

```json
{
  "timestamp": "2024-12-02T10:30:00Z",
  "architecture": "ARM64",
  "cpu_model": "Apple M4",
  "model_size": "base",
  "iterations": 50,
  "avg_latency_ms": 200.0,
  "total_time_s": 10.0,
  "rps": 5.0,
  "cpu_limit": 1,
  "memory_mb": 16384,
  "is_docker": true
}
```

## 2. Benchmark trên K8s Xeon

### Deploy Benchmark Pod

```bash
# Apply ConfigMap (chỉnh sửa nếu cần)
kubectl apply -f k8s/bench-configmap.yaml

# Deploy benchmark Pod
kubectl apply -f k8s/bench-pod.yaml

# Xem logs
kubectl logs -f benchmark-xeon -n stt

# Copy kết quả về local
kubectl cp stt/benchmark-xeon:/app/scripts/benchmark_results/xeon_result.json \
    ./scripts/benchmark_results/xeon_base_$(date +%Y%m%d_%H%M%S).json
```

### Stress Test trên K8s

```bash
# Deploy stress test Pod
kubectl delete pod benchmark-xeon-stress -n stt --ignore-not-found
kubectl apply -f k8s/bench-pod.yaml

# Xem logs của stress test
kubectl logs -f benchmark-xeon-stress -n stt
```

## 3. Phân tích kết quả

### Tính Normalization Ratio

```bash
# Liệt kê tất cả benchmark results
python scripts/analyze_benchmark.py --list

# Phân tích M4 vs Xeon
python scripts/analyze_benchmark.py \
    --m4 scripts/benchmark_results/m4_base_20241202_100000.json \
    --xeon scripts/benchmark_results/xeon_base_20241202_110000.json

# Tính sizing cho target 10 RPS
python scripts/analyze_benchmark.py \
    --m4 scripts/benchmark_results/m4_base_20241202_100000.json \
    --xeon scripts/benchmark_results/xeon_base_20241202_110000.json \
    --target-rps 10

# Tạo báo cáo markdown và lưu ratio config
python scripts/analyze_benchmark.py \
    --m4 scripts/benchmark_results/m4_base_20241202_100000.json \
    --xeon scripts/benchmark_results/xeon_base_20241202_110000.json \
    --report --save-ratio --output benchmark_report.md
```

### Ví dụ Output

```
============================================================
NORMALIZATION RATIO
============================================================
M4 Latency:    200.00 ms
Xeon Latency:  500.00 ms
Ratio:         2.50
------------------------------------------------------------
➡️  1 M4 core ≈ 2.50 Xeon cores
============================================================

============================================================
SIZING RECOMMENDATION (Target: 10 RPS)
============================================================
M4 Cores Needed:     2.0
Xeon Cores Needed:   5.0
Recommended Pods:    2
CPU per Pod:         2.5 cores
Memory per Pod:      1.0 GB
============================================================
```

## 4. Cập nhật K8s Deployment

Dựa trên kết quả benchmark, cập nhật `k8s/deployment.yaml`:

```yaml
resources:
  requests:
    cpu: "2.5" # Từ sizing recommendation
    memory: "1Gi"
  limits:
    cpu: "3" # +0.5 cho burst
    memory: "1.5Gi"
```

## Troubleshooting

### Kết quả không chính xác

**Vấn đề**: Latency trên Mac quá thấp so với thực tế

**Nguyên nhân**: Không chạy trong Docker với CPU isolation

**Giải pháp**:

- Luôn dùng `docker run --cpus="1"`
- Kiểm tra `is_docker: true` trong kết quả

### CPU Throttling

**Vấn đề**: Latency tăng vọt khi tăng số threads

**Nguyên nhân**: Nhiều threads tranh chấp 1 CPU core

**Giải pháp**:

- Giữ `WHISPER_N_THREADS=1` nếu CPU limit = 1
- Hoặc tăng CPU limit tương ứng với số threads

### Model Loading Chậm

**Vấn đề**: Benchmark đầu tiên chậm hơn nhiều

**Nguyên nhân**: Model chưa được cache

**Giải pháp**:

- Script đã có warmup inference
- Đảm bảo model artifacts đã được download trước

## Tham khảo

- [benmark-proposal.md](../benmark-proposal.md) - Đề xuất ban đầu
- [k8s/bench-pod.yaml](../k8s/bench-pod.yaml) - K8s benchmark manifests
- [scripts/benchmark.py](../scripts/benchmark.py) - Benchmark tool
- [scripts/analyze_benchmark.py](../scripts/analyze_benchmark.py) - Results analyzer
