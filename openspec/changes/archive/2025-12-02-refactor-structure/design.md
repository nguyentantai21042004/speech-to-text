# Design: Refactor Project Structure

## Context

Project hiện tại đã có `document/architecture.md` định nghĩa chuẩn architecture nhưng implementation chưa hoàn toàn tuân theo. Cần refactor để:
- Tăng maintainability
- Hỗ trợ testing tốt hơn qua dependency injection
- Tuân theo Clean Architecture principles

## Goals / Non-Goals

### Goals
- Tạo interface layer cho dependency injection
- Di chuyển adapters vào infrastructure layer
- Consolidate data models vào models layer
- Giữ backward compatibility (không breaking changes)

### Non-Goals
- Thay đổi business logic
- Thay đổi API contracts
- Thêm features mới

## Decisions

### Decision 1: Interface Design

**ITranscriber Interface:**
```python
from abc import ABC, abstractmethod
from typing import Optional

class ITranscriber(ABC):
    @abstractmethod
    def transcribe(self, audio_path: str, language: str = "vi") -> str:
        """Transcribe audio file to text."""
        pass
```

**IAudioDownloader Interface:**
```python
from abc import ABC, abstractmethod
from pathlib import Path

class IAudioDownloader(ABC):
    @abstractmethod
    async def download(self, url: str, destination: Path) -> float:
        """Download audio from URL. Returns file size in MB."""
        pass
```

**Rationale:** Minimal interfaces focusing on single responsibility. Allows easy mocking for tests.

### Decision 2: Infrastructure Organization

```
infrastructure/
└── whisper/
    ├── __init__.py
    ├── library_adapter.py  # WhisperLibraryAdapter implements ITranscriber
    ├── engine.py           # Legacy CLI wrapper (fallback)
    └── model_downloader.py # Model download utilities
```

**Rationale:** Group by external dependency (Whisper), not by function. Easier to add new infrastructure (e.g., `infrastructure/ffmpeg/`).

### Decision 3: Dependency Injection Strategy

Use `core/container.py` for singleton registrations:

```python
# core/container.py
def bootstrap_container():
    from interfaces.transcriber import ITranscriber
    from infrastructure.whisper.library_adapter import WhisperLibraryAdapter
    
    Container.register(ITranscriber, WhisperLibraryAdapter())
```

**Rationale:** Simple DI without external framework. Sufficient for current project size.

### Decision 4: Import Path Updates

All imports will use absolute paths from project root:
- `from interfaces.transcriber import ITranscriber`
- `from infrastructure.whisper.library_adapter import WhisperLibraryAdapter`
- `from models.schemas import TranscribeRequest`

**Rationale:** Consistent, explicit imports. Avoids relative import confusion.

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Breaking existing tests | Update imports incrementally, run tests after each step |
| Import errors at runtime | Validate all imports before removing old directories |
| Circular imports | Interfaces have no dependencies, break cycles |

## Migration Plan

1. **Phase 1: Add new structure** (non-breaking)
   - Create `interfaces/`, `models/`, `infrastructure/`
   - Copy files to new locations
   - Implement interfaces

2. **Phase 2: Update consumers**
   - Update services to use interfaces
   - Update routes to use DI
   - Update tests

3. **Phase 3: Cleanup**
   - Remove old `adapters/` directory
   - Final test validation

**Rollback:** Git revert if issues found. No database migrations involved.

## Open Questions

- None currently. Architecture pattern is well-defined in `document/architecture.md`.
