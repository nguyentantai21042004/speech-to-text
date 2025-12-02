# Improve Service Initialization and Logging Configuration

## Why

The current Speech-to-Text API service has two architectural issues that affect maintainability, observability, and best practices:

**1. Lazy Model Initialization Problem:**
- Whisper model is initialized on first request (lazy loading) rather than at service startup
- First request experiences significant latency penalty (~1-2 seconds for model loading)
- Startup health checks don't validate that the model can be loaded successfully
- Service appears "healthy" even if model files are missing or corrupted
- Errors only surface when first transcription request arrives
- Not following best practice of "fail fast" at startup

**2. Logging Inconsistency Problem:**
- Core application uses `core/logger.py` with Loguru for structured logging
- Many scripts use `print()` statements instead of logger
- Inconsistent log formats make debugging and monitoring difficult
- Cannot control log levels for script output
- Logs from different components don't follow the same format
- Missing context (timestamps, log levels, source) in script output

## What Changes

We will improve service initialization, standardize logging, and reorganize model directory structure:

### 1. Eager Model Initialization
- **Initialize Whisper model at service startup** in the lifespan context manager
- **Validate model loading** before accepting requests
- **Fail fast** if model cannot be loaded (exit with clear error message)
- **Update health check** to verify model is initialized
- **Log model initialization** with timing and memory usage

### 2. Standardized Logging Configuration
- **Centralize all logging** through `core/logger.py`
- **Replace print() statements** in scripts with logger calls
- **Configure third-party library logging** to use Loguru
- **Add log level configuration** for different components
- **Improve log format** for better readability and filtering
- **Document logging best practices** in project conventions

### 3. Model Directory Reorganization
- **Move model directories** from project root into dedicated `models/` folder
- **Update WHISPER_ARTIFACTS_DIR** default from `.` to `models`
- **Update all references** in code, scripts, Docker, and Kubernetes configs
- **Update .gitignore** to reflect new model location
- **Improve project structure** for better organization and clarity

### 4. Environment Configuration Updates
- Update `WHISPER_ARTIFACTS_DIR` default to `models`
- Add `LOG_LEVEL` environment variable (already exists but not fully utilized)
- Add `LOG_FORMAT` for console vs JSON logging
- Update `.env.example` with all configuration examples

## User Review Required

> [!IMPORTANT]
> **Breaking Change**: Service will now fail to start if Whisper model cannot be loaded. This is intentional (fail-fast principle) but may affect deployment scripts that don't verify artifact downloads.

> [!WARNING]
> **Script Output Changes**: Scripts that currently use `print()` will now use structured logging. Any automation that parses script output may need updates.

## Proposed Changes

### Service Initialization

#### [MODIFY] [main.py](file:///Users/tantai/Workspaces/tools/speech-to-text/cmd/api/main.py)

Update the `lifespan` context manager to eagerly initialize the Whisper model:
- Call `bootstrap_container()` to initialize DI container
- Explicitly resolve `ITranscriber` to trigger model loading
- Add try-catch with detailed error logging
- Log model initialization timing and memory usage
- Update shutdown sequence to properly cleanup model

---

### Logging Configuration

#### [MODIFY] [logger.py](file:///Users/tantai/Workspaces/tools/speech-to-text/core/logger.py)

Enhance logging configuration:
- Add function to intercept standard library logging and route to Loguru
- Add function to configure third-party library loggers (httpx, urllib3, etc.)
- Add `configure_script_logging()` function for scripts
- Improve log format with more context (module, function, line)
- Add JSON logging option for production environments

#### [MODIFY] [download_whisper_artifacts.py](file:///Users/tantai/Workspaces/tools/speech-to-text/scripts/download_whisper_artifacts.py)

Replace all `print()` statements with logger calls:
- Import logger from `core.logger`
- Replace informational prints with `logger.info()`
- Replace error prints with `logger.error()`
- Add progress logging with appropriate levels

#### [MODIFY] [test_container_api.py](file:///Users/tantai/Workspaces/tools/speech-to-text/scripts/test_container_api.py)

Replace all `print()` statements with logger calls:
- Import logger from `core.logger`
- Use structured logging for test results
- Add test context to log messages

#### [MODIFY] Other scripts in `scripts/` directory

Apply same logging standardization to all scripts that use `print()`:
- `benchmark.py`
- `test_real_audio.py`
- `test_concurrent_requests.py`
- And others as identified

---

### Model Directory Reorganization

#### [MODIFY] [library_adapter.py](file:///Users/tantai/Workspaces/tools/speech-to-text/infrastructure/whisper/library_adapter.py)

Update MODEL_CONFIGS to use new paths:
- Change `"dir": "whisper_base_xeon"` to `"dir": "models/whisper_base_xeon"`
- Change `"dir": "whisper_small_xeon"` to `"dir": "models/whisper_small_xeon"`
- Change `"dir": "whisper_medium_xeon"` to `"dir": "models/whisper_medium_xeon"`

#### [MODIFY] [download_whisper_artifacts.py](file:///Users/tantai/Workspaces/tools/speech-to-text/scripts/download_whisper_artifacts.py)

Update artifact download script:
- Create `models/` directory if it doesn't exist
- Download artifacts to `models/whisper_{size}_xeon/` instead of root
- Update all path references

#### [MODIFY] [docker-compose.yml](file:///Users/tantai/Workspaces/tools/speech-to-text/docker-compose.yml)

Update volume mounts and environment:
- Change volume mount from `/app/whisper_base_xeon` to `/app/models/whisper_base_xeon`
- Update `WHISPER_ARTIFACTS_DIR` default to `models`

#### [MODIFY] [docker-compose.dev.yml](file:///Users/tantai/Workspaces/tools/speech-to-text/docker-compose.dev.yml)

Update development environment:
- Change `WHISPER_ARTIFACTS_DIR` from `.` to `models`
- Update `LD_LIBRARY_PATH` to include `models/` prefix

#### [MODIFY] [.gitignore](file:///Users/tantai/Workspaces/tools/speech-to-text/.gitignore)

Update model directory patterns:
- Change from `whisper_*_xeon/` to `models/whisper_*_xeon/`
- Keep root-level pattern for backward compatibility during migration

#### [MODIFY] Kubernetes configs in `k8s/`

Update all K8s manifests:
- `bench-pod.yaml`: Update volume mount paths
- `bench-configmap.yaml`: Update `WHISPER_ARTIFACTS_DIR` to `/app/models`
- Other configs as needed

#### [MODIFY] Diagnostic scripts in `scripts/`

Update hardcoded paths in:
- `scan_params.py`
- `scan_params_extended.py`
- `find_vad_offset.py`
- `disable_vad.py`
- `find_and_disable_vad.py`
- `test_vad_path.py`

---

### Configuration

#### [MODIFY] [config.py](file:///Users/tantai/Workspaces/tools/speech-to-text/core/config.py)

Update configuration settings:
- Change `whisper_artifacts_dir` default from `.` to `models`
- Add `log_format`: "console" or "json"
- Add `log_file_enabled`: Enable/disable file logging
- Add `script_log_level`: Separate log level for scripts

#### [MODIFY] [.env.example](file:///Users/tantai/Workspaces/tools/speech-to-text/.env.example)

Update environment variable examples:
- Change `WHISPER_ARTIFACTS_DIR=.` to `WHISPER_ARTIFACTS_DIR=models`
- Add comprehensive logging configuration examples
- Add comments explaining the new model directory structure

---

### Documentation

#### [MODIFY] [project.md](file:///Users/tantai/Workspaces/tools/speech-to-text/openspec/project.md)

Update project conventions:
- Add logging best practices section
- Document when to use different log levels
- Add examples of structured logging
- Document eager initialization pattern

## Verification Plan

### Automated Tests

1. **Unit Tests for Logging Configuration**
   ```bash
   # Create new test file for logging
   uv run pytest tests/test_logging_config.py -v
   ```
   - Test logger initialization
   - Test log level configuration
   - Test third-party logger interception

2. **Integration Test for Eager Initialization**
   ```bash
   # Test that service fails fast with missing model
   # Remove model files temporarily and verify startup fails
   uv run pytest tests/test_service_initialization.py -v
   ```
   - Test successful initialization with valid model
   - Test failure with missing model files
   - Test failure with corrupted model files

3. **Existing Tests Should Pass**
   ```bash
   # Run full test suite to ensure no regressions
   make test
   ```

### Manual Verification

1. **Verify Eager Initialization**
   - Start service with valid model: `make -f Makefile.dev dev-up`
   - Check logs show model initialization at startup
   - Verify first request has no loading delay
   - Stop service and remove model files
   - Start service again and verify it fails with clear error message

2. **Verify Logging Standardization**
   - Run artifact download script: `python scripts/download_whisper_artifacts.py base`
   - Verify output uses structured logging format (timestamps, levels, etc.)
   - Check that log level can be controlled via `LOG_LEVEL` environment variable
   - Verify logs are written to `logs/app.log` with correct format

3. **Verify Health Check**
   - Start service: `make -f Makefile.dev dev-up`
   - Call health endpoint: `curl http://localhost:8000/health`
   - Verify response includes model initialization status
   - Stop service, remove model, restart
   - Verify health check fails or service doesn't start
