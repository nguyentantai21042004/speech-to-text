#!/usr/bin/env python3
"""
Comprehensive test runner with pytest integration.

This script runs all tests with detailed reporting including:
- HTML report generation
- JSON results export
- Test execution timing
- Slow test detection
- Coverage reporting
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def get_project_root() -> Path:
    """Get the project root directory."""
    return Path(__file__).parent.parent


def ensure_report_directory(report_dir: Path) -> None:
    """Ensure the report directory exists."""
    report_dir.mkdir(parents=True, exist_ok=True)


def run_pytest(
    report_dir: Path,
    verbose: bool = True,
    coverage: bool = True,
    html_report: bool = True,
    json_report: bool = True,
    slow_threshold: float = 5.0,
) -> tuple[int, dict]:
    """
    Run pytest with comprehensive reporting.

    Args:
        report_dir: Directory to store reports
        verbose: Enable verbose output
        coverage: Enable coverage reporting
        html_report: Generate HTML report
        json_report: Generate JSON report
        slow_threshold: Threshold in seconds for slow test detection

    Returns:
        Tuple of (exit_code, results_dict)
    """
    project_root = get_project_root()
    tests_dir = project_root / "tests"

    # Build pytest arguments - run from tests directory to avoid 'cmd' module conflict
    # The 'cmd' folder in project root shadows Python's built-in 'cmd' module
    # Use --import-mode=importlib to avoid adding project root to sys.path
    args = [
        sys.executable,
        "-m",
        "pytest",
        ".",  # Run tests from current directory (tests/)
        "-v" if verbose else "",
        f"--durations=0",  # Show all test durations
        f"--rootdir={project_root}",  # Set root for proper path resolution
        "--import-mode=importlib",  # Avoid sys.path manipulation
        "-p",
        "no:cacheprovider",  # Disable cache to avoid path issues
    ]

    # Add HTML report
    if html_report:
        html_path = report_dir / "test_report.html"
        args.extend(
            [
                f"--html={html_path}",
                "--self-contained-html",
            ]
        )

    # Add JSON report
    json_path = report_dir / "results.json"
    if json_report:
        args.extend(
            [
                "--json-report",
                f"--json-report-file={json_path}",
            ]
        )

    # Add coverage
    if coverage:
        coverage_dir = report_dir / "coverage"
        args.extend(
            [
                f"--cov={project_root}",
                "--cov-report=term-missing",
                f"--cov-report=html:{coverage_dir}",
                f"--cov-report=json:{report_dir / 'coverage.json'}",
                f"--cov-config={project_root / '.coveragerc'}",
            ]
        )

    # Filter empty args
    args = [a for a in args if a]

    # Set up environment - EXCLUDE project root from PYTHONPATH to avoid 'cmd' module conflict
    # The 'cmd' folder in project root shadows Python's built-in 'cmd' module
    env = os.environ.copy()

    # Clear PYTHONPATH completely to avoid 'cmd' module conflict
    # Tests use importlib workaround to import cmd.api.main
    env["PYTHONPATH"] = ""

    # Run pytest from tests directory
    start_time = time.time()
    result = subprocess.run(
        args,
        cwd=tests_dir,  # Run from tests directory
        capture_output=False,
        env=env,
    )
    elapsed_time = time.time() - start_time

    # Parse results
    results = {
        "exit_code": result.returncode,
        "elapsed_time": elapsed_time,
        "timestamp": datetime.now().isoformat(),
    }

    # Parse JSON report if available
    if json_report and json_path.exists():
        with open(json_path) as f:
            json_results = json.load(f)
            results["summary"] = json_results.get("summary", {})
            results["tests"] = json_results.get("tests", [])

    # Parse coverage if available
    coverage_json = report_dir / "coverage.json"
    if coverage and coverage_json.exists():
        with open(coverage_json) as f:
            cov_data = json.load(f)
            results["coverage"] = {
                "total_percent": cov_data.get("totals", {}).get("percent_covered", 0),
                "covered_lines": cov_data.get("totals", {}).get("covered_lines", 0),
                "missing_lines": cov_data.get("totals", {}).get("missing_lines", 0),
            }

    return result.returncode, results


def find_slow_tests(results: dict, threshold: float = 5.0) -> list[dict]:
    """Find tests that took longer than the threshold."""
    slow_tests = []
    for test in results.get("tests", []):
        duration = test.get("duration", 0)
        if duration > threshold:
            slow_tests.append(
                {
                    "name": test.get("nodeid", "unknown"),
                    "duration": duration,
                }
            )
    return sorted(slow_tests, key=lambda x: x["duration"], reverse=True)


def generate_summary(results: dict, slow_threshold: float = 5.0) -> dict:
    """Generate a summary of test results."""
    summary = results.get("summary", {})
    slow_tests = find_slow_tests(results, slow_threshold)

    return {
        "timestamp": results.get("timestamp"),
        "elapsed_time_seconds": round(results.get("elapsed_time", 0), 2),
        "total_tests": summary.get("total", 0),
        "passed": summary.get("passed", 0),
        "failed": summary.get("failed", 0),
        "skipped": summary.get("skipped", 0),
        "errors": summary.get("error", 0),
        "coverage_percent": results.get("coverage", {}).get("total_percent", 0),
        "slow_tests_count": len(slow_tests),
        "slow_tests": slow_tests,
        "status": "PASSED" if results.get("exit_code", 1) == 0 else "FAILED",
    }


def print_summary(summary: dict) -> None:
    """Print a formatted summary to console."""
    print("\n" + "=" * 60)
    print("TEST EXECUTION SUMMARY")
    print("=" * 60)
    print(f"Status: {summary['status']}")
    print(f"Timestamp: {summary['timestamp']}")
    print(f"Total Time: {summary['elapsed_time_seconds']}s")
    print("-" * 60)
    print(f"Total Tests: {summary['total_tests']}")
    print(f"  Passed: {summary['passed']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Skipped: {summary['skipped']}")
    print(f"  Errors: {summary['errors']}")
    print("-" * 60)
    print(f"Coverage: {summary['coverage_percent']:.1f}%")
    print("-" * 60)

    if summary["slow_tests"]:
        print(f"Slow Tests (>{5.0}s): {summary['slow_tests_count']}")
        for test in summary["slow_tests"][:10]:  # Show top 10
            print(f"  - {test['name']}: {test['duration']:.2f}s")
    else:
        print("No slow tests detected")

    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Run all tests with comprehensive reporting"
    )
    parser.add_argument(
        "--report-dir",
        type=str,
        default="scripts/test_reports",
        help="Directory to store reports (default: scripts/test_reports)",
    )
    parser.add_argument(
        "--no-coverage",
        action="store_true",
        help="Disable coverage reporting",
    )
    parser.add_argument(
        "--no-html",
        action="store_true",
        help="Disable HTML report generation",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Disable JSON report generation",
    )
    parser.add_argument(
        "--slow-threshold",
        type=float,
        default=5.0,
        help="Threshold in seconds for slow test detection (default: 5.0)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Quiet mode (less verbose output)",
    )

    args = parser.parse_args()

    # Setup
    project_root = get_project_root()
    report_dir = project_root / args.report_dir
    ensure_report_directory(report_dir)

    print(f"Running tests from: {project_root / 'tests'}")
    print(f"Reports will be saved to: {report_dir}")
    print()

    # Run tests
    exit_code, results = run_pytest(
        report_dir=report_dir,
        verbose=not args.quiet,
        coverage=not args.no_coverage,
        html_report=not args.no_html,
        json_report=not args.no_json,
        slow_threshold=args.slow_threshold,
    )

    # Generate and print summary
    summary = generate_summary(results, args.slow_threshold)
    print_summary(summary)

    # Save summary
    summary_path = report_dir / "summary.json"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary saved to: {summary_path}")

    # Print report locations
    if not args.no_html:
        print(f"HTML Report: {report_dir / 'test_report.html'}")
    if not args.no_json:
        print(f"JSON Results: {report_dir / 'results.json'}")
    if not args.no_coverage:
        print(f"Coverage Report: {report_dir / 'coverage' / 'index.html'}")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
