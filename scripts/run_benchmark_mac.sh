#!/bin/bash
# =============================================================================
# Mac M4 Benchmark Runner
# =============================================================================
# This script runs the Whisper benchmark on Mac M4 with proper CPU isolation.
# It builds the Docker image, runs benchmark with --cpus="1", and copies results.
#
# Usage:
#   ./scripts/run_benchmark_mac.sh [OPTIONS]
#
# Options:
#   -n, --iterations NUM    Number of benchmark iterations (default: 50)
#   -m, --model-size SIZE   Model size: base, small, medium (default: base)
#   -s, --stress            Run multi-thread stress test
#   -h, --help              Show this help message
#
# Examples:
#   ./scripts/run_benchmark_mac.sh
#   ./scripts/run_benchmark_mac.sh -n 100 -m small
#   ./scripts/run_benchmark_mac.sh --stress
# =============================================================================

set -e

# Default values
ITERATIONS=50
MODEL_SIZE="base"
STRESS_MODE=""
IMAGE_NAME="stt-api-bench"
CONTAINER_NAME="stt-benchmark-$$"
RESULTS_DIR="scripts/benchmark_results"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored message
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

# Show help
show_help() {
    head -30 "$0" | tail -25
    exit 0
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--iterations)
            ITERATIONS="$2"
            shift 2
            ;;
        -m|--model-size)
            MODEL_SIZE="$2"
            shift 2
            ;;
        -s|--stress)
            STRESS_MODE="--stress"
            shift
            ;;
        -h|--help)
            show_help
            ;;
        *)
            print_error "Unknown option: $1"
            show_help
            ;;
    esac
done

# Validate model size
if [[ ! "$MODEL_SIZE" =~ ^(base|small|medium)$ ]]; then
    print_error "Invalid model size: $MODEL_SIZE. Must be base, small, or medium."
    exit 1
fi

echo "============================================================"
echo "  MAC M4 BENCHMARK RUNNER"
echo "============================================================"
echo ""
print_info "Configuration:"
echo "  - Iterations:  $ITERATIONS"
echo "  - Model Size:  $MODEL_SIZE"
echo "  - CPU Limit:   1 core (isolated)"
echo "  - Stress Mode: ${STRESS_MODE:-disabled}"
echo ""

# Check Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker Desktop."
    exit 1
fi
print_success "Docker is running"

# Create results directory
mkdir -p "$RESULTS_DIR"

# Build Docker image
print_info "Building Docker image..."
docker build -t "$IMAGE_NAME" -f cmd/api/Dockerfile . || {
    print_error "Failed to build Docker image"
    exit 1
}
print_success "Docker image built: $IMAGE_NAME"

# Generate output filename
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="/app/scripts/benchmark_results/m4_${MODEL_SIZE}_${TIMESTAMP}.json"

# Prepare benchmark command
BENCH_CMD="python scripts/benchmark.py --iterations $ITERATIONS --model-size $MODEL_SIZE --output $OUTPUT_FILE"
if [[ -n "$STRESS_MODE" ]]; then
    BENCH_CMD="python scripts/benchmark.py --stress --model-size $MODEL_SIZE"
fi

# Run benchmark with CPU isolation
print_info "Running benchmark with CPU isolation (--cpus=\"1\")..."
echo ""
echo "============================================================"

docker run --rm \
    --name "$CONTAINER_NAME" \
    --cpus="1" \
    --memory="4g" \
    -e WHISPER_MODEL_SIZE="$MODEL_SIZE" \
    -v "$(pwd)/scripts/benchmark_results:/app/scripts/benchmark_results" \
    "$IMAGE_NAME" \
    /bin/bash -c "$BENCH_CMD"

DOCKER_EXIT_CODE=$?

echo "============================================================"
echo ""

if [[ $DOCKER_EXIT_CODE -eq 0 ]]; then
    print_success "Benchmark completed successfully!"
    
    # Find the latest result file
    LATEST_RESULT=$(ls -t "$RESULTS_DIR"/m4_*.json 2>/dev/null | head -1)
    if [[ -n "$LATEST_RESULT" ]]; then
        print_success "Results saved to: $LATEST_RESULT"
        echo ""
        echo "Result summary:"
        cat "$LATEST_RESULT" | python3 -m json.tool 2>/dev/null || cat "$LATEST_RESULT"
    fi
else
    print_error "Benchmark failed with exit code: $DOCKER_EXIT_CODE"
    exit $DOCKER_EXIT_CODE
fi

echo ""
echo "============================================================"
echo "  NEXT STEPS"
echo "============================================================"
echo "1. Run the same benchmark on K8s Xeon cluster"
echo "2. Use analyze_benchmark.py to calculate Normalization Ratio"
echo "3. Update k8s/deployment.yaml with recommended resource limits"
echo ""
