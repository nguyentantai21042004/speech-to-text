#!/usr/bin/env python3
"""
CPU Scaling Profiler - Analyze CPU scaling efficiency for Whisper inference.

This tool measures how well the Whisper service scales with different CPU counts
to answer: "Does the service need many weak cores or few strong cores?"

Usage:
    # Basic profiling (tests 1, 2, 4, 8 cores)
    python scripts/profile_cpu_scaling.py

    # Custom CPU counts
    python scripts/profile_cpu_scaling.py --cpu-counts 1,2,4

    # With specific model
    python scripts/profile_cpu_scaling.py --model-size small

    # Generate report only (use existing results)
    python scripts/profile_cpu_scaling.py --report-only

Note: For accurate results, run in Docker with --cpus flag or use cgroups.
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from dataclasses import dataclass, asdict, field
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
class CPUScalingResult:
    """Result for a single CPU count test."""

    cpu_count: int
    avg_latency_ms: float
    rps: float
    speedup: float = 1.0
    efficiency: float = 1.0
    iterations: int = 10


@dataclass
class CPUScalingReport:
    """Complete CPU scaling profiling report."""

    timestamp: str
    architecture: str
    cpu_model: str
    model_size: str
    audio_duration_s: float
    results: list = field(default_factory=list)
    recommendation: str = ""
    optimal_cores: int = 1
    diminishing_returns_point: int = 0
    scaling_type: str = ""  # "linear", "sub-linear", "poor"


def detect_architecture() -> str:
    """Detect CPU architecture."""
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

    elif system == "Darwin":
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

        try:
            result = subprocess.run(
                ["sysctl", "-n", "hw.model"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                return f"Apple Silicon ({result.stdout.strip()})"
        except Exception:
            pass

    return "Unknown CPU"


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
    return 30.0  # Default assumption


def load_test_audio() -> str:
    """Load test audio file."""
    test_audio_dir = PROJECT_ROOT / "scripts" / "test_audio"
    test_audio_path = test_audio_dir / "benchmark_30s.wav"

    if test_audio_path.exists():
        return str(test_audio_path)

    # Look for any audio file
    if test_audio_dir.exists():
        for audio_file in test_audio_dir.glob("*.wav"):
            return str(audio_file)
        for audio_file in test_audio_dir.glob("*.mp3"):
            return str(audio_file)

    raise RuntimeError(
        "No test audio found. Please add audio files to scripts/test_audio/"
    )


def run_benchmark_with_threads(
    adapter, audio_path: str, n_threads: int, iterations: int = 10, language: str = "vi"
) -> tuple[float, float]:
    """
    Run benchmark with specific thread count.

    Returns:
        Tuple of (avg_latency_ms, rps)
    """
    # Set thread count
    os.environ["WHISPER_N_THREADS"] = str(n_threads)

    latencies = []
    for i in range(iterations):
        start = time.perf_counter()
        try:
            adapter.transcribe(audio_path, language=language)
        except Exception as e:
            logger.warning(f"Iteration {i+1} failed: {e}")
            continue
        end = time.perf_counter()
        latencies.append((end - start) * 1000)

    if not latencies:
        return 0.0, 0.0

    avg_latency_ms = sum(latencies) / len(latencies)
    rps = 1000 / avg_latency_ms if avg_latency_ms > 0 else 0

    return avg_latency_ms, rps


def profile_cpu_scaling(
    model_size: str = "base",
    cpu_counts: list[int] = None,
    iterations: int = 10,
    audio_path: str = None,
    language: str = "vi",
) -> CPUScalingReport:
    """
    Profile CPU scaling efficiency.

    Args:
        model_size: Whisper model size
        cpu_counts: List of CPU counts to test
        iterations: Number of iterations per test
        audio_path: Path to test audio
        language: Language code

    Returns:
        CPUScalingReport with all results
    """
    if cpu_counts is None:
        cpu_counts = [1, 2, 4, 8]

    # Filter to available cores
    max_cores = os.cpu_count() or 8
    cpu_counts = [c for c in cpu_counts if c <= max_cores]

    logger.info("=" * 60)
    logger.info("CPU SCALING PROFILER")
    logger.info("=" * 60)

    architecture = detect_architecture()
    cpu_model = detect_cpu_model()

    logger.info(f"Architecture: {architecture}")
    logger.info(f"CPU Model: {cpu_model}")
    logger.info(f"Model Size: {model_size}")
    logger.info(f"CPU Counts to test: {cpu_counts}")
    logger.info(f"Iterations per test: {iterations}")

    # Set model size
    os.environ["WHISPER_MODEL_SIZE"] = model_size

    # Load adapter
    logger.info("Loading Whisper model...")
    try:
        from infrastructure.whisper.library_adapter import WhisperLibraryAdapter

        adapter = WhisperLibraryAdapter(model_size=model_size)
        logger.success("Model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        raise

    # Load audio
    if audio_path is None:
        audio_path = load_test_audio()
    audio_duration = get_audio_duration(audio_path)
    logger.info(f"Test audio: {audio_path} ({audio_duration:.1f}s)")

    # Warmup
    logger.info("Running warmup...")
    try:
        adapter.transcribe(audio_path, language=language)
        logger.success("Warmup complete")
    except Exception as e:
        logger.warning(f"Warmup failed: {e}")

    # Run profiling for each CPU count
    results = []
    baseline_latency = None

    for cpu_count in cpu_counts:
        logger.info(f"\nTesting with {cpu_count} thread(s)...")

        avg_latency_ms, rps = run_benchmark_with_threads(
            adapter, audio_path, cpu_count, iterations, language
        )

        if avg_latency_ms == 0:
            logger.warning(f"All iterations failed for {cpu_count} threads")
            continue

        # Calculate speedup and efficiency
        if baseline_latency is None:
            baseline_latency = avg_latency_ms

        speedup = baseline_latency / avg_latency_ms if avg_latency_ms > 0 else 0
        efficiency = speedup / cpu_count if cpu_count > 0 else 0

        result = CPUScalingResult(
            cpu_count=cpu_count,
            avg_latency_ms=round(avg_latency_ms, 2),
            rps=round(rps, 4),
            speedup=round(speedup, 2),
            efficiency=round(efficiency, 2),
            iterations=iterations,
        )
        results.append(result)

        logger.info(f"  Latency: {avg_latency_ms:.2f}ms")
        logger.info(f"  RPS: {rps:.4f}")
        logger.info(f"  Speedup: {speedup:.2f}x")
        logger.info(f"  Efficiency: {efficiency:.0%}")

    # Analyze results
    recommendation, optimal_cores, diminishing_point, scaling_type = analyze_scaling(
        results
    )

    report = CPUScalingReport(
        timestamp=datetime.now(timezone.utc).isoformat(),
        architecture=architecture,
        cpu_model=cpu_model,
        model_size=model_size,
        audio_duration_s=audio_duration,
        results=[asdict(r) for r in results],
        recommendation=recommendation,
        optimal_cores=optimal_cores,
        diminishing_returns_point=diminishing_point,
        scaling_type=scaling_type,
    )

    return report


def analyze_scaling(results: list[CPUScalingResult]) -> tuple[str, int, int, str]:
    """
    Analyze scaling results to determine recommendation.

    Returns:
        Tuple of (recommendation, optimal_cores, diminishing_returns_point, scaling_type)
    """
    if not results:
        return "No results to analyze", 1, 0, "unknown"

    # Find optimal cores (best efficiency above 70%)
    optimal_cores = 1
    for r in results:
        if r.efficiency >= 0.7:
            optimal_cores = r.cpu_count

    # Find diminishing returns point (efficiency drops below 50%)
    diminishing_point = 0
    for r in results:
        if r.efficiency < 0.5 and diminishing_point == 0:
            diminishing_point = r.cpu_count

    # Determine scaling type
    if len(results) >= 2:
        last_efficiency = results[-1].efficiency
        if last_efficiency >= 0.8:
            scaling_type = "linear"
        elif last_efficiency >= 0.5:
            scaling_type = "sub-linear"
        else:
            scaling_type = "poor"
    else:
        scaling_type = "unknown"

    # Generate recommendation
    if scaling_type == "linear":
        recommendation = (
            f"Service scales well with multiple cores (efficiency {results[-1].efficiency:.0%} at {results[-1].cpu_count} cores). "
            f"Recommendation: Use 'nhiều cores yếu' - more cores provide proportional speedup."
        )
    elif scaling_type == "sub-linear":
        recommendation = (
            f"Service shows sub-linear scaling. Optimal at {optimal_cores} cores (efficiency {results[optimal_cores-1].efficiency if optimal_cores <= len(results) else 0:.0%}). "
            f"Recommendation: Balance between core count and per-core performance."
        )
    else:
        recommendation = (
            f"Service shows poor multi-core scaling. "
            f"Recommendation: Use 'ít cores mạnh' - fewer but faster cores are more efficient."
        )

    return recommendation, optimal_cores, diminishing_point, scaling_type


def print_report(report: CPUScalingReport) -> None:
    """Print CPU scaling report to console."""
    logger.info("\n" + "=" * 70)
    logger.info("CPU SCALING REPORT")
    logger.info("=" * 70)
    logger.info(f"Timestamp:      {report.timestamp}")
    logger.info(f"Architecture:   {report.architecture}")
    logger.info(f"CPU Model:      {report.cpu_model}")
    logger.info(f"Model Size:     {report.model_size}")
    logger.info(f"Audio Duration: {report.audio_duration_s:.1f}s")
    logger.info("-" * 70)

    # Results table
    logger.info(
        f"{'Cores':<8} {'Latency (ms)':<15} {'RPS':<10} {'Speedup':<10} {'Efficiency':<12}"
    )
    logger.info("-" * 70)

    for r in report.results:
        eff_pct = f"{r['efficiency']:.0%}"
        logger.info(
            f"{r['cpu_count']:<8} {r['avg_latency_ms']:<15.2f} {r['rps']:<10.4f} "
            f"{r['speedup']:<10.2f}x {eff_pct:<12}"
        )

    logger.info("-" * 70)
    logger.info(f"Scaling Type:           {report.scaling_type}")
    logger.info(f"Optimal Cores:          {report.optimal_cores}")
    logger.info(f"Diminishing Returns At: {report.diminishing_returns_point or 'N/A'}")
    logger.info("-" * 70)
    logger.info(f"RECOMMENDATION: {report.recommendation}")
    logger.info("=" * 70)


def save_report(report: CPUScalingReport, output_path: str) -> None:
    """Save report to JSON file."""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(asdict(report), f, indent=2)

    logger.success(f"Report saved to: {output_path}")


def generate_markdown_report(report: CPUScalingReport, output_path: str) -> None:
    """Generate markdown report."""
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    md_content = f"""# CPU Scaling Report

## System Information

| Property | Value |
|----------|-------|
| Timestamp | {report.timestamp} |
| Architecture | {report.architecture} |
| CPU Model | {report.cpu_model} |
| Model Size | {report.model_size} |
| Audio Duration | {report.audio_duration_s:.1f}s |

## Scaling Results

| Cores | Latency (ms) | RPS | Speedup | Efficiency |
|-------|--------------|-----|---------|------------|
"""

    for r in report.results:
        md_content += f"| {r['cpu_count']} | {r['avg_latency_ms']:.2f} | {r['rps']:.4f} | {r['speedup']:.2f}x | {r['efficiency']:.0%} |\n"

    md_content += f"""
## Analysis

- **Scaling Type**: {report.scaling_type}
- **Optimal Cores**: {report.optimal_cores}
- **Diminishing Returns Point**: {report.diminishing_returns_point or 'N/A'}

## Recommendation

{report.recommendation}

## Answer: "Nhiều cores yếu hay ít cores mạnh?"

"""

    if report.scaling_type == "linear":
        md_content += "**Answer: Nhiều cores yếu** - The service scales efficiently with multiple cores.\n"
    elif report.scaling_type == "sub-linear":
        md_content += f"**Answer: Balanced** - Optimal at {report.optimal_cores} cores. Beyond that, diminishing returns.\n"
    else:
        md_content += "**Answer: Ít cores mạnh** - The service doesn't scale well with multiple cores.\n"

    with open(output_file, "w") as f:
        f.write(md_content)

    logger.success(f"Markdown report saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="CPU Scaling Profiler for Whisper inference",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
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
        "--cpu-counts",
        "-c",
        type=str,
        default="1,2,4,8",
        help="Comma-separated CPU counts to test (default: 1,2,4,8)",
    )
    parser.add_argument(
        "--iterations",
        "-n",
        type=int,
        default=10,
        help="Iterations per CPU count (default: 10)",
    )
    parser.add_argument(
        "--output", "-o", type=str, default=None, help="Output JSON file path"
    )
    parser.add_argument(
        "--audio", type=str, default=None, help="Path to test audio file"
    )
    parser.add_argument(
        "--language", "-l", type=str, default="vi", help="Language code (default: vi)"
    )

    args = parser.parse_args()

    # Parse CPU counts
    cpu_counts = [int(c.strip()) for c in args.cpu_counts.split(",")]

    # Run profiling
    report = profile_cpu_scaling(
        model_size=args.model_size,
        cpu_counts=cpu_counts,
        iterations=args.iterations,
        audio_path=args.audio,
        language=args.language,
    )

    # Print report
    print_report(report)

    # Save reports
    results_dir = PROJECT_ROOT / "scripts" / "benchmark_results"
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON report
    json_path = args.output or str(
        results_dir / f"cpu_scaling_{args.model_size}_{timestamp}.json"
    )
    save_report(report, json_path)

    # Markdown report
    md_path = str(results_dir / f"cpu_scaling_report.md")
    generate_markdown_report(report, md_path)


if __name__ == "__main__":
    main()
