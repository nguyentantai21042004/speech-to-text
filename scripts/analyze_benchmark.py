#!/usr/bin/env python3
"""
Benchmark Results Analyzer - Calculate Normalization Ratio and Sizing Recommendations.

This tool analyzes benchmark results from Mac M4 and K8s Xeon to calculate
the Normalization Ratio and provide resource sizing recommendations.

Usage:
    # Compare M4 and Xeon results
    python scripts/analyze_benchmark.py --m4 m4_base.json --xeon xeon_base.json

    # Calculate sizing for target RPS
    python scripts/analyze_benchmark.py --m4 m4_base.json --xeon xeon_base.json --target-rps 10

    # Generate markdown report
    python scripts/analyze_benchmark.py --m4 m4_base.json --xeon xeon_base.json --report

    # List all benchmark results
    python scripts/analyze_benchmark.py --list
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

RESULTS_DIR = PROJECT_ROOT / "scripts" / "benchmark_results"


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


@dataclass
class SizingRecommendation:
    """Resource sizing recommendation."""

    target_rps: float
    m4_cores_needed: float
    xeon_cores_needed: float
    recommended_pods: int
    cpu_per_pod: float
    memory_per_pod_gb: float


@dataclass
class NormalizationResult:
    """Normalization ratio calculation result."""

    ratio: float
    m4_latency_ms: float
    xeon_latency_ms: float
    m4_rps: float
    xeon_rps: float
    model_size: str
    calculated_at: str


def load_result(file_path: str) -> BenchmarkResult:
    """Load benchmark result from JSON file."""
    with open(file_path, "r") as f:
        data = json.load(f)
    return BenchmarkResult(**data)


def calculate_ratio(m4: BenchmarkResult, xeon: BenchmarkResult) -> NormalizationResult:
    """
    Calculate Normalization Ratio between M4 and Xeon.

    Ratio = Latency_Xeon / Latency_M4

    If ratio > 1: M4 is faster (1 M4 core = ratio Xeon cores)
    If ratio < 1: Xeon is faster
    """
    ratio = xeon.avg_latency_ms / m4.avg_latency_ms if m4.avg_latency_ms > 0 else 0

    return NormalizationResult(
        ratio=round(ratio, 2),
        m4_latency_ms=m4.avg_latency_ms,
        xeon_latency_ms=xeon.avg_latency_ms,
        m4_rps=m4.rps,
        xeon_rps=xeon.rps,
        model_size=m4.model_size,
        calculated_at=datetime.now().isoformat(),
    )


def calculate_sizing(
    target_rps: float, ratio: float, m4_rps: float, memory_per_model_gb: float = 1.0
) -> SizingRecommendation:
    """
    Calculate resource sizing for target RPS on Xeon cluster.

    Args:
        target_rps: Target requests per second
        ratio: Normalization ratio (Xeon latency / M4 latency)
        m4_rps: RPS achieved on M4 with 1 core
        memory_per_model_gb: Memory required per model instance

    Returns:
        SizingRecommendation with CPU and memory requirements
    """
    # Calculate M4 cores needed for target RPS
    m4_cores_needed = target_rps / m4_rps if m4_rps > 0 else 0

    # Convert to Xeon cores using ratio
    xeon_cores_needed = m4_cores_needed * ratio

    # Recommend pod distribution (2 pods minimum for HA)
    if xeon_cores_needed <= 2:
        recommended_pods = 2
    elif xeon_cores_needed <= 4:
        recommended_pods = 2
    elif xeon_cores_needed <= 8:
        recommended_pods = 3
    else:
        recommended_pods = max(2, int(xeon_cores_needed / 3) + 1)

    cpu_per_pod = xeon_cores_needed / recommended_pods

    return SizingRecommendation(
        target_rps=target_rps,
        m4_cores_needed=round(m4_cores_needed, 2),
        xeon_cores_needed=round(xeon_cores_needed, 2),
        recommended_pods=recommended_pods,
        cpu_per_pod=round(cpu_per_pod, 2),
        memory_per_pod_gb=memory_per_model_gb,
    )


def generate_markdown_report(
    m4: BenchmarkResult,
    xeon: BenchmarkResult,
    norm: NormalizationResult,
    sizing: Optional[SizingRecommendation] = None,
) -> str:
    """Generate markdown report comparing M4 and Xeon performance."""

    report = f"""# Whisper Benchmark Report

Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary

| Metric | Mac M4 | K8s Xeon | Ratio |
|--------|--------|----------|-------|
| Architecture | {m4.architecture} | {xeon.architecture} | - |
| CPU Model | {m4.cpu_model[:30]}... | {xeon.cpu_model[:30]}... | - |
| Avg Latency | {m4.avg_latency_ms:.2f} ms | {xeon.avg_latency_ms:.2f} ms | {norm.ratio:.2f}x |
| RPS (1 core) | {m4.rps:.2f} | {xeon.rps:.2f} | {m4.rps/xeon.rps:.2f}x |
| Model Size | {m4.model_size} | {xeon.model_size} | - |
| Iterations | {m4.iterations} | {xeon.iterations} | - |

## Normalization Ratio

**Ratio: {norm.ratio:.2f}**

This means:
- 1 M4 core ≈ {norm.ratio:.2f} Xeon cores for Whisper inference
- M4 is **{norm.ratio:.1f}x faster** than Xeon per core

## Interpretation

"""

    if norm.ratio > 1:
        report += f"""The Mac M4 is **{norm.ratio:.1f}x faster** than Xeon per CPU core for this workload.
This is expected due to Apple Silicon's optimized NEON instructions vs Xeon's AVX.

When sizing for Xeon deployment, multiply your M4 core requirements by **{norm.ratio:.2f}**.
"""
    else:
        report += f"""The Xeon is **{1/norm.ratio:.1f}x faster** than M4 per CPU core for this workload.
This may indicate AVX optimizations are working well on Xeon.

When sizing for Xeon deployment, divide your M4 core requirements by **{1/norm.ratio:.2f}**.
"""

    if sizing:
        report += f"""

## Resource Sizing Recommendation

**Target: {sizing.target_rps} RPS**

| Resource | Value |
|----------|-------|
| M4 Cores Needed | {sizing.m4_cores_needed} |
| Xeon Cores Needed | {sizing.xeon_cores_needed} |
| Recommended Pods | {sizing.recommended_pods} |
| CPU per Pod | {sizing.cpu_per_pod} cores |
| Memory per Pod | {sizing.memory_per_pod_gb} GB |

### Kubernetes Configuration

```yaml
# deployment.yaml
resources:
  requests:
    cpu: "{sizing.cpu_per_pod}"
    memory: "{sizing.memory_per_pod_gb}Gi"
  limits:
    cpu: "{sizing.cpu_per_pod + 0.5}"  # +0.5 for burst
    memory: "{sizing.memory_per_pod_gb + 0.5}Gi"

# HPA
spec:
  minReplicas: {sizing.recommended_pods}
  maxReplicas: {sizing.recommended_pods * 2}
```
"""

    report += f"""

## Raw Data

### Mac M4 Result
```json
{json.dumps(asdict(m4), indent=2)}
```

### K8s Xeon Result
```json
{json.dumps(asdict(xeon), indent=2)}
```

---
*Report generated by analyze_benchmark.py*
"""

    return report


def save_ratio_config(norm: NormalizationResult, output_path: str) -> None:
    """Save normalization ratio to config file."""
    config = {
        "normalization_ratio": norm.ratio,
        "m4_latency_ms": norm.m4_latency_ms,
        "xeon_latency_ms": norm.xeon_latency_ms,
        "m4_rps": norm.m4_rps,
        "xeon_rps": norm.xeon_rps,
        "model_size": norm.model_size,
        "calculated_at": norm.calculated_at,
        "description": f"1 M4 core = {norm.ratio} Xeon cores for Whisper {norm.model_size} model",
    }

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump(config, f, indent=2)

    print(f"💾 Ratio config saved to: {output_path}")


def list_results() -> None:
    """List all benchmark result files."""
    if not RESULTS_DIR.exists():
        print("No benchmark results found.")
        return

    results = list(RESULTS_DIR.glob("*.json"))
    if not results:
        print("No benchmark results found.")
        return

    print("\n" + "=" * 70)
    print("BENCHMARK RESULTS")
    print("=" * 70)
    print(f"{'File':<40} {'Arch':<10} {'Model':<8} {'Latency':<12} {'RPS':<8}")
    print("-" * 70)

    for result_file in sorted(results):
        try:
            result = load_result(str(result_file))
            arch = "M4" if "ARM" in result.architecture else "Xeon"
            print(
                f"{result_file.name:<40} {arch:<10} {result.model_size:<8} {result.avg_latency_ms:<12.2f} {result.rps:<8.2f}"
            )
        except Exception as e:
            print(f"{result_file.name:<40} Error: {e}")

    print("=" * 70)


def compare_results(result_files: list[str]) -> None:
    """Compare multiple benchmark result files."""
    print("\n" + "=" * 80)
    print("BENCHMARK COMPARISON")
    print("=" * 80)
    print(
        f"{'File':<30} {'Arch':<8} {'Model':<8} {'Latency (ms)':<15} {'RPS':<10} {'Docker':<8}"
    )
    print("-" * 80)

    for file_path in result_files:
        try:
            result = load_result(file_path)
            arch = "M4" if "ARM" in result.architecture else "Xeon"
            docker = "Yes" if result.is_docker else "No"
            name = Path(file_path).name[:28]
            print(
                f"{name:<30} {arch:<8} {result.model_size:<8} {result.avg_latency_ms:<15.2f} {result.rps:<10.2f} {docker:<8}"
            )
        except Exception as e:
            print(f"{file_path:<30} Error: {e}")

    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Whisper benchmark results and calculate sizing recommendations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--m4", type=str, help="Path to Mac M4 benchmark result JSON")
    parser.add_argument(
        "--xeon", type=str, help="Path to K8s Xeon benchmark result JSON"
    )
    parser.add_argument(
        "--target-rps",
        type=float,
        default=10.0,
        help="Target RPS for sizing calculation (default: 10)",
    )
    parser.add_argument(
        "--report", action="store_true", help="Generate markdown report"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file for report (default: stdout)",
    )
    parser.add_argument(
        "--save-ratio", action="store_true", help="Save ratio to config file"
    )
    parser.add_argument(
        "--list", action="store_true", help="List all benchmark result files"
    )
    parser.add_argument(
        "--compare", nargs="+", type=str, help="Compare multiple result files"
    )

    args = parser.parse_args()

    # List results
    if args.list:
        list_results()
        return

    # Compare results
    if args.compare:
        compare_results(args.compare)
        return

    # Require both M4 and Xeon results for analysis
    if not args.m4 or not args.xeon:
        parser.print_help()
        print("\n❌ Error: Both --m4 and --xeon arguments are required for analysis")
        sys.exit(1)

    # Load results
    print("📊 Loading benchmark results...")
    try:
        m4_result = load_result(args.m4)
        print(f"   M4: {args.m4}")
    except Exception as e:
        print(f"❌ Failed to load M4 result: {e}")
        sys.exit(1)

    try:
        xeon_result = load_result(args.xeon)
        print(f"   Xeon: {args.xeon}")
    except Exception as e:
        print(f"❌ Failed to load Xeon result: {e}")
        sys.exit(1)

    # Validate model sizes match
    if m4_result.model_size != xeon_result.model_size:
        print(
            f"⚠️  Warning: Model sizes don't match (M4: {m4_result.model_size}, Xeon: {xeon_result.model_size})"
        )

    # Calculate normalization ratio
    print("\n📐 Calculating Normalization Ratio...")
    norm = calculate_ratio(m4_result, xeon_result)

    print("\n" + "=" * 60)
    print("NORMALIZATION RATIO")
    print("=" * 60)
    print(f"M4 Latency:    {norm.m4_latency_ms:.2f} ms")
    print(f"Xeon Latency:  {norm.xeon_latency_ms:.2f} ms")
    print(f"Ratio:         {norm.ratio:.2f}")
    print("-" * 60)
    print(f"➡️  1 M4 core ≈ {norm.ratio:.2f} Xeon cores")
    print("=" * 60)

    # Calculate sizing
    print(f"\n📏 Calculating sizing for {args.target_rps} RPS...")
    sizing = calculate_sizing(args.target_rps, norm.ratio, m4_result.rps)

    print("\n" + "=" * 60)
    print(f"SIZING RECOMMENDATION (Target: {args.target_rps} RPS)")
    print("=" * 60)
    print(f"M4 Cores Needed:     {sizing.m4_cores_needed}")
    print(f"Xeon Cores Needed:   {sizing.xeon_cores_needed}")
    print(f"Recommended Pods:    {sizing.recommended_pods}")
    print(f"CPU per Pod:         {sizing.cpu_per_pod} cores")
    print(f"Memory per Pod:      {sizing.memory_per_pod_gb} GB")
    print("=" * 60)

    # Save ratio config
    if args.save_ratio:
        ratio_path = RESULTS_DIR / "ratio_config.json"
        save_ratio_config(norm, str(ratio_path))

    # Generate report
    if args.report:
        report = generate_markdown_report(m4_result, xeon_result, norm, sizing)

        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write(report)
            print(f"\n📄 Report saved to: {args.output}")
        else:
            print("\n" + report)


if __name__ == "__main__":
    main()
