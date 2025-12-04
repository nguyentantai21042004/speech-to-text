#!/bin/bash
set -e

echo "========== Whisper Dynamic Model Loading Entrypoint =========="

# Read model size from ENV (default: small)
MODEL_SIZE=${WHISPER_MODEL_SIZE:-small}
echo "🔧 Model Size: $MODEL_SIZE"

# Define model directory
MODEL_DIR="whisper_${MODEL_SIZE}_xeon"
echo "Model Directory: $MODEL_DIR"

# Download artifacts if not present
if [ ! -d "$MODEL_DIR" ]; then
    echo "Model artifacts not found, downloading..."
    python3 scripts/download_whisper_artifacts.py "$MODEL_SIZE"

    if [ $? -ne 0 ]; then
        echo "Failed to download model artifacts"
        exit 1
    fi
    echo "Model artifacts downloaded successfully"
else
    echo "Model artifacts already present"
fi

# Set library path
export LD_LIBRARY_PATH="$PWD/$MODEL_DIR:$LD_LIBRARY_PATH"
echo "LD_LIBRARY_PATH set to: $LD_LIBRARY_PATH"

echo "========== Starting Application =========="
echo ""

# Execute the command passed to the entrypoint
exec "$@"
