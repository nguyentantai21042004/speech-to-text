## MODIFIED Requirements

### Requirement: Whisper Library Adapter Location

The Whisper library adapter SHALL be located in `infrastructure/whisper/` directory and implement the `ITranscriber` interface.

#### Scenario: Adapter implements interface
- **WHEN** the WhisperLibraryAdapter is instantiated
- **THEN** it SHALL implement the `ITranscriber` interface from `interfaces/transcriber.py`
- **AND** it SHALL be registered in the DI container as the `ITranscriber` implementation

#### Scenario: Singleton pattern maintained
- **WHEN** multiple requests need transcription
- **THEN** the system SHALL use a single WhisperLibraryAdapter instance
- **AND** the instance SHALL be managed by the DI container

### Requirement: Infrastructure Directory Structure

The Whisper integration code SHALL be organized under `infrastructure/whisper/`:
- `library_adapter.py` - Direct C library integration (implements ITranscriber)
- `engine.py` - Legacy CLI wrapper (fallback)
- `model_downloader.py` - Model download utilities

#### Scenario: File organization
- **WHEN** accessing Whisper functionality
- **THEN** imports SHALL use `from infrastructure.whisper.library_adapter import WhisperLibraryAdapter`
- **AND** the old `adapters/whisper/` path SHALL NOT exist
