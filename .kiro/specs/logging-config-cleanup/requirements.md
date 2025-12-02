# Requirements Document

## Introduction

Tài liệu này mô tả các yêu cầu để cải thiện và chuẩn hóa hệ thống logging và configuration cho Speech-to-Text API service. Mục tiêu là đảm bảo:
1. Whisper model được khởi tạo một lần duy nhất (singleton pattern) và tái sử dụng cho mọi request
2. Logging được chuẩn hóa sử dụng `core/logger.py` (Loguru) xuyên suốt toàn bộ source code
3. Configuration và `.env.example` được đồng bộ và đầy đủ

## Glossary

- **STT_System**: Speech-to-Text API service wrapper cho Whisper model
- **WhisperLibraryAdapter**: Component chịu trách nhiệm tích hợp trực tiếp với Whisper.cpp C library
- **DI_Container**: Dependency Injection Container quản lý lifecycle của các service instances
- **Loguru**: Thư viện logging Python được sử dụng trong `core/logger.py`
- **Singleton**: Design pattern đảm bảo chỉ có một instance duy nhất của một class

## Requirements

### Requirement 1: Singleton Model Initialization

**User Story:** As a developer, I want the Whisper model to be initialized only once at service startup, so that memory is used efficiently and subsequent requests are processed faster.

#### Acceptance Criteria

1. WHEN the STT_System starts THEN the DI_Container SHALL initialize exactly one WhisperLibraryAdapter instance
2. WHEN multiple transcription requests arrive concurrently THEN the STT_System SHALL reuse the same WhisperLibraryAdapter instance for all requests
3. WHEN the DI_Container is already initialized THEN the bootstrap_container function SHALL skip re-initialization and log a debug message
4. WHEN resolving ITranscriber interface THEN the DI_Container SHALL return the same singleton instance

### Requirement 2: Unified Logging with Loguru

**User Story:** As a developer, I want all logging throughout the codebase to use the centralized Loguru logger from `core/logger.py`, so that logs are consistent, formatted uniformly, and easy to analyze.

#### Acceptance Criteria

1. THE STT_System SHALL use only the logger from `core/logger.py` for all application logging
2. WHEN third-party libraries emit logs THEN the STT_System SHALL configure those libraries to use minimal or suppressed logging levels
3. WHEN native C libraries (whisper.cpp) emit stdout/stderr THEN the STT_System SHALL capture and route those outputs through Loguru
4. THE STT_System SHALL NOT use Python's standard `logging` module directly in any application code
5. WHEN configuring log format THEN the STT_System SHALL include timestamp, level, module name, function name, line number, and message

### Requirement 3: Log Level Configuration

**User Story:** As an operator, I want to control log verbosity through environment variables, so that I can adjust logging detail for different environments (development vs production).

#### Acceptance Criteria

1. WHEN LOG_LEVEL environment variable is set THEN the STT_System SHALL use that level for console output
2. WHEN LOG_LEVEL is not set THEN the STT_System SHALL default to INFO level
3. THE STT_System SHALL always write DEBUG level logs to file regardless of console log level
4. WHEN an invalid LOG_LEVEL value is provided THEN the STT_System SHALL fall back to INFO level and continue operation

### Requirement 4: Third-Party Library Log Suppression

**User Story:** As a developer, I want third-party library logs to be minimal and non-intrusive, so that application logs remain clean and valuable.

#### Acceptance Criteria

1. WHEN librosa library emits logs THEN the STT_System SHALL suppress or minimize those logs
2. WHEN uvicorn server emits logs THEN the STT_System SHALL configure uvicorn to use appropriate log level matching application settings
3. WHEN httpx or aiohttp libraries emit logs THEN the STT_System SHALL suppress verbose connection logs
4. WHEN pydantic validation occurs THEN the STT_System SHALL suppress verbose validation debug logs

### Requirement 5: Environment Configuration Synchronization

**User Story:** As a developer, I want `.env.example` to be synchronized with `core/config.py`, so that all available configuration options are documented and discoverable.

#### Acceptance Criteria

1. THE `.env.example` file SHALL contain all configuration fields defined in `core/config.py` Settings class
2. THE `.env.example` file SHALL include descriptive comments for each configuration option
3. WHEN a new configuration field is added to Settings class THEN the `.env.example` file SHALL be updated to include that field
4. THE `.env.example` file SHALL group related configuration options with section headers

### Requirement 6: Structured Log Output

**User Story:** As an operator, I want logs to be structured and parseable, so that I can easily search and analyze them in log aggregation systems.

#### Acceptance Criteria

1. THE STT_System SHALL format console logs with color coding for different log levels
2. THE STT_System SHALL format file logs without color codes for machine parsing
3. WHEN logging exceptions THEN the STT_System SHALL include shortened traceback information using format_exception_short utility
4. THE STT_System SHALL rotate log files at 100MB and retain logs for 30 days with compression
