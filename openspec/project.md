# Project Context

## Purpose
Provide a production-ready, stateless speech-to-text (STT) API that transcribes audio from URLs using Whisper.cpp, delivering high-quality transcripts through a FastAPI interface with minimal infrastructure dependencies.

## Tech Stack
- **Python 3.12+** with uv for dependency management
- **FastAPI 0.104+** + **Pydantic 2.5+** for HTTP services and data validation
- **Whisper.cpp** (shared library integration via ctypes) for transcription engine
- **httpx** for async HTTP client (audio download)
- **librosa + soundfile** for audio loading and preprocessing
- **FFmpeg/FFprobe** for audio format conversion and duration detection
- **Docker** for containerized deployment
- **Loguru** for structured logging

## Project Conventions

### Code Style
- Follow PEP8 with type hints on public functions
- Prefer descriptive module/class names that mirror their Clean Architecture role (e.g., `TranscribeService`, `WhisperLibraryAdapter`)
- Use Conventional Commit prefixes (`feat`, `fix`, `docs`, `refactor`, etc.)
- Keep logging structured with contextual identifiers to aid observability

### Architecture Patterns
- **Stateless Design**: Each request is independent, no session state or background jobs
- **Clean Architecture**: Presentation (FastAPI routers) → Application (services) → Infrastructure (adapters)
- **Singleton Pattern**: Whisper transcriber initialized once at startup for performance (`get_whisper_library_adapter()`)
- **Direct Library Integration**: Whisper.cpp loaded as shared library (.so) via ctypes instead of CLI subprocess
- **Interface-Based**: Services implement interfaces for testability and flexibility
- **Dependency Injection**: Simple DI container in `core/container.py`

### Testing Strategy
- **Pytest** for unit/integration tests
- **Coverage Focus**: Services, adapters, and error handling paths
- **Test Commands**:
  - `make test` - Run full test suite
  - `uv run pytest` - Direct pytest execution
  - `make -f Makefile.dev dev-test` - Run tests in dev container

### Git Workflow
- Develop on short-lived feature branches: `feat/<scope>` or `fix/<scope>`
- Require OpenSpec proposal approval before architectural changes
- Use Conventional Commits
- Keep PRs focused on single change-set aligned with OpenSpec change ID

## Domain Context

### Primary Workflow
1. **Client Request**: POST to `/transcribe` with `media_url` and optional `language`
2. **Authentication**: Verify `X-API-Key` header against `INTERNAL_API_KEY`
3. **Audio Download**: Service downloads audio from URL (streaming with size validation)
4. **Duration Detection**: Use FFprobe to detect audio length for adaptive timeout
5. **Transcription**: 
   - Short audio (≤30s): Direct transcription via Whisper.cpp library
   - Long audio (>30s): Sequential chunking with FFmpeg, process each chunk, merge results
6. **Response**: Return transcribed text with metadata (duration, confidence, processing_time)

### Key Features
- **Direct Transcription**: Synchronous request-response (no queues)
- **Dynamic Model Loading**: Switch between base/small/medium models via `WHISPER_MODEL_SIZE` ENV variable
- **Auto-Download**: Whisper artifacts downloaded from MinIO on first run
- **Anti-Hallucination**: Configurable thresholds (entropy, logprob, no-speech)
- **Sequential Smart-Chunking**: Handle audio up to 30+ minutes with flat memory usage (~500MB)
- **Adaptive Timeout**: Automatic timeout calculation: `max(base_timeout, audio_duration * 1.5)`

## Important Constraints

### Performance
- **Model Loading**: Models loaded once at startup (~60MB for base, ~181MB for small, ~1.5GB for medium)
- **RAM Usage**: ~1GB for base, ~500MB for small, ~2GB for medium
- **Concurrent Requests**: Singleton transcriber handles requests sequentially
- **File Size Limits**: Configurable max upload size (default: 500MB)
- **Temporary Storage**: Files cleaned up after transcription
- **Processing Speed**: 4-5x faster than realtime for chunked audio

### Platform Requirements
- **Linux Only**: Shared libraries (.so) compiled for Linux x86_64/Xeon
- **macOS Development**: Use Docker dev container (`docker-compose.dev.yml`)
- **CPU Requirements**: AVX2 and FMA support for optimal performance
- **Dependencies**: libgomp1 (OpenMP runtime), FFmpeg, FFprobe

### API Standards
- **Response Format**: Standardized `{status, transcription, duration, confidence, processing_time}` structure
- **Error Handling**: Proper HTTP status codes (400, 401, 413, 500) with detailed error messages
- **Health Checks**: `/health` endpoint for monitoring
- **Authentication**: `X-API-Key` header required for `/transcribe` endpoint

## External Dependencies

### Runtime Dependencies
- **Whisper.cpp Libraries**: `libwhisper.so`, `libggml.so.0`, `libggml-base.so.0`, `libggml-cpu.so.0`
- **Whisper Models**: `ggml-base-q5_1.bin`, `ggml-small-q5_1.bin`, or `ggml-medium-q5_1.bin`
- **FFmpeg/FFprobe**: Audio format conversion and duration detection
- **libgomp1**: OpenMP runtime for parallel processing

### Development Dependencies
- **MinIO**: Artifact storage (for downloading Whisper models)
- **boto3**: MinIO client for artifact downloads
- **Docker**: Development container for macOS compatibility

## Project Structure

```
speech2text/
├── adapters/                   # Infrastructure adapters
│   └── whisper/                # Whisper.cpp integration
│       ├── engine.py           # Legacy CLI wrapper (fallback)
│       ├── library_adapter.py  # Direct C library integration (primary)
│       └── model_downloader.py # MinIO artifact downloader
├── cmd/                        # Application entry points
│   └── api/                    # API service
│       ├── Dockerfile          # Production Docker image
│       ├── main.py             # FastAPI application bootstrap
│       └── swagger_static/     # Swagger UI static files
├── core/                       # Core configuration and utilities
│   ├── config.py               # Settings management (Pydantic Settings)
│   ├── constants.py            # Application constants
│   ├── container.py            # Dependency injection container
│   ├── dependencies.py         # System dependency validation
│   ├── errors.py               # Custom exceptions hierarchy
│   └── logger.py               # Loguru logging setup
├── internal/                   # Internal API implementation
│   └── api/
│       ├── dependencies/       # FastAPI dependencies (auth, etc.)
│       ├── routes/             # API endpoints
│       │   ├── transcribe_routes.py  # POST /transcribe
│       │   └── health_routes.py      # GET /health
│       ├── schemas/            # Request/response models
│       │   └── common_schemas.py
│       └── utils.py            # API utilities (response helpers)
├── services/                   # Business logic layer
│   └── transcription.py        # TranscribeService (download + transcribe)
├── scripts/                    # Utility scripts
│   ├── dev-startup.sh          # Dev container startup
│   ├── download_whisper_artifacts.py  # MinIO downloader
│   └── entrypoint.sh           # Production entrypoint
├── tests/                      # Test suite
│   ├── test_api_transcribe.py
│   ├── test_api_transcribe_v2.py
│   ├── test_chunking.py
│   ├── test_model_switching.py
│   ├── test_transcription_service.py
│   └── test_whisper_library.py
├── k8s/                        # Kubernetes manifests
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── namespace.yaml
│   ├── pvc.yaml
│   └── secret.yaml
├── openspec/                   # OpenSpec specifications
│   ├── changes/                # Change proposals
│   ├── specs/                  # Feature specifications
│   └── project.md              # This file
├── document/                   # Documentation
│   └── architecture.md         # Architecture reference
├── docker-compose.yml          # Production compose
├── docker-compose.dev.yml      # Development compose
├── Makefile                    # Production commands
├── Makefile.dev                # Development commands
├── pyproject.toml              # Project dependencies (uv)
└── .env.example                # Environment template
```

## Key Components

### TranscribeService (`services/transcription.py`)
- Orchestrates audio download and transcription
- Handles adaptive timeout calculation
- Manages temporary file cleanup
- Delegates to WhisperLibraryAdapter for actual transcription

### WhisperLibraryAdapter (`adapters/whisper/library_adapter.py`)
- Direct C library integration via ctypes
- Loads shared libraries in correct dependency order
- Singleton pattern for model reuse
- Supports chunked transcription for long audio
- Auto-detects CPU threads (capped at 8)

### Model Configurations
| Model | Directory | File | Size | RAM |
|-------|-----------|------|------|-----|
| base | `whisper_base_xeon/` | `ggml-base-q5_1.bin` | 60MB | ~1GB |
| small | `whisper_small_xeon/` | `ggml-small-q5_1.bin` | 181MB | ~500MB |
| medium | `whisper_medium_xeon/` | `ggml-medium-q5_1.bin` | 1.5GB | ~2GB |

### Error Hierarchy (`core/errors.py`)
- **STTError**: Base exception
- **TransientError**: Retryable (OutOfMemoryError, TimeoutError, WhisperCrashError, NetworkError)
- **PermanentError**: Non-retryable (InvalidAudioFormatError, FileTooLargeError, TranscriptionError)

## Development Workflow

### Local Development (macOS)
```bash
# Use dev container (required for .so libraries)
make -f Makefile.dev dev-up
make -f Makefile.dev dev-logs
```

### Production Build
```bash
# Build Docker image
docker build -t stt-api:latest -f cmd/api/Dockerfile .

# Run with model selection
docker run -e WHISPER_MODEL_SIZE=small -p 8000:8000 stt-api:latest
```

### Model Switching
```bash
# Switch to medium model (no rebuild required)
WHISPER_MODEL_SIZE=medium docker-compose up
```

### Testing
```bash
make test                    # Full test suite
make test-library            # Library adapter tests
make test-integration        # Model switching tests
uv run pytest --cov=.        # With coverage
```

## Configuration Reference

### Key Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_MODEL_SIZE` | `base` | Model size: base, small, medium |
| `WHISPER_ARTIFACTS_DIR` | `.` | Base directory for model artifacts |
| `WHISPER_LANGUAGE` | `vi` | Default transcription language |
| `WHISPER_N_THREADS` | `0` | CPU threads (0=auto, max 8) |
| `WHISPER_CHUNK_ENABLED` | `true` | Enable chunking for long audio |
| `WHISPER_CHUNK_DURATION` | `30` | Chunk size in seconds |
| `WHISPER_CHUNK_OVERLAP` | `1` | Overlap between chunks |
| `TRANSCRIBE_TIMEOUT_SECONDS` | `30` | Base timeout (adaptive for long audio) |
| `MAX_UPLOAD_SIZE_MB` | `500` | Maximum file size |
| `INTERNAL_API_KEY` | - | API authentication key |

## Migration History

This project was migrated from a stateful architecture (MongoDB + RabbitMQ + MinIO + Consumer service) to a stateless API design. See archived OpenSpec changes:
- `2025-11-27-stateless-migration` - Core stateless refactor
- `2025-11-27-dynamic-model-loading` - Shared library integration
