#!/bin/bash
# Benchmark all audio files with different model sizes
# Usage: ./scripts/benchmark_all_audio.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "=============================================="
echo "COMPREHENSIVE AUDIO BENCHMARK"
echo "=============================================="
echo "Project Root: $PROJECT_ROOT"
echo "Script Dir: $SCRIPT_DIR"
echo ""

# Check for audio files
AUDIO_DIR="$SCRIPT_DIR/test_audio"
if [ ! -d "$AUDIO_DIR" ]; then
    echo "ERROR: Audio directory not found: $AUDIO_DIR"
    exit 1
fi

AUDIO_COUNT=$(find "$AUDIO_DIR" -type f \( -name "*.wav" -o -name "*.mp3" -o -name "*.m4a" \) | wc -l | tr -d ' ')
echo "Found $AUDIO_COUNT audio files in $AUDIO_DIR"
echo ""

# List audio files with sizes
echo "Audio files to benchmark:"
echo "----------------------------------------------"
find "$AUDIO_DIR" -type f \( -name "*.wav" -o -name "*.mp3" -o -name "*.m4a" \) -exec ls -lh {} \; | awk '{print $5, $9}'
echo "----------------------------------------------"
echo ""

# Create results directory
RESULTS_DIR="$SCRIPT_DIR/benchmark_results"
mkdir -p "$RESULTS_DIR"

# Model sizes to test
MODELS=("base")  # Add "small" "medium" for comprehensive testing

# Iterations per audio file
ITERATIONS=5

for MODEL in "${MODELS[@]}"; do
    echo ""
    echo "=============================================="
    echo "Benchmarking with model: $MODEL"
    echo "=============================================="
    
    # Run benchmark
    cd "$PROJECT_ROOT"
    uv run python scripts/benchmark.py \
        --all-audio \
        --model-size "$MODEL" \
        --iterations "$ITERATIONS" \
        --language vi
    
    echo ""
    echo "Completed benchmark for model: $MODEL"
done

echo ""
echo "=============================================="
echo "BENCHMARK COMPLETE"
echo "=============================================="
echo "Results saved to: $RESULTS_DIR"
echo ""
echo "Generated reports:"
ls -la "$RESULTS_DIR"/*.md 2>/dev/null || echo "No markdown reports found"
ls -la "$RESULTS_DIR"/*.json 2>/dev/null || echo "No JSON reports found"
