#!/bin/bash
set -e

echo "=== Installing system dependencies ==="
apt-get update && apt-get install -y --no-install-recommends ffmpeg wget libgomp1 curl && rm -rf /var/lib/apt/lists/*

echo "=== Installing uv ==="
pip install --no-cache-dir uv

echo "=== Syncing Python dependencies ==="
uv sync --frozen

echo "=== Setting up scripts ==="
chmod +x /app/scripts/download_whisper_artifacts.py || true
chmod +x /app/scripts/entrypoint.sh || true

echo "=== Checking model artifacts ==="
MODEL_SIZE=${WHISPER_MODEL_SIZE:-small}
MODEL_DIR="/app/models/whisper_${MODEL_SIZE}_xeon"
MODEL_FILE="$MODEL_DIR/ggml-${MODEL_SIZE}-q5_1.bin"

echo "Model size: $MODEL_SIZE"
echo "Model directory: $MODEL_DIR"
echo "Model file: $MODEL_FILE"

# Check if model file exists (not just directory)
if [ ! -f "$MODEL_FILE" ]; then
  echo "Model file not found, downloading artifacts..."
  
  # Download artifacts using uv run (ensures dependencies are available)
  uv run python /app/scripts/download_whisper_artifacts.py "$MODEL_SIZE"
  
  if [ ! -f "$MODEL_FILE" ]; then
    echo "Failed to download model file"
    exit 1
  fi
  echo "Model artifacts downloaded successfully"
else
  echo "Model file exists"
fi

# Verify required library files
echo "=== Verifying library files ==="
REQUIRED_FILES=(
  "$MODEL_DIR/libggml-base.so.0"
  "$MODEL_DIR/libggml-cpu.so.0"
  "$MODEL_DIR/libggml.so.0"
  "$MODEL_DIR/libwhisper.so"
)

for file in "${REQUIRED_FILES[@]}"; do
  if [ ! -f "$file" ]; then
    echo "Missing required file: $file"
    exit 1
  else
    echo "Found: $(basename $file)"
  fi
done

echo "=== Setting library path ==="
export LD_LIBRARY_PATH="$MODEL_DIR:$LD_LIBRARY_PATH"
echo "LD_LIBRARY_PATH=$LD_LIBRARY_PATH"

# Write LD_LIBRARY_PATH to a file that Python can read
echo "$LD_LIBRARY_PATH" > /tmp/ld_library_path.txt

echo "=== Starting uvicorn ==="
# Use --no-reload for production-like behavior with proper LD_LIBRARY_PATH
# For development, we sacrifice hot-reload to ensure library loading works
exec env LD_LIBRARY_PATH="$LD_LIBRARY_PATH" .venv/bin/uvicorn cmd.api.main:app --host 0.0.0.0 --port 8000
