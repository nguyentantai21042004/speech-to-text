# Testing Guide

Comprehensive testing documentation for the Speech-to-Text system.

---

## Overview

The test suite covers:

- **Unit Tests**: Core business logic, configuration, utilities
- **Integration Tests**: API endpoints, service layer
- **Performance Tests**: CPU scaling, benchmarking

**Current Status**: 114 tests, 100% passing

---

## Quick Start

```bash
# Run all tests
uv run pytest tests/

# Run with verbose output
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=. --cov-report=html

# Run specific test file
uv run pytest tests/test_chunking.py -v

# Run using test runner script (with reports)
uv run python scripts/run_all_tests.py
```

---

## Test Structure

```
tests/
├── test_api_transcribe.py       # API endpoint tests (v1)
├── test_api_transcribe_v2.py    # API endpoint tests (v2)
├── test_chunking.py             # Chunking configuration & logic
├── test_inaudible_fix.py        # Audio validation & merge quality
├── test_logging_config.py       # Logging configuration
├── test_transcription_service.py # Service layer tests
└── test_whisper_library.py      # Whisper adapter tests
```

---

## Test Categories

### 1. Configuration Tests (`test_chunking.py`)

Tests for chunking configuration and validation logic.

```python
# Test chunking settings
def test_chunking_settings_exist()
def test_chunking_default_values()
def test_chunk_overlap_validation_valid()
def test_chunk_overlap_validation_invalid()

# Test chunk calculations (pure logic)
def test_calculate_chunk_count()
def test_calculate_chunk_boundaries()
def test_short_audio_single_chunk()

# Test text merging
def test_merge_basic_chunks()
def test_merge_with_empty_strings()
def test_merge_empty_list()
```

**Key Points**:

- Tests configuration validation without mocking
- Tests pure calculation logic
- No external dependencies required

### 2. Service Layer Tests (`test_transcription_service.py`)

Tests for `TranscribeService` using dependency injection.

```python
# Success scenarios
def test_transcribe_from_url_success()
def test_transcribe_from_url_with_language_override()
def test_adaptive_timeout_calculation()

# Error handling
def test_transcribe_from_url_download_failure()
def test_transcribe_from_url_timeout()

# Resource management
def test_temp_file_cleanup()

# Dependency injection
def test_service_accepts_custom_transcriber()
def test_service_accepts_custom_downloader()
```

**Key Points**:

- Uses mock implementations of `ITranscriber` and `IAudioDownloader`
- Tests business logic without real Whisper library
- Validates timeout handling and cleanup

### 3. API Tests (`test_api_transcribe.py`, `test_api_transcribe_v2.py`)

Tests for FastAPI endpoints.

```python
# Authentication
def test_valid_api_key_success()
def test_missing_api_key()
def test_invalid_api_key()

# Request validation
def test_missing_media_url()
def test_invalid_media_url_format()
def test_optional_language_parameter()

# Response format
def test_success_response_structure()

# Error handling
def test_timeout_error()
def test_file_too_large_error()
def test_invalid_url_error()
def test_internal_server_error()
```

**Key Points**:

- Uses FastAPI TestClient
- Mocks service layer for isolation
- Tests HTTP status codes and response formats

### 4. Whisper Adapter Tests (`test_whisper_library.py`)

Tests for `WhisperLibraryAdapter` configuration and validation.

```python
# Model configuration
def test_model_configs_exist()
def test_small_model_config()
def test_medium_model_config()
def test_all_configs_have_required_fields()

# Validation
def test_invalid_model_size_raises_error()
def test_missing_library_directory_raises_error()

# Initialization
def test_successful_initialization()
def test_null_context_raises_error()
def test_uses_settings_model_size_when_not_specified()

# Singleton pattern
def test_singleton_creates_instance_once()

# Exception classes
def test_whisper_library_error_is_exception()
def test_library_load_error_is_whisper_error()
def test_model_init_error_is_whisper_error()
```

**Key Points**:

- Tests configuration constants
- Mocks ctypes.CDLL for library loading
- Tests error handling and validation

### 5. Logging Tests (`test_logging_config.py`)

Tests for centralized logging configuration.

```python
# InterceptHandler
def test_intercept_handler_is_logging_handler()
def test_intercept_handler_emit_does_not_raise()

# Third-party loggers
def test_configures_httpx_logger()
def test_configures_urllib3_logger()
def test_configures_boto3_logger()
def test_configures_uvicorn_logger()

# Script logging
def test_configure_script_logging_default_level()
def test_configure_script_logging_debug_level()
def test_configure_script_logging_json_format()

# Setup functions
def test_setup_logger_creates_handlers()
def test_setup_logger_idempotent()
def test_setup_json_logging_default_level()

# Exception formatting
def test_format_exception_with_context()
def test_format_exception_without_context()
def test_format_exception_includes_location()

# Module exports
def test_all_exports_available()
def test_logger_object_available()
def test_logger_can_log_messages()
```

### 6. Audio Validation Tests (`test_inaudible_fix.py`)

Tests for audio validation and smart merge functionality.

```python
# Smart merge quality
def test_merge_removes_duplicates()
def test_merge_preserves_content()
def test_merge_handles_inaudible_markers()

# Audio validation
def test_validate_empty_audio()
def test_validate_silent_audio()
def test_validate_constant_noise()
def test_validate_valid_audio()

# Overlap validation
def test_various_overlap_values()

# Thread safety
def test_concurrent_access_simulation()
```

---

## Test Runner Script

The `scripts/run_all_tests.py` provides enhanced test execution with reporting.

### Features

- HTML and JSON test reports
- Coverage analysis
- Slow test detection
- Summary statistics

### Usage

```bash
# Run with all features
uv run python scripts/run_all_tests.py

# Run without coverage (faster)
uv run python scripts/run_all_tests.py --no-coverage

# Run specific test pattern
uv run python scripts/run_all_tests.py -k "test_chunking"
```

### Output

```
============================================================
TEST EXECUTION SUMMARY
============================================================
Status: PASSED
Timestamp: 2025-12-03T12:28:55.256786
Total Time: 4.27s
------------------------------------------------------------
Total Tests: 114
  Passed: 114
  Failed: 0
  Skipped: 0
  Errors: 0
------------------------------------------------------------
Coverage: 85.2%
------------------------------------------------------------
No slow tests detected
============================================================
```

### Reports Location

| Report        | Path                                    |
| ------------- | --------------------------------------- |
| HTML Report   | `scripts/test_reports/test_report.html` |
| JSON Results  | `scripts/test_reports/results.json`     |
| Summary       | `scripts/test_reports/summary.json`     |
| Coverage HTML | `htmlcov/index.html`                    |

---

## Writing Tests

### Guidelines

1. **Use Dependency Injection**: Mock interfaces, not implementations
2. **Test Business Logic**: Focus on behavior, not implementation details
3. **Avoid Over-Mocking**: Only mock external dependencies
4. **Use Fixtures**: Share setup code with pytest fixtures
5. **Descriptive Names**: Test names should describe the scenario

### Example: Service Test with DI

```python
class MockTranscriber(ITranscriber):
    """Mock transcriber for testing"""

    def __init__(self, transcription_text: str = "Test"):
        self.transcription_text = transcription_text

    def transcribe(self, audio_path: str, language: str = "vi") -> str:
        return self.transcription_text

    def get_audio_duration(self, audio_path: str) -> float:
        return 30.0


@pytest.mark.asyncio
async def test_transcribe_success(tmp_path):
    mock_transcriber = MockTranscriber(transcription_text="Hello world")
    mock_downloader = MockAudioDownloader(file_size_mb=2.5)

    service = TranscribeService(
        transcriber=mock_transcriber,
        audio_downloader=mock_downloader
    )

    result = await service.transcribe_from_url("https://example.com/audio.mp3")

    assert result["text"] == "Hello world"
    assert result["file_size_mb"] == 2.5
```

### Example: Configuration Test

```python
def test_chunk_overlap_validation_invalid():
    """Test that invalid overlap raises ValueError"""
    settings = get_settings()

    # Save and restore original values
    original_overlap = settings.whisper_chunk_overlap
    try:
        settings.whisper_chunk_overlap = 20  # Invalid: >= duration/2

        with pytest.raises(ValueError, match="must be less than half"):
            settings.validate_chunk_overlap()
    finally:
        settings.whisper_chunk_overlap = original_overlap
```

---

## Running in Docker

For tests that require Whisper libraries (Linux x86_64):

```bash
# Run tests in Docker container
docker run --rm -v $(pwd):/app -w /app \
  -e WHISPER_ARTIFACTS_DIR=models \
  python:3.12-slim-bookworm \
  bash -c "pip install -e . && pytest tests/ -v"

# Or use docker-compose
docker-compose -f docker-compose.dev.yml run --rm api-dev \
  pytest tests/ -v
```

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          pip install uv
          uv sync

      - name: Run tests
        run: uv run pytest tests/ -v --cov=. --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
```

---

## Troubleshooting

### Common Issues

#### 1. Import errors

```bash
# Ensure package is installed
uv sync
# Or
pip install -e .
```

#### 2. Async test failures

```bash
# Install pytest-asyncio
uv add pytest-asyncio

# Mark async tests
@pytest.mark.asyncio
async def test_async_function():
    ...
```

#### 3. Mock not working

```python
# Wrong: Mocking the class
with patch("module.ClassName"):
    ...

# Right: Mocking where it's used
with patch("services.transcription.TranscribeService.transcribe_from_url"):
    ...
```

#### 4. Settings cache issues

```python
# Clear settings cache between tests
from core.config import get_settings
get_settings.cache_clear()
```

---

## Performance Testing

See [PERFORMANCE_REPORT.md](PERFORMANCE_REPORT.md) and [SCALING_STRATEGY.md](SCALING_STRATEGY.md) for:

- CPU scaling analysis
- Benchmark results
- Scaling recommendations
