# Implementation Tasks

## 1. Benchmark Tool Core
- [x] 1.1 Create `scripts/benchmark.py` with CLI interface (argparse)
  - Arguments: `--iterations`, `--model-size`, `--output`, `--stress`
- [x] 1.2 Implement model loading and warmup logic
  - Load WhisperLibraryAdapter
  - Run 1 warmup inference (not counted)
- [x] 1.3 Implement benchmark loop with timing
  - Use `time.perf_counter()` for accurate timing
  - Calculate avg_latency, total_time, rps
- [x] 1.4 Implement architecture and CPU detection
  - `platform.machine()` for architecture
  - Parse `/proc/cpuinfo` (Linux) or `sysctl` (macOS) for CPU model
- [x] 1.5 Implement JSON output with schema validation
  - Include all required fields: timestamp, architecture, cpu_model, model_size, iterations, avg_latency_ms, rps, cpu_limit

## 2. Test Audio Setup
- [x] 2.1 Use existing standardized test audio file
  - 30 seconds Vietnamese speech
  - Store in `scripts/test_audio/benchmark_30s.wav`
- [x] 2.2 Add audio file to Docker image or download on first run
  - Dockerfile already copies `scripts/` folder including test_audio
  - benchmark.py auto-creates synthetic audio if not found

## 3. Mac M4 Docker Integration
- [x] 3.1 Create `scripts/run_benchmark_mac.sh` helper script
  - Build image, run with `--cpus="1"`
  - Copy results from container via volume mount
- [x] 3.2 Add warning detection for non-Docker runs
  - Check if running in container via `/.dockerenv` or cgroup
  - Print warning in `print_results()` if not in Docker
- [ ] 3.3 Test benchmark on Mac M4 with Docker Desktop
  - Manual testing required by user

## 4. K8s Benchmark Pod
- [x] 4.1 Create `k8s/bench-pod.yaml` manifest
  - QoS Guaranteed (requests=limits, cpu: "1", memory: "2Gi")
  - restartPolicy: Never
  - Volume mount for results and whisper models
  - Includes stress test Pod variant
- [x] 4.2 Create `k8s/bench-configmap.yaml` for benchmark config
  - BENCHMARK_ITERATIONS, BENCHMARK_MODEL_SIZE, BENCHMARK_OUTPUT_PATH
  - WHISPER_LANGUAGE, WHISPER_ARTIFACTS_DIR
- [ ] 4.3 Test benchmark Pod on Xeon cluster
  - Manual testing required by user

## 5. Multi-thread Stress Test
- [x] 5.1 Implement `--stress` mode in benchmark.py
  - Test with thread counts [1, 2, 4]
  - Keep CPU limit at 1
- [x] 5.2 Implement throttling detection logic
  - Flag if latency increases >2x with `throttling_detected` flag
- [x] 5.3 Generate comparison table output
  - Table with Threads, Avg Latency, Status columns

## 6. Results Analyzer
- [x] 6.1 Create `scripts/analyze_benchmark.py`
  - Load M4 and Xeon result files with `load_result()`
- [x] 6.2 Implement Normalization Ratio calculation
  - `calculate_ratio()`: ratio = latency_xeon / latency_m4
- [x] 6.3 Implement sizing calculator
  - `calculate_sizing()`: target_rps, ratio, m4_rps → SizingRecommendation
- [x] 6.4 Implement markdown report generator
  - `generate_markdown_report()`: Summary table, ratio, K8s config
- [x] 6.5 Save ratio to `scripts/benchmark_results/ratio_config.json`
  - `save_ratio_config()` with `--save-ratio` flag

## 7. Results Management
- [x] 7.1 Create `scripts/benchmark_results/` directory structure
  - Created with `.gitkeep` file
- [x] 7.2 Implement results history (append, not overwrite)
  - Filename format: `{arch}_{model}_{timestamp}.json` in benchmark.py
- [x] 7.3 Implement results comparison function
  - `compare_results()` in analyze_benchmark.py with `--compare` flag

## 8. Documentation
- [x] 8.1 Create `document/benchmark-guide.md` with benchmark instructions
  - How to run on Mac M4 (helper script + manual)
  - How to run on K8s Xeon (Pod deployment)
  - How to analyze results (analyze_benchmark.py)
- [x] 8.2 Add example output and sizing calculation
  - Example JSON output, Normalization Ratio, Sizing Recommendation
- [x] 8.3 Document troubleshooting (throttling, inaccurate results)
  - CPU isolation, throttling detection, model loading

## 9. K8s Deployment Updates
- [x] 9.1 Update `k8s/deployment.yaml` with benchmark-based resource limits
  - Added sizing calculation comments
  - Updated CPU requests to 2.5 cores, limits to 3 cores
- [x] 9.2 Update HPA thresholds based on benchmark data
  - CPU target 70%, Memory target 75%
  - Conservative scale-down (25% per minute)
  - Fast scale-up (immediate, max 2 pods per 30s)

## 10. Validation (Manual Testing Required)
- [ ] 10.1 Run full benchmark cycle: Mac M4 → Xeon → Analyze
  - `./scripts/run_benchmark_mac.sh`
  - `kubectl apply -f k8s/bench-pod.yaml`
  - `python scripts/analyze_benchmark.py --m4 <m4.json> --xeon <xeon.json>`
- [ ] 10.2 Verify sizing recommendations match expected performance
  - Deploy with recommended resources
  - Load test to verify target RPS achieved
- [ ] 10.3 Run stress test and verify throttling detection works
  - `./scripts/run_benchmark_mac.sh --stress`
  - Verify throttling warning appears when latency >2x
