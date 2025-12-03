#!/usr/bin/env python3
"""
Whisper Benchmark Tool - Measure real-world inference performance.

This tool measures actual Whisper inference performance to calculate
the Normalization Ratio between Mac M4 (dev) and K8s Xeon (prod).

Usage:
    # Basic benchmark (50 iterations, base model)
    python scripts/benchmark.py

    # Custom iterations and model
    python scripts/benchmark.py --iterations 100 --model-size small

    # Save results to file
    python scripts/benchmark.py --output results/m4_base.json

    # Multi-thread stress test
    python scripts/benchmark.py --stress

    # Run in Docker with CPU isolation (recommended)
    docker run --rm --cpus="1" stt-api python scripts/benchmark.py
"""

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Setup logging
try:
    from core.logger import logger, configure_script_logging
    from core.config import get_settings

    settings = get_settings()
    configure_script_logging(level=settings.script_log_level)
except ImportError:
    from loguru import logger

    logger.remove()
    logger.add(
        sys.stdout,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
    )


@dataclass
class BenchmarkResult:
    """Benchmark result data structure."""

    timestamp: str
    architecture: str
    cpu_model: str
    model_size: str
    iterations: int
    avg_latency_ms: float
    total_time_s: float
    rps: float
    cpu_limit: int
    memory_mb: int
    is_docker: bool
    hostname: str
    python_version: str


def detect_architecture() -> str:
    """Detect CPU architecture (ARM64 or x86_64)."""
    machine = platform.machine().lower()
    if machine in ("arm64", "aarch64"):
        return "ARM64"
    elif machine in ("x86_64", "amd64"):
        return "x86_64"
    return machine


def detect_cpu_model() -> str:
    """Detect CPU model name."""
    system = platform.system()

    if system == "Linux":
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if line.startswith("model name"):
                        return line.split(":")[1].strip()
        except Exception:
            pass

    elif system == "Darwin":  # macOS
        try:
            result = subprocess.run(
                ["sysctl", "-n", "machdep.cpu.brand_string"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

        # Fallback for Apple Silicon
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.model"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return f"Apple Silicon ({result.stdout.strip()})"
        except Exception:
            pass

    return "Unknown CPU"


def detect_memory_mb() -> int:
    """Detect total system memory in MB."""
    system = platform.system()

    if system == "Linux":
        try:
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal"):
                        # MemTotal: 16384000 kB
                        kb = int(line.split()[1])
                        return kb // 1024
        except Exception:
            pass

    elif system == "Darwin":
        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.memsize"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                bytes_mem = int(result.stdout.strip())
                return bytes_mem // (1024 * 1024)
        except Exception:
            pass

    return 0


def is_running_in_docker() -> bool:
    """Check if running inside a Docker container."""
    # Check for .dockerenv file
    if os.path.exists("/.dockerenv"):
        return True

    # Check cgroup for docker/containerd
    try:
        with open("/proc/1/cgroup", "r") as f:
            content = f.read()
            if "docker" in content or "containerd" in content:
                return True
    except Exception:
        pass

    return False


def get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-show_entries",
                "format=duration",
                "-of",
                "csv=p=0",
                audio_path,
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
    except Exception:
        pass
    return 0.0


def get_cpu_limit() -> int:
    """Get CPU limit (from cgroup if in container, else physical cores)."""
    if is_running_in_docker():
        # Try cgroup v2
        try:
            with open("/sys/fs/cgroup/cpu.max", "r") as f:
                content = f.read().strip()
                if content != "max":
                    quota, period = content.split()
                    if quota != "max":
                        return max(1, int(quota) // int(period))
        except Exception:
            pass

        # Try cgroup v1
        try:
            with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us", "r") as f:
                quota = int(f.read().strip())
            with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us", "r") as f:
                period = int(f.read().strip())
            if quota > 0:
                return max(1, quota // period)
        except Exception:
            pass

    # Fallback to physical cores
    return os.cpu_count() or 1


def load_test_audio() -> str:
    """
    Load standardized test audio file for benchmarking.

    Priority:
    1. Use benchmark_30s.wav if exists
    2. Look for any existing .wav or .mp3 file
    3. Create synthetic 30s audio using ffmpeg

    Returns:
        Path to test audio file
    """
    test_audio_dir = PROJECT_ROOT / "scripts" / "test_audio"
    test_audio_path = test_audio_dir / "benchmark_30s.wav"

    # Priority 1: Use standardized benchmark audio
    if test_audio_path.exists():
        duration = get_audio_duration(str(test_audio_path))
        logger.success(
            f"Using standardized benchmark audio: {test_audio_path} ({duration:.1f}s)"
        )
        return str(test_audio_path)

    # Priority 2: Look for any existing audio file and convert to 30s wav
    if test_audio_dir.exists():
        for audio_file in test_audio_dir.glob("*.wav"):
            return str(audio_file)
        for audio_file in test_audio_dir.glob("*.mp3"):
            return str(audio_file)

    # Create synthetic test audio using ffmpeg
    logger.warning("No test audio found, creating synthetic 30s audio...")
    test_audio_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Generate 30 seconds of silence with some noise
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "anoisesrc=d=30:c=pink:r=16000:a=0.1",
                "-ar",
                "16000",
                "-ac",
                "1",
                str(test_audio_path),
            ],
            capture_output=True,
            check=True,
            timeout=60,
        )
        logger.success(f"Created test audio: {test_audio_path}")
        return str(test_audio_path)
    except Exception as e:
        logger.error(f"Failed to create test audio: {e}")
        raise RuntimeError("No test audio available and cannot create synthetic audio")


def run_warmup(adapter, audio_path: str, language: str = "vi") -> None:
    """Run warmup inference (not counted in benchmark)."""
    logger.info("Running warmup inference...")
    try:
        adapter.transcribe(audio_path, language=language)
        logger.success("Warmup complete")
    except Exception as e:
        logger.warning(f"Warmup failed (continuing anyway): {e}")


def run_benchmark(
    adapter, audio_path: str, iterations: int, language: str = "vi"
) -> tuple[float, float, float]:
    """
    Run benchmark iterations and return timing results.

    Returns:
        Tuple of (avg_latency_ms, total_time_s, rps)
    """
    logger.info(f"Running {iterations} benchmark iterations...")

    latencies = []
    start_total = time.perf_counter()

    for i in range(iterations):
        start = time.perf_counter()
        try:
            adapter.transcribe(audio_path, language=language)
        except Exception as e:
            logger.warning(f"Iteration {i+1} failed: {e}")
            continue
        end = time.perf_counter()

        latency_ms = (end - start) * 1000
        latencies.append(latency_ms)

        if (i + 1) % 10 == 0 or i == 0:
            logger.info(f"Iteration {i+1}/{iterations}: {latency_ms:.2f}ms")

    end_total = time.perf_counter()
    total_time_s = end_total - start_total

    if not latencies:
        raise RuntimeError("All benchmark iterations failed")

    avg_latency_ms = sum(latencies) / len(latencies)
    rps = 1000 / avg_latency_ms if avg_latency_ms > 0 else 0

    return avg_latency_ms, total_time_s, rps


def run_stress_test(adapter, audio_path: str, language: str = "vi") -> dict:
    """
    Run multi-thread stress test to detect CPU throttling.

    Tests with thread counts [1, 2, 4] while keeping CPU limit at 1.
    """
    from core.config import get_settings

    logger.info("=" * 60)
    logger.info("MULTI-THREAD STRESS TEST")
    logger.info("=" * 60)
    logger.info("Testing for CPU throttling with different thread counts...")
    logger.info("CPU Limit: 1 core (if in container)")

    settings = get_settings()
    original_threads = settings.whisper_n_threads

    results = {}
    thread_counts = [1, 2, 4]
    iterations_per_test = 10

    for n_threads in thread_counts:
        logger.info(f"Testing with {n_threads} thread(s)...")

        # Update thread count in settings
        os.environ["WHISPER_N_THREADS"] = str(n_threads)

        latencies = []
        for i in range(iterations_per_test):
            start = time.perf_counter()
            try:
                adapter.transcribe(audio_path, language=language)
            except Exception as e:
                logger.warning(f"Failed: {e}")
                continue
            end = time.perf_counter()
            latencies.append((end - start) * 1000)

        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            results[n_threads] = avg_latency
            logger.info(f"Avg Latency: {avg_latency:.2f}ms")

    # Restore original thread count
    os.environ["WHISPER_N_THREADS"] = str(original_threads)

    # Analyze results
    logger.info("=" * 60)
    logger.info("STRESS TEST RESULTS")
    logger.info("=" * 60)

    baseline = results.get(1, 0)
    throttling_detected = False

    for threads, latency in sorted(results.items()):
        ratio = latency / baseline if baseline > 0 else 0
        status = "OK"
        if ratio > 2.0:
            status = "THROTTLING DETECTED"
            throttling_detected = True
            logger.warning(f"Threads: {threads}, Latency: {latency:.2f}ms - {status}")
        elif ratio > 1.5:
            status = "Degraded"
            logger.warning(f"Threads: {threads}, Latency: {latency:.2f}ms - {status}")
        else:
            logger.info(f"Threads: {threads}, Latency: {latency:.2f}ms - {status}")

    if throttling_detected:
        logger.warning("THROTTLING DETECTED!")
        logger.info("Recommendations:")
        logger.info("1. Keep thread count at 1 for this CPU limit")
        logger.info("2. Or increase CPU limit to match thread count")
    else:
        logger.success("No throttling detected")

    return {
        "results": results,
        "throttling_detected": throttling_detected,
        "baseline_latency_ms": baseline,
    }


def save_results(result: BenchmarkResult, output_path: str) -> None:
    """Save benchmark results to JSON file."""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(asdict(result), f, indent=2)

    logger.success(f"Results saved to: {output_path}")


def print_results(result: BenchmarkResult) -> None:
    """Print benchmark results to console."""
    logger.info("=" * 60)
    logger.info("BENCHMARK RESULTS")
    logger.info("=" * 60)
    logger.info(f"Timestamp:      {result.timestamp}")
    logger.info(f"Architecture:   {result.architecture}")
    logger.info(f"CPU Model:      {result.cpu_model}")
    logger.info(f"Model Size:     {result.model_size}")
    logger.info(f"Iterations:     {result.iterations}")
    logger.info(f"CPU Limit:      {result.cpu_limit} core(s)")
    logger.info(f"Memory:         {result.memory_mb} MB")
    logger.info(f"Docker:         {'Yes' if result.is_docker else 'No'}")
    logger.info("-" * 60)
    logger.info(f"Avg Latency:    {result.avg_latency_ms:.2f} ms")
    logger.info(f"Total Time:     {result.total_time_s:.2f} s")
    logger.info(f"RPS:            {result.rps:.2f} req/s")
    logger.info("=" * 60)

    if not result.is_docker:
        logger.warning("Not running in Docker container!")
        logger.warning("Results may be inaccurate due to multi-core usage.")
        logger.info('For accurate benchmarks, run with: docker run --cpus="1" ...')


def get_all_audio_files() -> list[Path]:
    """Get all audio files from test_audio directory."""
    test_audio_dir = PROJECT_ROOT / "scripts" / "test_audio"
    audio_files = []

    if test_audio_dir.exists():
        for ext in ["*.wav", "*.mp3", "*.m4a", "*.mp4"]:
            audio_files.extend(test_audio_dir.glob(ext))

    # Sort by file size
    audio_files.sort(key=lambda f: f.stat().st_size)
    return audio_files


def calculate_rtf(processing_time_s: float, audio_duration_s: float) -> float:
    """
    Calculate Real-Time Factor (RTF).

    RTF < 1.0 means faster than real-time.
    RTF = processing_time / audio_duration
    """
    if audio_duration_s <= 0:
        return 0.0
    return processing_time_s / audio_duration_s


def run_memory_profiled_benchmark(
    adapter, audio_path: str, iterations: int, language: str = "vi"
) -> tuple[float, float, float, float]:
    """
    Run benchmark with memory profiling.

    Returns:
        Tuple of (avg_latency_ms, total_time_s, rps, peak_memory_mb)
    """
    import tracemalloc

    tracemalloc.start()

    latencies = []
    start_total = time.perf_counter()

    for i in range(iterations):
        start = time.perf_counter()
        try:
            adapter.transcribe(audio_path, language=language)
        except Exception as e:
            logger.warning(f"Iteration {i+1} failed: {e}")
            continue
        end = time.perf_counter()
        latencies.append((end - start) * 1000)

    end_total = time.perf_counter()
    total_time_s = end_total - start_total

    # Get peak memory
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_memory_mb = peak / (1024 * 1024)

    if not latencies:
        return 0.0, total_time_s, 0.0, peak_memory_mb

    avg_latency_ms = sum(latencies) / len(latencies)
    rps = 1000 / avg_latency_ms if avg_latency_ms > 0 else 0

    return avg_latency_ms, total_time_s, rps, peak_memory_mb


def benchmark_all_audio(
    adapter, model_size: str, iterations: int = 5, language: str = "vi"
) -> list[dict]:
    """
    Benchmark all audio files in test_audio directory.

    Returns:
        List of benchmark results for each audio file
    """
    audio_files = get_all_audio_files()

    if not audio_files:
        logger.error("No audio files found in scripts/test_audio/")
        return []

    logger.info(f"Found {len(audio_files)} audio files to benchmark")
    results = []

    for audio_file in audio_files:
        file_size_mb = audio_file.stat().st_size / (1024 * 1024)
        audio_duration = get_audio_duration(str(audio_file))

        logger.info(f"\nBenchmarking: {audio_file.name}")
        logger.info(f"  Size: {file_size_mb:.2f} MB")
        logger.info(f"  Duration: {audio_duration:.1f}s")

        # Run benchmark with memory profiling
        avg_latency_ms, total_time_s, rps, peak_memory_mb = (
            run_memory_profiled_benchmark(
                adapter, str(audio_file), iterations, language
            )
        )

        if avg_latency_ms == 0:
            logger.warning(f"  Skipped (all iterations failed)")
            continue

        rtf = calculate_rtf(avg_latency_ms / 1000, audio_duration)

        result = {
            "file_name": audio_file.name,
            "file_size_mb": round(file_size_mb, 2),
            "audio_duration_s": round(audio_duration, 1),
            "avg_latency_ms": round(avg_latency_ms, 2),
            "rps": round(rps, 4),
            "rtf": round(rtf, 3),
            "peak_memory_mb": round(peak_memory_mb, 2),
            "model_size": model_size,
            "iterations": iterations,
        }
        results.append(result)

        logger.info(f"  Latency: {avg_latency_ms:.2f}ms")
        logger.info(f"  RTF: {rtf:.3f}")
        logger.info(f"  Peak Memory: {peak_memory_mb:.2f}MB")

    return results


def save_all_audio_results(results: list[dict], model_size: str) -> None:
    """Save all-audio benchmark results."""
    results_dir = PROJECT_ROOT / "scripts" / "benchmark_results"
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Save JSON
    json_path = results_dir / f"all_audio_{model_size}_{timestamp}.json"
    with open(json_path, "w") as f:
        json.dump(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "model_size": model_size,
                "results": results,
            },
            f,
            indent=2,
        )
    logger.success(f"Results saved to: {json_path}")

    # Generate markdown report
    md_path = results_dir / "audio_benchmark_report.md"
    md_content = f"""# Audio Benchmark Report

## Configuration
- Model Size: {model_size}
- Timestamp: {datetime.now().isoformat()}

## Results

| File | Size (MB) | Duration (s) | Latency (ms) | RTF | Memory (MB) |
|------|-----------|--------------|--------------|-----|-------------|
"""
    for r in results:
        md_content += f"| {r['file_name']} | {r['file_size_mb']} | {r['audio_duration_s']} | {r['avg_latency_ms']} | {r['rtf']} | {r['peak_memory_mb']} |\n"

    md_content += """
## RTF Analysis

- RTF < 0.1: Excellent (10x faster than real-time)
- RTF < 0.5: Good (2x faster than real-time)
- RTF < 1.0: Acceptable (faster than real-time)
- RTF > 1.0: Problematic (slower than real-time)
"""

    with open(md_path, "w") as f:
        f.write(md_content)
    logger.success(f"Markdown report saved to: {md_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Whisper Benchmark Tool - Measure inference performance",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=50,
        help="Number of benchmark iterations (default: 50)",
    )
    parser.add_argument(
        "--model-size",
        "-m",
        type=str,
        default="base",
        choices=["base", "small", "medium"],
        help="Whisper model size (default: base)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output JSON file path (optional)",
    )
    parser.add_argument(
        "--stress", action="store_true", help="Run multi-thread stress test"
    )
    parser.add_argument(
        "--language",
        "-l",
        type=str,
        default="vi",
        help="Language code for transcription (default: vi)",
    )
    parser.add_argument(
        "--audio", type=str, default=None, help="Path to test audio file (optional)"
    )
    parser.add_argument(
        "--all-audio",
        action="store_true",
        help="Benchmark all audio files in test_audio directory",
    )
    parser.add_argument(
        "--cpu-profile",
        action="store_true",
        help="Run CPU scaling profiler instead of standard benchmark",
    )
    parser.add_argument(
        "--memory-profile",
        action="store_true",
        help="Enable memory profiling with tracemalloc",
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=0,
        help="Number of concurrent requests to simulate (0 = disabled)",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("WHISPER BENCHMARK TOOL")
    logger.info("=" * 60)

    # Detect system info
    architecture = detect_architecture()
    cpu_model = detect_cpu_model()
    memory_mb = detect_memory_mb()
    cpu_limit = get_cpu_limit()
    is_docker = is_running_in_docker()

    logger.info(f"Architecture:   {architecture}")
    logger.info(f"CPU Model:      {cpu_model}")
    logger.info(f"Memory:         {memory_mb} MB")
    logger.info(f"CPU Limit:      {cpu_limit} core(s)")
    logger.info(f"Docker:         {'Yes' if is_docker else 'No'}")
    logger.info(f"Model Size:     {args.model_size}")
    logger.info(f"Iterations:     {args.iterations}")

    # Set model size environment variable
    os.environ["WHISPER_MODEL_SIZE"] = args.model_size

    # Import and initialize adapter
    logger.info("Loading Whisper model...")
    try:
        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        adapter = WhisperLibraryAdapter(model_size=args.model_size)
        logger.success("Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        sys.exit(1)

    # Load test audio
    audio_path = args.audio or load_test_audio()
    logger.info(f"Test audio: {audio_path}")

    # Run warmup
    run_warmup(adapter, audio_path, args.language)

    # Run CPU profiler if requested
    if args.cpu_profile:
        logger.info("Running CPU scaling profiler...")
        from scripts.profile_cpu_scaling import (
            profile_cpu_scaling,
            print_report,
            save_report,
        )

        report = profile_cpu_scaling(model_size=args.model_size, language=args.language)
        print_report(report)
        return

    # Run stress test if requested
    if args.stress:
        stress_results = run_stress_test(adapter, audio_path, args.language)
        return

    # Run all-audio benchmark if requested
    if args.all_audio:
        results = benchmark_all_audio(
            adapter, args.model_size, args.iterations, args.language
        )
        save_all_audio_results(results, args.model_size)
        return

    # Run benchmark
    avg_latency_ms, total_time_s, rps = run_benchmark(
        adapter, audio_path, args.iterations, args.language
    )

    # Create result object
    result = BenchmarkResult(
        timestamp=datetime.now(timezone.utc).isoformat(),
        architecture=architecture,
        cpu_model=cpu_model,
        model_size=args.model_size,
        iterations=args.iterations,
        avg_latency_ms=round(avg_latency_ms, 2),
        total_time_s=round(total_time_s, 2),
        rps=round(rps, 2),
        cpu_limit=cpu_limit,
        memory_mb=memory_mb,
        is_docker=is_docker,
        hostname=platform.node(),
        python_version=platform.python_version(),
    )

    # Print results
    print_results(result)

    # Save results if output path specified
    if args.output:
        save_results(result, args.output)
    else:
        # Auto-generate output path
        results_dir = PROJECT_ROOT / "scripts" / "benchmark_results"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        arch_short = "m4" if "ARM" in architecture else "xeon"
        auto_output = results_dir / f"{arch_short}_{args.model_size}_{timestamp}.json"
        save_results(result, str(auto_output))


if __name__ == "__main__":
    main()
