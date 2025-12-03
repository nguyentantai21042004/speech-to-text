# Implementation Tasks: Centralize Constants and Errors

## Phase 1: Core Refactoring

### 1.1 Centralize Constants
- [x] Update `core/constants.py` with Audio constants
- [x] Update `core/constants.py` with HTTP constants
- [x] Update `core/constants.py` with Whisper Model Configs
- [x] Update `core/constants.py` with Benchmark constants

### 1.2 Centralize Errors
- [x] Update `core/errors.py` with WhisperLibraryError and subclasses
- [x] Update `core/errors.py` with AudioFileNotFoundError and ChunkProcessingError

### 1.3 Centralize Messages
- [x] Create `core/messages.py` with ErrorMessages class

## Phase 2: Infrastructure Updates

### 2.1 Update Whisper Adapter
- [x] Remove local constants/errors from `infrastructure/whisper/library_adapter.py`
- [x] Update imports in `infrastructure/whisper/library_adapter.py` to use `core`

### 2.2 Update Model Downloader
- [x] Remove local constants from `infrastructure/whisper/model_downloader.py`
- [x] Update imports in `infrastructure/whisper/model_downloader.py` to use `core`

### 2.3 Update Audio Downloader
- [x] Remove local constants from `infrastructure/http/audio_downloader.py`
- [x] Update imports in `infrastructure/http/audio_downloader.py` to use `core`

## Phase 3: Verification

### 3.1 Fix Tests
- [x] Update `tests/test_whisper_library.py` imports
- [x] Update any other affected tests
- [x] Run local Python import tests

### 3.2 Manual Check
- [x] Verify no circular imports
- [x] Verify Docker build passes

## Verification Results

### Local Tests (PASSED)
```
=== REFACTORING VERIFICATION ===
1. core.constants: OK
2. core.errors: OK
3. core.messages: OK
4. infrastructure imports: OK
5. values consistency: OK
=== ALL TESTS PASSED ===
```

### Docker Notes
- Container starts successfully
- Restart loop is due to pre-existing issue with `scripts/download_whisper_artifacts.py` running before `uv sync`
- This is NOT related to the refactoring changes
- Refactoring code imports work correctly when dependencies are installed
