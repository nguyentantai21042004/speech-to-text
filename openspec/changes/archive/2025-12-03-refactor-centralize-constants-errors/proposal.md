# Refactor: Centralize Constants and Error Definitions

## Why

After reviewing the codebase, several issues were identified regarding code organization:

1.  **Scattered Constants**: Constants are defined in multiple places (`library_adapter.py`, `model_downloader.py`, `audio_downloader.py`), causing maintenance difficulties and inconsistencies (e.g., duplicate `MODEL_CONFIGS`).
2.  **Scattered Error Definitions**: Error classes are defined in individual modules instead of a centralized `core/errors.py`.
3.  **Hardcoded Strings**: Error messages are hardcoded inline, making them hard to maintain.
4.  **Duplicate Code**: `MODEL_CONFIGS` is defined twice.

## What Changes

### 1. Centralize Constants
- **[MODIFY] `core/constants.py`**: Add all constants here (Audio, HTTP, Whisper Configs, Benchmark).

### 2. Centralize Error Definitions
- **[MODIFY] `core/errors.py`**: Add all error classes here (`WhisperLibraryError`, `LibraryLoadError`, etc.).

### 3. Update Imports
- **[MODIFY] `infrastructure/whisper/library_adapter.py`**: Import from core.
- **[MODIFY] `infrastructure/whisper/model_downloader.py`**: Import from core.
- **[MODIFY] `infrastructure/http/audio_downloader.py`**: Import from core.

### 4. Create Error Message Templates (Optional)
- **[CREATE] `core/messages.py`**: Centralized error and log message templates.

## User Review Required

> [!IMPORTANT]
> **Breaking Change**: Modules importing constants/errors from old locations will need to update imports. Tests will also need updates.

## Proposed Changes

### Core

#### [MODIFY] [core/constants.py](file:///Users/tantai/Workspaces/tools/speech-to-text/core/constants.py)
- Add Audio Processing Constants
- Add HTTP Client Constants
- Add Whisper Model Configurations
- Add Benchmark/Profiling Constants

#### [MODIFY] [core/errors.py](file:///Users/tantai/Workspaces/tools/speech-to-text/core/errors.py)
- Add Whisper Library Errors
- Add Audio Processing Errors

#### [NEW] [core/messages.py](file:///Users/tantai/Workspaces/tools/speech-to-text/core/messages.py)
- Add ErrorMessages class

### Infrastructure

#### [MODIFY] [infrastructure/whisper/library_adapter.py](file:///Users/tantai/Workspaces/tools/speech-to-text/infrastructure/whisper/library_adapter.py)
- Remove local definitions
- Update imports

#### [MODIFY] [infrastructure/whisper/model_downloader.py](file:///Users/tantai/Workspaces/tools/speech-to-text/infrastructure/whisper/model_downloader.py)
- Remove local definitions
- Update imports

#### [MODIFY] [infrastructure/http/audio_downloader.py](file:///Users/tantai/Workspaces/tools/speech-to-text/infrastructure/http/audio_downloader.py)
- Remove local definitions
- Update imports

## Verification Plan

### Automated Tests
- Run `pytest tests/` to ensure no regressions.
- Verify imports work correctly.

### Manual Verification
- Build Docker image.
- Run transcription test.
