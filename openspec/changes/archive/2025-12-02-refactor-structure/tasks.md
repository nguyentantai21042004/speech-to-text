# Implementation Tasks

## 1. Create Interface Layer
- [x] 1.1 Create `interfaces/__init__.py`
- [x] 1.2 Create `interfaces/transcriber.py` with `ITranscriber` abstract class
- [x] 1.3 Create `interfaces/audio_downloader.py` with `IAudioDownloader` abstract class

## 2. Create Models Layer
- [x] 2.1 Create `models/__init__.py`
- [x] 2.2 Create `models/schemas.py` - move/consolidate Pydantic schemas

## 3. Migrate Adapters to Infrastructure
- [x] 3.1 Create `infrastructure/__init__.py`
- [x] 3.2 Create `infrastructure/whisper/__init__.py`
- [x] 3.3 Move `adapters/whisper/engine.py` → `infrastructure/whisper/engine.py`
- [x] 3.4 Move `adapters/whisper/library_adapter.py` → `infrastructure/whisper/library_adapter.py`
- [x] 3.5 Move `adapters/whisper/model_downloader.py` → `infrastructure/whisper/model_downloader.py`
- [x] 3.6 Update `infrastructure/whisper/library_adapter.py` to implement `ITranscriber`

## 4. Update Services Layer
- [x] 4.1 Refactor `services/transcription.py` to use `ITranscriber` interface
- [x] 4.2 Extract audio download logic to implement `IAudioDownloader`

## 5. Update Dependency Injection
- [x] 5.1 Update `core/container.py` with interface registrations
- [x] 5.2 Update `core/dependencies.py` for FastAPI dependency injection

## 6. Update Entry Points
- [x] 6.1 Update `cmd/api/main.py` to bootstrap container
- [x] 6.2 Update `internal/api/routes/transcribe_routes.py` to use DI

## 7. Cleanup
- [x] 7.1 Remove old `adapters/` directory
- [x] 7.2 Update all import statements across codebase

## 8. Testing & Validation
- [x] 8.1 Update existing tests with new import paths
- [x] 8.2 Run full test suite to verify no regressions
- [x] 8.3 Verify API endpoints work correctly
