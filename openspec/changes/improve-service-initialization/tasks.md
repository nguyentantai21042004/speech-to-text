# Implementation Tasks: Improve Service Initialization and Logging

## Phase 0: Model Directory Reorganization (Foundation)

### 0.1 Update Configuration and Core Code
- [x] Update `core/config.py` to change `whisper_artifacts_dir` default from `.` to `models`
- [x] Update `infrastructure/whisper/library_adapter.py` MODEL_CONFIGS paths
- [x] Create `models/.gitkeep` to ensure directory is tracked
- [x] Update `.gitignore` to use `models/whisper_*_xeon/` pattern

### 0.2 Update Scripts
- [x] Update `scripts/download_whisper_artifacts.py` to create and use `models/` directory
- [x] Update `scripts/scan_params.py` to use configuration instead of hardcoded path
- [x] Update `scripts/scan_params_extended.py`
- [x] Update `scripts/find_vad_offset.py`
- [x] Update `scripts/disable_vad.py`
- [x] Update `scripts/find_and_disable_vad.py`
- [x] Update `scripts/test_vad_path.py`

### 0.3 Update Docker Configuration
- [x] Update `docker-compose.yml` volume mounts and WHISPER_ARTIFACTS_DIR
- [x] Update `docker-compose.dev.yml` environment and LD_LIBRARY_PATH
- [x] Test Docker build and verify model paths work

### 0.4 Update Kubernetes Configuration
- [x] Update `k8s/bench-pod.yaml` volume mount paths
- [x] Update `k8s/bench-configmap.yaml` WHISPER_ARTIFACTS_DIR
- [x] Update other K8s manifests as needed

### 0.5 Update Environment Files
- [x] Update `.env.example` WHISPER_ARTIFACTS_DIR to `models`
- [x] Add migration notes in comments
- [x] Document backward compatibility (can still use `.` if needed)

### 0.6 Migration Testing
- [x] Create `models/` directory locally
- [x] Move existing `whisper_*_xeon/` directories to `models/`
- [x] Test application startup with new paths
- [x] Test artifact download script creates correct structure
- [x] Verify all scripts work with new paths

## Phase 1: Logging Standardization (Foundation)

### 1.1 Enhance Core Logger
- [ ] Update `core/logger.py` to add standard library logging interception
- [ ] Add function to configure third-party library loggers (httpx, urllib3, boto3)
- [ ] Add `configure_script_logging()` function for standalone scripts
- [ ] Add JSON logging format option for production
- [ ] Add tests for logging configuration

### 1.2 Update Configuration
- [ ] Add `LOG_FORMAT` setting to `core/config.py` (console/json)
- [ ] Add `LOG_FILE_ENABLED` setting
- [ ] Add `SCRIPT_LOG_LEVEL` setting for script verbosity
- [ ] Update `.env.example` with comprehensive logging examples
- [ ] Document logging configuration in comments

### 1.3 Migrate Scripts to Structured Logging
- [ ] Update `scripts/download_whisper_artifacts.py` (replace all print statements)
- [ ] Update `scripts/test_container_api.py` (replace all print statements)
- [ ] Update `scripts/benchmark.py` (replace all print statements)
- [ ] Update `scripts/test_real_audio.py` (replace all print statements)
- [ ] Update remaining scripts in `scripts/` directory
- [ ] Test each script to verify logging works correctly

## Phase 2: Eager Model Initialization

### 2.1 Update Service Startup
- [ ] Modify `cmd/api/main.py` lifespan context manager
- [ ] Add explicit model initialization call after DI container bootstrap
- [ ] Add comprehensive error handling with clear error messages
- [ ] Log model initialization timing (start, duration, memory)
- [ ] Add model validation (verify context is not NULL)
- [ ] Update shutdown sequence to log model cleanup

### 2.2 Update Health Check
- [ ] Modify health check endpoint to include model status
- [ ] Add model initialization timestamp to health response
- [ ] Add model size and configuration to health response
- [ ] Test health check with and without model loaded

### 2.3 Update Container Bootstrap
- [ ] Ensure `bootstrap_container()` is idempotent
- [ ] Add logging for each registration step
- [ ] Verify singleton pattern works with eager initialization

## Phase 3: Testing and Validation

### 3.1 Unit Tests
- [ ] Create `tests/test_logging_config.py` for logger tests
- [ ] Test log level configuration
- [ ] Test third-party logger interception
- [ ] Test JSON vs console format
- [ ] Create `tests/test_service_initialization.py`
- [ ] Test successful initialization with valid model
- [ ] Test failure with missing model files
- [ ] Test failure with corrupted model files

### 3.2 Integration Tests
- [ ] Run full test suite to verify no regressions
- [ ] Test service startup with different model sizes
- [ ] Test health check responses
- [ ] Verify first request has no loading delay

### 3.3 Manual Verification
- [ ] Start service and verify model loads at startup (check logs)
- [ ] Verify first transcription request has no model loading delay
- [ ] Remove model files and verify service fails to start with clear error
- [ ] Run scripts and verify structured logging output
- [ ] Test LOG_LEVEL environment variable controls verbosity
- [ ] Verify logs written to files have correct format

## Phase 4: Documentation

### 4.1 Update Project Documentation
- [ ] Update `openspec/project.md` with logging best practices
- [ ] Add section on eager initialization pattern
- [ ] Document log levels and when to use them
- [ ] Add examples of structured logging

### 4.2 Update README
- [ ] Add logging configuration section
- [ ] Document LOG_LEVEL and LOG_FORMAT options
- [ ] Add troubleshooting for model initialization failures

## Dependencies and Parallelization

**Sequential Dependencies:**
- Phase 1 must complete before Phase 2 (logging foundation needed for initialization logs)
- Phase 2 must complete before Phase 3 (need implementation to test)
- Phase 3 must complete before Phase 4 (verify before documenting)

**Parallelizable Work:**
- Within Phase 1.3: All script migrations can be done in parallel
- Within Phase 3.1: Test files can be created in parallel
- Within Phase 4: Documentation updates can be done in parallel
