# Design: Service Initialization and Logging Improvements

## Architecture Overview

This change improves two cross-cutting concerns in the Speech-to-Text API:

1. **Service Initialization**: Move from lazy to eager model loading
2. **Logging Standardization**: Centralize all logging through Loguru

## Technical Approach

### 1. Eager Model Initialization

**Current Flow:**
```
Service Startup → DI Container Bootstrap → Wait for First Request
                                                    ↓
                                          First Request Arrives
                                                    ↓
                                          Resolve ITranscriber (lazy)
                                                    ↓
                                          Load Whisper Model (1-2s delay)
                                                    ↓
                                          Process Request
```

**New Flow:**
```
Service Startup → DI Container Bootstrap → Eager Model Load
                                                    ↓
                                          Validate Model Loaded
                                                    ↓
                                          Service Ready (fast fail if error)
                                                    ↓
                                          First Request Arrives
                                                    ↓
                                          Resolve ITranscriber (already loaded)
                                                    ↓
                                          Process Request (no loading delay)
```

**Implementation:**

Update `cmd/api/main.py` lifespan context manager:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        settings = get_settings()
        logger.info(f"========== Starting {settings.app_name} v{settings.app_version} ==========")
        
        # Validate system dependencies
        validate_dependencies(check_ffmpeg=False)
        
        # Initialize DI Container
        from core.container import bootstrap_container
        bootstrap_container()
        logger.info("DI Container initialized")
        
        # EAGER MODEL INITIALIZATION (NEW)
        logger.info("Initializing Whisper model...")
        start_time = time.time()
        
        try:
            from core.container import get_transcriber
            transcriber = get_transcriber()  # This triggers model loading
            
            # Validate model is actually loaded
            if not hasattr(transcriber, 'ctx') or transcriber.ctx is None:
                raise ModelInitError("Whisper context is NULL after initialization")
            
            init_duration = time.time() - start_time
            logger.info(
                f"Whisper model initialized successfully: "
                f"model={transcriber.model_size}, "
                f"duration={init_duration:.2f}s, "
                f"estimated_ram={transcriber.config['ram_mb']}MB"
            )
            
        except Exception as e:
            logger.error(f"FATAL: Failed to initialize Whisper model: {e}")
            logger.exception("Model initialization error details:")
            raise  # Fail fast - don't start service if model can't load
        
        logger.info(f"========== {settings.app_name} started successfully ==========")
        
        yield
        
        # Shutdown
        logger.info("========== Shutting down API service ==========")
        # Model cleanup happens automatically via __del__
        
    except Exception as e:
        logger.error(f"Fatal error in application lifespan: {e}")
        raise
```

**Benefits:**
- First request has consistent latency (no model loading)
- Service fails fast if model files are missing/corrupted
- Health checks can verify model is loaded
- Easier to debug startup issues

### 2. Logging Standardization

**Current State:**
- Core app uses `core/logger.py` with Loguru ✓
- Scripts use `print()` statements ✗
- Third-party libraries use standard `logging` ✗
- Inconsistent formats and no log level control ✗

**New Architecture:**

```
┌─────────────────────────────────────────────────────────┐
│                    core/logger.py                        │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Loguru (Primary Logger)                           │ │
│  │  - Structured logging                              │ │
│  │  - Console handler (colored, configurable level)   │ │
│  │  - File handler (app.log, always DEBUG)            │ │
│  │  - Error handler (error.log, ERROR+)               │ │
│  └────────────────────────────────────────────────────┘ │
│                                                           │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Standard Library Logging Interception             │ │
│  │  - Intercept logging.Logger calls                  │ │
│  │  - Route to Loguru                                 │ │
│  └────────────────────────────────────────────────────┘ │
│                                                           │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Third-Party Logger Configuration                  │ │
│  │  - httpx: WARNING                                  │ │
│  │  - urllib3: WARNING                                │ │
│  │  - boto3: INFO                                     │ │
│  └────────────────────────────────────────────────────┘ │
│                                                           │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Script Logging Helper                             │ │
│  │  - configure_script_logging()                      │ │
│  │  - Console only (no files)                         │ │
│  │  - Simplified format                               │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**Implementation:**

Enhance `core/logger.py`:

```python
import logging
import sys
from loguru import logger

class InterceptHandler(logging.Handler):
    """Intercept standard logging and route to Loguru."""
    
    def emit(self, record):
        # Get corresponding Loguru level
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        
        # Find caller from where logging call originated
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1
        
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )

def configure_third_party_loggers():
    """Configure third-party library loggers to reduce noise."""
    # Suppress verbose logs from HTTP libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.INFO)
    logging.getLogger("boto3").setLevel(logging.INFO)
    
    logger.debug("Third-party loggers configured")

def intercept_standard_logging():
    """Intercept Python standard library logging and route to Loguru."""
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    logger.debug("Standard library logging intercepted")

def configure_script_logging(level: str = "INFO"):
    """
    Configure logging for standalone scripts.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
    """
    # Remove default handlers
    logger.remove()
    
    # Add console handler only (no files for scripts)
    logger.add(
        sys.stdout,
        colorize=True,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level=level.upper(),
    )
    
    logger.debug(f"Script logging configured (level={level})")

# In setup_logger(), add:
def setup_logger():
    # ... existing setup ...
    
    # NEW: Intercept standard library logging
    intercept_standard_logging()
    
    # NEW: Configure third-party loggers
    configure_third_party_loggers()
```

**Script Migration Example:**

Before (`scripts/download_whisper_artifacts.py`):
```python
print(f"📦 Downloading Whisper {model_size.upper()} artifacts...")
print(f"   From: {MINIO_ENDPOINT}/{BUCKET_NAME}")
print(f"   To: {output_dir}/")
```

After:
```python
from core.logger import logger, configure_script_logging

# At script start
configure_script_logging()

# Replace prints
logger.info(f"Downloading Whisper {model_size.upper()} artifacts...")
logger.info(f"From: {MINIO_ENDPOINT}/{BUCKET_NAME}")
logger.info(f"To: {output_dir}/")
```

### 3. Configuration Updates

Add to `core/config.py`:

```python
class Settings(BaseSettings):
    # ... existing settings ...
    
    # Logging configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_format: str = Field(default="console", env="LOG_FORMAT")  # console or json
    log_file_enabled: bool = Field(default=True, env="LOG_FILE_ENABLED")
    script_log_level: str = Field(default="INFO", env="SCRIPT_LOG_LEVEL")
```

Update `.env.example`:

```bash
# ============================================================================
# Logging Settings
# ============================================================================
# Log level for application: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_LEVEL=INFO

# Log format: console (colored, human-readable) or json (for log aggregation)
LOG_FORMAT=console

# Enable file logging (logs/app.log and logs/error.log)
LOG_FILE_ENABLED=true

# Log level for standalone scripts
SCRIPT_LOG_LEVEL=INFO
```

## Migration Strategy

1. **Phase 1: Logging Foundation** (Low Risk)
   - Enhance `core/logger.py` with new functions
   - No breaking changes to existing code
   - All existing logs continue to work

2. **Phase 2: Script Migration** (Low Risk)
   - Migrate scripts one by one
   - Test each script individually
   - Scripts are not critical path for API service

3. **Phase 3: Eager Initialization** (Medium Risk)
   - Update service startup
   - Test thoroughly in dev environment
   - **Breaking change**: Service will fail to start if model missing

4. **Phase 4: Validation** (Critical)
   - Run full test suite
   - Manual testing of startup scenarios
   - Verify logs are readable and useful

## Rollback Plan

If issues arise:

1. **Logging Issues**: Revert `core/logger.py` changes, scripts will still work with print()
2. **Initialization Issues**: Revert `main.py` lifespan changes, model will lazy-load again
3. **Both are independent**: Can rollback one without affecting the other

## Performance Impact

**Eager Initialization:**
- Startup time: +1-2 seconds (one-time cost)
- First request latency: -1-2 seconds (benefit)
- Memory: No change (model was loaded anyway)

**Logging:**
- Negligible performance impact
- Loguru is highly optimized
- File I/O is async

## Security Considerations

None - this change doesn't affect authentication, authorization, or data handling.

## Compatibility

- **Docker**: No changes needed, ENV variables are backward compatible
- **Kubernetes**: No changes needed, existing deployments will work
- **Scripts**: Old scripts with print() will continue to work until migrated
