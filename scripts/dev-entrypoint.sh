#!/bin/bash
set -e

echo "=== Dev Container Starting (Fast Mode) ==="

# Model check
MODEL_SIZE=${WHISPER_MODEL_SIZE:-base}
MODEL_DIR="/app/models/whisper_${MODEL_SIZE}_xeon"
MODEL_FILE="$MODEL_DIR/ggml-${MODEL_SIZE}-q5_1.bin"

echo "Model: $MODEL_SIZE"

# Download only if missing (cached in volume)
if [ ! -f "$MODEL_FILE" ]; then
  echo "Downloading model artifacts..."
  uv run python /app/scripts/download_whisper_artifacts.py "$MODEL_SIZE"
  
  if [ ! -f "$MODEL_FILE" ]; then
    echo "Failed to download model"
    exit 1
  fi
  echo "Downloaded"
else
  echo "Model cached"
fi

# Quick verify libraries
LIBS=("libggml-base.so.0" "libggml-cpu.so.0" "libggml.so.0" "libwhisper.so")
for lib in "${LIBS[@]}"; do
  [ ! -f "$MODEL_DIR/$lib" ] && echo "Missing: $lib" && exit 1
done
echo "Libraries OK"

# Set library path
export LD_LIBRARY_PATH="$MODEL_DIR:$LD_LIBRARY_PATH"

echo "=== Starting API (reload enabled) ==="
exec env LD_LIBRARY_PATH="$LD_LIBRARY_PATH" uv run uvicorn cmd.api.main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --reload \
  --reload-dir /app/cmd \
  --reload-dir /app/core \
  --reload-dir /app/services \
  --reload-dir /app/internal
