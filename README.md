# Speech-to-Text System

A high-performance **stateless** Speech-to-Text (STT) API built with **FastAPI** and **Whisper.cpp**. Designed for simplicity, direct transcription, and minimal infrastructure dependencies.

---

## Key Features

### Core Capabilities

- **Direct Transcription** - Transcribe audio from URL with a single API call
- **Stateless Architecture** - No database, no message queue, no object storage
- **High-Quality STT** - Powered by Whisper.cpp with anti-hallucination filters
- **Multiple Languages** - Support for Vietnamese, English, and 90+ languages
- **Production-Ready** - Comprehensive logging, error handling, and health monitoring

### Dynamic Model Loading

- **Runtime Model Switching** - Change between small/medium models via environment variable
- **90% Faster** - Direct C library integration eliminates subprocess overhead
- **No Rebuild Required** - Single Docker image for all environments
- **Auto-Download** - Artifacts automatically downloaded from MinIO if missing
- **Memory Efficient** - Model loaded once at startup, reused for all requests

### Sequential Smart-Chunking (Production-Ready)

- **Long Audio Support** - Handle audio up to 30+ minutes without timeout
- **Flat Memory Usage** - Consistent ~500MB regardless of audio length
- **High Performance** - Process at 4-5x faster than realtime
- **Adaptive Timeout** - Automatic timeout calculation based on audio duration
- **Zero Timeout Errors** - Tested with 3-18 minute audio files (100% success rate)
- **Quality Preserved** - 98% confidence maintained across all chunk sizes

### Performance Optimizations

- **Direct Library Integration** - C library calls instead of subprocess spawning
- **Model Preloading** - Whisper model loaded once and reused (90% latency reduction)
- **In-Memory Caching** - Model validation cached to eliminate redundant I/O
- **Sequential Chunking** - Process long audio in 30s segments with 1s overlap
- **FFmpeg Integration** - Efficient audio splitting and format conversion
- **Immediate Cleanup** - Chunk files removed immediately after processing
- **Efficient Downloads** - Streaming audio download with size validation
- **Multi-threading** - Auto-detect CPU cores (up to 8 threads)

### Architecture Highlights

- **Stateless Design** - Each request is independent, no session state
- **Clean Architecture** - Service layer, dependency injection, interface-based design
- **Docker-Ready** - Minimal Docker setup with health checks
- **Simple Deployment** - Single service, no external dependencies

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Technology Stack](#technology-stack)
- [Quick Start](#quick-start)
- [Installation](#installation)
  - [Local Development](#local-development)
  - [Docker Deployment](#docker-deployment)
- [Dynamic Model Loading](#dynamic-model-loading-new)
- [API Documentation](#api-documentation)
- [Configuration](#configuration)
- [Project Structure](#project-structure)
- [Development Guide](#development-guide)
- [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### System Architecture

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Client     │─────▶│  API Service │─────▶│  Whisper.cpp │
│  (Request)   │      │  (FastAPI)   │      │     (STT)    │
└──────────────┘      └──────────────┘      └──────────────┘
                              │
                              ▼
                      ┌──────────────┐
                      │  Audio URL   │
                      │  (Download)  │
                      └──────────────┘
```

### Core Service

#### **API Service** (`cmd/api/main.py`)

- RESTful API with FastAPI
- `/transcribe` endpoint for direct transcription
- Downloads audio from provided URL
- Transcribes using Whisper.cpp
- Returns result immediately
- Health checks and monitoring

---

## Technology Stack

### Backend

| Technology      | Version | Purpose               |
| --------------- | ------- | --------------------- |
| **FastAPI**     | 0.104+  | Web framework         |
| **Pydantic**    | 2.5+    | Data validation       |
| **httpx**       | Latest  | Async HTTP client     |
| **Whisper.cpp** | Latest  | Speech-to-text engine |
| **Loguru**      | Latest  | Structured logging    |

### Code Organization

| Module                | Purpose                                              |
| --------------------- | ---------------------------------------------------- |
| **core/constants.py** | Centralized constants (Audio, HTTP, Whisper configs) |
| **core/errors.py**    | Centralized exceptions (STT, Whisper, Audio errors)  |
| **core/messages.py**  | Error and log message templates                      |

### Audio Processing

| Library    | Purpose                 |
| ---------- | ----------------------- |
| **FFmpeg** | Audio format conversion |

### Infrastructure

| Service            | Purpose                 |
| ------------------ | ----------------------- |
| **Docker**         | Containerization        |
| **Docker Compose** | Container orchestration |

---

## Quick Start

### Prerequisites

- **Python 3.12+**
- **Docker & Docker Compose** (for containerized deployment)
- **FFmpeg** (for audio processing)
- **Whisper.cpp** (compiled binary)

### 1. Clone Repository

```bash
git clone <repository-url>
cd speech2text
```

### 2. Environment Setup

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Install Dependencies

```bash
# Using uv (recommended)
uv sync

# Or using pip
pip install -e .
```

### 4. Start Service

#### Option A: Docker (Recommended)

```bash
# Start service with small model (default)
docker-compose up -d

# OR switch to medium model (no rebuild required!)
WHISPER_MODEL_SIZE=medium docker-compose up -d

# View logs
docker-compose logs -f api

# Stop service
docker-compose down
```

#### Option B: Local Development

```bash
# Start API
uv run python cmd/api/main.py

# Or with uvicorn directly
uv run uvicorn cmd.api.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Test the System

```bash
# Transcribe audio from URL
curl -X POST http://localhost:8000/transcribe \
  -H "Content-Type: application/json" \
  -d '{"audio_url": "http://example.com/audio.mp3"}'

# Check health
curl http://localhost:8000/health
```

---

## Dynamic Model Loading (NEW!)

### Overview

The system now supports **dynamic model loading** with direct C library integration, providing **60-90% performance improvement** over the previous CLI-based approach.

### Key Benefits

| Feature               | Benefit                                                                     |
| --------------------- | --------------------------------------------------------------------------- |
| **Runtime Switching** | Change models via `WHISPER_MODEL_SIZE=small\|medium` without Docker rebuild |
| **90% Faster**        | Direct C library calls eliminate subprocess overhead (2-3s → 0.1-0.3s)      |
| **Single Image**      | One Docker image works for all environments (dev/staging/prod)              |
| **Auto-Download**     | Artifacts automatically downloaded from MinIO if missing                    |
| **Memory Efficient**  | Model loaded once at startup, reused for all requests                       |

### Quick Start

#### Local Development

```bash
# Download model artifacts
make setup-artifacts-base      # Download base model (60MB, ~1GB RAM) - DEFAULT
make setup-artifacts-small     # Download small model (181MB, ~500MB RAM)
make setup-artifacts-medium    # Download medium model (1.5GB, ~2GB RAM)

# Run tests
make test-library             # Test library adapter
make test-integration         # Test model switching

# Run API
make run-api
```

#### Docker Deployment

```bash
# Run with base model (default)
docker-compose up

# Switch to other models (no rebuild!)
WHISPER_MODEL_SIZE=small docker-compose up
WHISPER_MODEL_SIZE=medium docker-compose up

# Or edit docker-compose.yml:
# WHISPER_MODEL_SIZE: base  # or small, medium
```

### Model Specifications

| Model      | Size   | RAM     | Use Case                             |
| ---------- | ------ | ------- | ------------------------------------ |
| **base**   | ~60 MB | ~1 GB   | Default balance of speed vs accuracy |
| **small**  | 181 MB | ~500 MB | Development, fast transcription      |
| **medium** | 1.5 GB | ~2 GB   | Production, high accuracy            |

### Performance Comparison

| Metric              | Before (CLI)  | After (Library) | Improvement              |
| ------------------- | ------------- | --------------- | ------------------------ |
| First request       | 2-3s          | 0.5-1s          | **60-75%**               |
| Subsequent requests | 2-3s          | 0.1-0.3s        | **90%**                  |
| Memory (small)      | ~200MB/req    | ~500MB total    | Constant                 |
| Model loads         | Every request | Once at startup | (Very large improvement) |

### Documentation

- [User Guide](docs/DYNAMIC_MODEL_LOADING_GUIDE.md)
- [Implementation Summary](IMPLEMENTATION_SUMMARY.md)
- [Change Log](CHANGES.md)

### Building / Updating Whisper Artifacts

If you need to regenerate shared libraries or quantized models (e.g., to add the **base** variant alongside `small`/`medium`), reuse the Xeon-optimized builder pipeline in [`nguyentantai21042004/whisper-xeon-builde`](https://github.com/nguyentantai21042004/whisper-xeon-builde). It ships Docker automation that compiles `libwhisper.so`, quantizes the requested models (base/small/medium), and publishes deployment-ready folders (`whisper_base_xeon/`, `whisper_small_xeon/`, …) suitable for this repo’s loader flow.[^builder-ref]

[^builder-ref]: Artifact build reference: [nguyentantai21042004/whisper-xeon-builde](https://github.com/nguyentantai21042004/whisper-xeon-builde)

### Makefile Commands

```bash
make help                     # Show all available commands
make setup-artifacts-small    # Download small model
make setup-artifacts-medium   # Download medium model
make test-library             # Test library adapter
make test-integration         # Test model switching
make clean-old                # Remove old/unused files
```

---

## API Documentation

### Interactive Documentation

- **Swagger UI** (Public): http://localhost:8000/swagger/index.html
- **FastAPI Docs** (Dev): http://localhost:8000/docs
- **ReDoc** (Dev): http://localhost:8000/redoc
- **OpenAPI Spec**: http://localhost:8000/openapi.json

### Endpoints

#### POST `/transcribe`

Transcribe audio from presigned URL (e.g., MinIO).

**Authentication:** Requires `X-API-Key` header with internal API key.

**Request:**

```json
{
  "media_url": "https://minio.internal/bucket/audio_123.mp3?token=xyz...",
  "language": "vi" // Optional: language hint (default: "vi")
}
```

**Response (Success):**

```json
{
  "status": "success",
  "transcription": "Nội dung video nói về xe VinFast VF3...",
  "duration": 45.5, // Audio duration in seconds
  "confidence": 0.98, // AI confidence score
  "processing_time": 2.1 // Processing time in seconds
}
```

**Response (Timeout):**

```json
{
  "status": "timeout",
  "transcription": "",
  "duration": 0.0,
  "confidence": 0.0,
  "processing_time": 0.0
}
```

**Error Responses:**

- `401` - Missing or invalid API key
- `413` - File too large
- `400` - Invalid URL or download failed
- `422` - Validation error (missing/invalid fields)
- `500` - Internal server error

**Example cURL:**

```bash
curl -X POST http://localhost:8000/transcribe \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key-here" \
  -d '{
    "media_url": "https://minio.internal/bucket/audio_123.mp3?token=xyz",
    "language": "vi"
  }'
```

#### POST `/api/v1/transcribe` (Async)

Submit async transcription job with polling pattern. Ideal for long audio files (> 1 minute).

**Authentication:** Requires `X-API-Key` header.

**Request:**

```json
{
  "request_id": "post_123456", // Client-generated ID (e.g., post_id from Crawler)
  "media_url": "https://minio.internal/bucket/audio.mp3?token=xyz",
  "language": "vi" // Optional (default: "vi")
}
```

**Response (202 Accepted):**

```json
{
  "request_id": "post_123456",
  "status": "PROCESSING",
  "message": "Job submitted successfully"
}
```

**Idempotency:** If job with same `request_id` exists, returns current status without creating new job.

#### GET `/api/v1/transcribe/{request_id}` (Polling)

Poll job status until COMPLETED or FAILED.

**Response (PROCESSING):**

```json
{
  "request_id": "post_123456",
  "status": "PROCESSING",
  "message": "Transcription in progress"
}
```

**Response (COMPLETED):**

```json
{
  "request_id": "post_123456",
  "status": "COMPLETED",
  "message": "Transcription completed successfully",
  "transcription": "Nội dung video...",
  "duration": 45.5,
  "confidence": 0.98,
  "processing_time": 12.3
}
```

**Response (FAILED):**

```json
{
  "request_id": "post_123456",
  "status": "FAILED",
  "message": "Transcription failed",
  "error": "Failed to download audio file"
}
```

**Polling Strategy:**

- Poll every 2-5 seconds
- Jobs expire after 1 hour (configurable via `REDIS_JOB_TTL`)

#### GET `/health`

Service health check (includes Redis status).

**Response:**

```json
{
  "error_code": 0,
  "message": "Service is healthy",
  "data": {
    "status": "healthy",
    "service": "Speech-to-Text API",
    "version": "1.0.0",
    "model": {
      "initialized": true,
      "size": "base",
      "ram_mb": 1000
    },
    "redis": {
      "healthy": true
    }
  }
}
```

#### GET `/`

Root endpoint with service information.

**Response:**

```json
{
  "error_code": 0,
  "message": "API service is running",
  "data": {
    "service": "SMAP Speech-to-Text",
    "version": "1.0.0",
    "status": "running"
  }
}
```

---

## Configuration

### Environment Variables

```bash
# Application
APP_NAME="Speech-to-Text API"
APP_VERSION="1.0.0"
ENVIRONMENT="development"
DEBUG=true

# API Service
API_HOST="0.0.0.0"
API_PORT=8000
API_RELOAD=true
API_WORKERS=1
MAX_UPLOAD_SIZE_MB=500

# Storage
TEMP_DIR="/tmp/stt_processing"

# Whisper Library (Dynamic Model Loading)
WHISPER_MODEL_SIZE="base"        # Options: base (default), small, medium
WHISPER_ARTIFACTS_DIR="."
WHISPER_LANGUAGE="vi"
WHISPER_MODEL="base"

# Chunking Configuration (NEW - Production Ready)
WHISPER_CHUNK_ENABLED=true       # Enable/disable chunking
WHISPER_CHUNK_DURATION=30        # Chunk size in seconds
WHISPER_CHUNK_OVERLAP=1          # Overlap in seconds
WHISPER_N_THREADS=0              # 0 for auto-detect (recommended)

# API Security
INTERNAL_API_KEY="your-api-key-here"
TRANSCRIBE_TIMEOUT_SECONDS=90    # Base timeout (adaptive for long audio)

# MinIO (for artifact download) - Change to your MinIO server
MINIO_ENDPOINT="http://localhost:9000"
MINIO_ACCESS_KEY="minioadmin"
MINIO_SECRET_KEY="minioadmin"

# Logging
LOG_LEVEL="INFO"                 # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT="console"             # console (colored) or json (for log aggregation)
LOG_FILE_ENABLED=true            # Enable file logging
LOG_FILE="logs/stt.log"
SCRIPT_LOG_LEVEL="INFO"          # Log level for standalone scripts

# Redis (for async job state management)
REDIS_HOST="localhost"           # Redis host (localhost for dev, redis for docker)
REDIS_PORT=6379                  # Redis port
REDIS_PASSWORD=""                # Redis password (empty if no auth)
REDIS_DB=0                       # Redis database number (0-15)
REDIS_JOB_TTL=3600               # Job state TTL in seconds (1 hour)
```

### Chunking Configuration

The system automatically handles long audio files using sequential chunking:

#### How It Works

1. **Audio Duration Detection** - Uses `ffprobe` to detect audio length
2. **Chunking Decision**:
   - Audio ≤ 30s → Direct transcription (fast path)
   - Audio > 30s → Sequential chunking (long audio path)
3. **Sequential Processing** - Process chunks one at a time (prevents CPU thrashing)
4. **Smart Merge** - Concatenate results with space separator
5. **Adaptive Timeout** - Automatically calculate timeout: `max(90s, audio_duration * 1.5)`

#### Configuration Options

| Variable                     | Default | Description                                 |
| ---------------------------- | ------- | ------------------------------------------- |
| `WHISPER_CHUNK_ENABLED`      | `true`  | Enable/disable chunking feature             |
| `WHISPER_CHUNK_DURATION`     | `30`    | Chunk size in seconds                       |
| `WHISPER_CHUNK_OVERLAP`      | `1`     | Overlap between chunks (prevents word cuts) |
| `WHISPER_N_THREADS`          | `0`     | CPU threads (0=auto-detect, max 8)          |
| `TRANSCRIBE_TIMEOUT_SECONDS` | `90`    | Base timeout (adaptive for long audio)      |

#### Performance Expectations

| Audio Duration | Processing Time   | Memory Usage | Status      |
| -------------- | ----------------- | ------------ | ----------- |
| < 30s          | 0.2-0.5x realtime | ~500MB       | Direct path |
| 3-5 minutes    | 0.28x realtime    | ~500MB       | Chunked     |
| 9-12 minutes   | 0.20x realtime    | ~500MB       | Chunked     |
| 15-20 minutes  | 0.24x realtime    | ~500MB       | Chunked     |

See `CHUNKING_TEST_REPORT.md` for comprehensive test results.

### Supported Audio Formats

MP3, WAV, M4A, MP4, AAC, OGG, FLAC, WMA, WEBM, MKV, AVI, MOV

---

## Project Structure

```
speech2text/
├── adapters/
│   └── whisper/              # Whisper.cpp integration
│       ├── engine.py         # Legacy CLI transcriber
│       ├── library_adapter.py # NEW Direct C library integration
│       └── model_downloader.py
├── cmd/
│   └── api/                  # API service entry point
│       ├── Dockerfile        # Production Docker image
│       └── main.py           # FastAPI application
├── core/                     # Core configuration and utilities
│   ├── config.py             # Settings management
│   ├── constants.py          # Centralized constants (Audio, HTTP, Whisper)
│   ├── errors.py             # Centralized exceptions (STT, Whisper, Audio)
│   ├── messages.py           # Error/log message templates
│   ├── logger.py             # Logging setup
│   ├── dependencies.py       # Dependency validation
│   └── container.py          # DI container
├── internal/
│   └── api/                  # API layer
│       ├── routes/           # API endpoints
│       │   ├── transcribe_routes.py
│       │   └── health_routes.py
│       ├── schemas/          # Request/response models
│       │   └── common_schemas.py
│       └── utils.py          # API utilities
├── scripts/                  # NEW Utility scripts
│   ├── entrypoint.sh         # NEW Smart entrypoint for Docker
│   ├── dev-startup.sh        # Dev container startup
│   └── download_whisper_artifacts.py # Download from MinIO
├── services/
│   └── transcription.py      # Transcription service
├── tests/                    # Test suite
│   ├── test_whisper_library.py  # Library adapter tests
│   └── test_model_switching.py  # Integration tests
├── whisper/                  # Whisper models and binaries
├── docker-compose.yml
├── docker-compose.dev.yml    # NEW Development compose
├── pyproject.toml
└── README.md
```

---

## Development Guide

### Running Tests

```bash
# Run all tests
make test

# Run library adapter tests
make test-library

# Run model switching tests
make test-integration

# Run with specific model
make test-small
make test-medium

# Run with coverage
uv run pytest --cov=. --cov-report=html
```

### Code Quality

```bash
# Format code
make format

# Lint code
make lint

# Clean up
make clean
make clean-old  # Remove old/unused files
```

### Docker Development

```bash
# Build image
make docker-build

# Start service with small model
make docker-up

# Start with medium model (no rebuild!)
WHISPER_MODEL_SIZE=medium docker-compose up -d

# View logs
make docker-logs

# Restart service
docker-compose restart api

# Stop service
make docker-down
```

---

## Troubleshooting

### Common Issues

#### 1. Whisper executable not found

```bash
# Check whisper path
ls -la whisper/bin/whisper-cli

# Update .env
WHISPER_EXECUTABLE="./whisper/bin/whisper-cli"
```

#### 2. FFmpeg not installed

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt-get install ffmpeg

# Verify installation
ffmpeg -version
ffprobe -version  # Required for chunking
```

#### 3. Port already in use

```bash
# Change port in .env
API_PORT=8001

# Or kill process using port 8000
lsof -ti:8000 | xargs kill -9
```

#### 4. Audio download fails

- Verify URL is accessible
- Check firewall/proxy settings
- Ensure audio format is supported
- Verify file size is within limits

#### 5. Model artifacts not found (Dynamic Loading)

```bash
# Download artifacts manually
make setup-artifacts-small
make setup-artifacts-medium

# Or let entrypoint download automatically
docker-compose up
```

#### 6. Library loading error

```bash
# Check LD_LIBRARY_PATH is set correctly
export LD_LIBRARY_PATH=/app/whisper_small_xeon:$LD_LIBRARY_PATH

# Verify artifacts exist
ls -la whisper_small_xeon/

# Re-download if corrupted
rm -rf whisper_small_xeon
make setup-artifacts-small
```

#### 7. Transcription timeout (Long Audio)

```bash
# Verify chunking is enabled
docker exec stt-api-dev printenv | grep WHISPER_CHUNK_ENABLED
# Should output: WHISPER_CHUNK_ENABLED=true

# Check timeout setting
docker exec stt-api-dev printenv | grep TRANSCRIBE_TIMEOUT
# Should output: TRANSCRIBE_TIMEOUT_SECONDS=90

# Increase timeout if needed (for very long audio)
# Edit docker-compose.dev.yml:
TRANSCRIBE_TIMEOUT_SECONDS: "180"  # 3 minutes

# Restart container
docker-compose restart api-dev
```

#### 8. High memory usage

```bash
# Check if chunking is enabled
docker exec stt-api-dev printenv | grep WHISPER_CHUNK

# Memory should stay ~500MB regardless of audio length
docker stats stt-api-dev

# If memory is high:
# 1. Verify WHISPER_CHUNK_ENABLED=true
# 2. Check for stuck processes
# 3. Review logs for errors
docker-compose logs -f api-dev
```

#### 9. Slow transcription performance

```bash
# Check thread configuration
docker exec stt-api-dev printenv | grep WHISPER_N_THREADS
# Should output: WHISPER_N_THREADS=0 (auto-detect)

# Check CPU allocation
docker stats smap-api-dev

# If using less than 4 cores, performance will be slower
# In production, ensure container has access to 4+ CPU cores
```

#### 10. Chunking not working

```bash
# Verify FFmpeg is installed
docker exec stt-api-dev ffmpeg -version
docker exec stt-api-dev ffprobe -version

# Check logs for chunking messages
docker-compose logs -f api-dev | grep -i chunk

# Expected logs:
# "Audio duration detected: X.X seconds"
# "Using chunked transcription (Y chunks)"
# "Processing chunk 1/Y"
```

### Logs

```bash
# View application logs
tail -f logs/stt.log

# Docker logs
docker-compose logs -f api
```

#### 11. Model initialization fails at startup

```bash
# Check logs for model initialization errors
docker-compose logs api | grep -i "model\|whisper\|init"

# Common causes:
# 1. Model files missing - download artifacts
make setup-artifacts-base

# 2. Model files corrupted - re-download
rm -rf models/whisper_base_xeon
make setup-artifacts-base

# 3. Wrong WHISPER_ARTIFACTS_DIR - check path
docker exec stt-api printenv | grep WHISPER_ARTIFACTS_DIR
# Should output: WHISPER_ARTIFACTS_DIR=models

# 4. Library loading error - check LD_LIBRARY_PATH
docker exec stt-api printenv | grep LD_LIBRARY_PATH
```

#### 12. Health check shows unhealthy

```bash
# Check health endpoint
curl http://localhost:8000/health | jq

# If model.initialized is false, check:
# 1. Model initialization logs
docker-compose logs api | grep -i "model\|init\|error"

# 2. Model files exist
docker exec stt-api ls -la models/whisper_base_xeon/

# 3. Restart service
docker-compose restart api
```

---

## Logging Configuration

### Log Levels

| Level      | Description                    | Use Case                     |
| ---------- | ------------------------------ | ---------------------------- |
| `DEBUG`    | Detailed diagnostic info       | Development, troubleshooting |
| `INFO`     | General operational messages   | Production (default)         |
| `WARNING`  | Potentially harmful situations | Production                   |
| `ERROR`    | Error events                   | Production                   |
| `CRITICAL` | Severe errors                  | Production                   |

### Log Formats

- **console** (default): Colored, human-readable output for development
- **json**: Structured JSON output for log aggregation (ELK, Datadog, etc.)

### Configuration Examples

```bash
# Development (verbose)
LOG_LEVEL=DEBUG
LOG_FORMAT=console
LOG_FILE_ENABLED=true

# Production (structured)
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE_ENABLED=false  # Use container log collector

# Script debugging
SCRIPT_LOG_LEVEL=DEBUG
```

### Log Files

- `logs/app.log` - All application logs (DEBUG level)
- `logs/error.log` - Error logs only (ERROR level)
- `logs/app.json.log` - JSON format logs (when LOG_FORMAT=json)

---

## Testing

### Overview

The test suite includes 114 tests covering:

- **Unit Tests**: Configuration, utilities, business logic
- **Integration Tests**: API endpoints, service layer
- **Performance Tests**: CPU scaling, benchmarking

### Quick Start

```bash
# Run all tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=. --cov-report=html

# Run using test runner script (with HTML reports)
uv run python scripts/run_all_tests.py
```

### Test Reports

| Report       | Location                                | Description              |
| ------------ | --------------------------------------- | ------------------------ |
| HTML Report  | `scripts/test_reports/test_report.html` | Interactive test results |
| Coverage     | `htmlcov/index.html`                    | Code coverage report     |
| JSON Results | `scripts/test_reports/results.json`     | Machine-readable results |

See [TESTING.md](docs/TESTING.md) for comprehensive testing documentation.

---

## Performance Testing

### Overview

The system includes comprehensive performance testing tools to analyze CPU scaling, benchmark audio processing, and guide scaling decisions.

### Quick Start

```bash
# Run CPU scaling profiler (in Docker)
docker run --rm -v $(pwd):/app -w /app \
  -e WHISPER_ARTIFACTS_DIR=models \
  python:3.12-slim-bookworm \
  python scripts/profile_cpu_scaling.py

# Benchmark all audio files
./scripts/benchmark_all_audio.sh
```

### Reports

| Report        | Location                                          | Description                      |
| ------------- | ------------------------------------------------- | -------------------------------- |
| CPU Scaling   | `scripts/benchmark_results/cpu_scaling_report.md` | CPU scaling analysis             |
| Performance   | `docs/PERFORMANCE_REPORT.md`                      | Comprehensive performance report |
| Scaling Guide | `docs/SCALING_STRATEGY.md`                        | When to scale up vs out          |

### Key Findings

- **CPU Scaling**: Poor multi-core scaling - use "ít cores mạnh" (fewer but stronger cores)
- **Optimal Config**: 1-2 cores per pod with high clock speed
- **Scaling Strategy**: Scale horizontally (more pods) for throughput

See [PERFORMANCE_REPORT.md](docs/PERFORMANCE_REPORT.md) and [SCALING_STRATEGY.md](docs/SCALING_STRATEGY.md) for details.

---

## Contact

- **Email**: nguyentantai.dev@gmail.com
