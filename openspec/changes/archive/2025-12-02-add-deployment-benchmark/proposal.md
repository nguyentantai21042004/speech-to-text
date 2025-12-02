# Change: Add Deployment Benchmark System

## Why

Hiện tại source đang có vấn đề trong cách triển khai:
1. **Mô hình Whisper được huấn luyện để chạy trên Linux**, không phải macOS - nên phải chạy trong Docker container Linux, nhưng cách setup chưa chuẩn
2. **Cấu hình K8s chưa đạt chuẩn** - Dockerfile và deployment.yaml cần được tối ưu theo best practices
3. **Thiếu quy trình benchmark** để sizing resource chính xác khi deploy từ Mac M4 (dev) lên K8s Xeon (prod)

Cần một hệ thống benchmark để tính **Normalization Ratio** giữa Mac M4 và Xeon, từ đó sizing CPU/Memory chính xác cho production.

## What Changes

- **ADDED**: Benchmark tool (`scripts/benchmark.py`) để đo hiệu năng thực tế với Whisper inference
- **ADDED**: K8s benchmark Pod manifest (`k8s/bench-pod.yaml`) để chạy benchmark trên Xeon cluster
- **ADDED**: Benchmark results analyzer để tính Normalization Ratio và sizing recommendations
- **ADDED**: Multi-thread stress test để phát hiện CPU throttling
- **ADDED**: Spec mới `deployment-benchmark` định nghĩa quy trình benchmark chuẩn
- **MODIFIED**: Dockerfile - tối ưu multi-stage build, hỗ trợ cả ARM64 và x86_64
- **MODIFIED**: K8s deployment.yaml - cập nhật resource limits dựa trên benchmark results

## Impact

- Affected specs: `deployment-benchmark` (new), `clean-architecture` (minor)
- Affected code:
  - `scripts/benchmark.py` (new)
  - `scripts/analyze_benchmark.py` (new)
  - `k8s/bench-pod.yaml` (new)
  - `cmd/api/Dockerfile` (modified)
  - `k8s/deployment.yaml` (modified)
  - `docker-compose.yml` (modified - add CPU limit option)
