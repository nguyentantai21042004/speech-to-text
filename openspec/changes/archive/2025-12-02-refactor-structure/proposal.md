# Change: Refactor Project Structure to Match Architecture Standard

## Why

Cấu trúc source hiện tại không hoàn toàn tuân theo architecture pattern đã định nghĩa trong `document/architecture.md`. Một số vấn đề:

1. **Thiếu layer `interfaces/`**: Không có abstract interfaces cho dependency injection
2. **Thiếu layer `models/`**: Database models và Pydantic schemas nằm rải rác
3. **Thiếu layer `repositories/`**: Không có repository pattern cho data access
4. **`adapters/` không theo chuẩn**: Nên nằm trong `infrastructure/` theo Clean Architecture
5. **Khó maintain và test**: Thiếu abstraction layers làm code coupling cao

## What Changes

### Directory Structure Changes

- **ADDED** `interfaces/` - Abstract interfaces cho dependency injection
  - `interfaces/transcriber.py` - ITranscriber interface
  - `interfaces/audio_downloader.py` - IAudioDownloader interface
  
- **ADDED** `models/` - Data models layer
  - `models/schemas.py` - Pydantic schemas (request/response DTOs)
  
- **ADDED** `infrastructure/` - Infrastructure implementations
  - `infrastructure/whisper/` - Move từ `adapters/whisper/`
  
- **MODIFIED** `services/transcription.py` - Sử dụng interfaces thay vì concrete implementations

- **REMOVED** `adapters/` - Di chuyển vào `infrastructure/`

### Code Changes

- Services sẽ depend on interfaces, không phải concrete implementations
- Dependency injection qua `core/container.py`
- Dễ dàng mock và test

## Impact

- **Affected specs**: `clean-architecture`, `whisper-library-integration`, `speech-transcription`
- **Affected code**: 
  - `adapters/whisper/*` → `infrastructure/whisper/*`
  - `services/transcription.py` - refactor to use interfaces
  - `core/container.py` - register dependencies
  - `cmd/api/main.py` - bootstrap container
  - `internal/api/routes/transcribe_routes.py` - use DI
- **Breaking changes**: None (internal refactor only)

## Target Structure

```
speech2text/
├── cmd/                        # Entry Points
│   └── api/
│       ├── main.py            # Bootstrap container, start FastAPI
│       └── Dockerfile
│
├── internal/                   # Internal Implementation
│   └── api/
│       ├── routes/            # API endpoints
│       ├── schemas/           # Request/Response schemas
│       └── dependencies/      # FastAPI dependencies
│
├── core/                       # Core Shared Layer
│   ├── config.py
│   ├── logger.py
│   ├── errors.py
│   ├── constants.py
│   ├── container.py           # DI container
│   └── dependencies.py
│
├── interfaces/                 # Interface Layer (NEW)
│   ├── __init__.py
│   ├── transcriber.py         # ITranscriber interface
│   └── audio_downloader.py    # IAudioDownloader interface
│
├── models/                     # Data Models Layer (NEW)
│   ├── __init__.py
│   └── schemas.py             # Pydantic DTOs
│
├── services/                   # Business Logic Layer
│   └── transcription.py       # TranscribeService (uses interfaces)
│
├── infrastructure/             # Infrastructure Layer (NEW)
│   └── whisper/               # Whisper.cpp integration
│       ├── engine.py
│       ├── library_adapter.py
│       └── model_downloader.py
│
├── scripts/
├── tests/
├── k8s/
├── document/
└── openspec/
```
