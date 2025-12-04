"""
FastAPI Service - Main entry point for Speech-to-Text API.
Stateless transcription service using Whisper.cpp.
"""

import warnings
from contextlib import asynccontextmanager

# Suppress expected warnings at startup
warnings.filterwarnings(
    "ignore", message=".*protected namespace.*", category=UserWarning
)
warnings.filterwarnings("ignore", message=".*ffmpeg.*", category=RuntimeWarning)
warnings.filterwarnings("ignore", message=".*avconv.*", category=RuntimeWarning)

from fastapi import FastAPI, Request, HTTPException, status as http_status  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi.responses import JSONResponse  # type: ignore
from fastapi.exceptions import RequestValidationError  # type: ignore
from fastapi.staticfiles import StaticFiles  # type: ignore

from core.config import get_settings
from core.logger import logger
from core.dependencies import validate_dependencies
from internal.api.routes.transcribe_routes import router as transcribe_router
from internal.api.routes.async_transcribe_routes import (
    router as async_transcribe_router,
)
from internal.api.routes.health_routes import create_health_routes
from internal.api.utils import error_response


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifespan - startup and shutdown.

    Implements eager model initialization:
    - Loads Whisper model at startup (not on first request)
    - Validates model is loaded correctly
    - Fails fast if model cannot be loaded
    """
    import time

    try:
        settings = get_settings()
        logger.info(
            f"========== Starting {settings.app_name} v{settings.app_version} API service =========="
        )
        logger.info(f"Environment: {settings.environment}")
        logger.info(f"Debug mode: {settings.debug}")
        logger.info(f"API: {settings.api_host}:{settings.api_port}")

        # Validate system dependencies
        # Note: API service doesn't need ffmpeg (only Consumer service needs it)
        # Skip ffmpeg check to avoid unnecessary warnings
        try:
            validate_dependencies(check_ffmpeg=False)
            logger.info("System dependencies validated")
        except Exception as e:
            # For API service, dependency check is optional (warn, don't fail)
            logger.warning(f"Dependency validation warning: {e}")

        # Initialize DI Container
        from core.container import bootstrap_container

        bootstrap_container()
        logger.info("DI Container initialized")

        # EAGER MODEL INITIALIZATION
        # Load Whisper model at startup instead of on first request
        logger.info("Initializing Whisper model (eager loading)...")
        model_init_start = time.time()

        try:
            from core.container import get_transcriber
            from infrastructure.whisper.library_adapter import ModelInitError

            transcriber = get_transcriber()  # This triggers model loading

            # Validate model is actually loaded
            if not hasattr(transcriber, "ctx") or transcriber.ctx is None:
                raise ModelInitError("Whisper context is NULL after initialization")

            model_init_duration = time.time() - model_init_start

            # Store model info in app state for health checks
            app.state.model_initialized = True
            app.state.model_init_timestamp = time.time()
            app.state.model_size = transcriber.model_size
            app.state.model_config = transcriber.config

            logger.info(
                f"Whisper model initialized successfully: "
                f"model={transcriber.model_size}, "
                f"duration={model_init_duration:.2f}s, "
                f"estimated_ram={transcriber.config['ram_mb']}MB"
            )

        except Exception as e:
            logger.error(f"FATAL: Failed to initialize Whisper model: {e}")
            logger.exception("Model initialization error details:")
            # Mark model as not initialized
            app.state.model_initialized = False
            app.state.model_init_error = str(e)
            # Fail fast - don't start service if model can't load
            raise RuntimeError(f"Failed to initialize Whisper model: {e}") from e

        logger.info(
            f"========== {settings.app_name} API service started successfully =========="
        )

        yield

        # Shutdown sequence
        logger.info("========== Shutting down API service ==========")

        # Log model cleanup
        if hasattr(app.state, "model_initialized") and app.state.model_initialized:
            logger.info(f"Cleaning up Whisper model (size={app.state.model_size})...")
            # Model cleanup happens automatically via __del__ in WhisperLibraryAdapter

        logger.info("========== API service stopped successfully ==========")

    except Exception as e:
        logger.error(f"Fatal error in application lifespan: {e}")
        logger.exception("Lifespan error details:")
        raise


def create_app() -> FastAPI:
    """
    Factory function to create and configure the FastAPI application.
    Includes comprehensive logging and error handling.

    Returns:
        FastAPI: Configured application instance
    """
    try:
        settings = get_settings()

        # OpenAPI metadata
        description = """
## Speech-to-Text API

A stateless Speech-to-Text service powered by Whisper.cpp.

### Key Features

* **Direct Transcription** - Transcribe audio from URL with `/transcribe` endpoint
* **Multi-language Support** - Support for Vietnamese, English, and other languages
* **Multiple Models** - Choose from Whisper models: tiny, base, small, medium, large
* **Health Monitoring** - System health checks

### Processing Flow

1. **Request** - POST audio URL to `/transcribe`
2. **Download** - Service downloads audio from provided URL
3. **Transcribe** - Whisper.cpp processes the audio
4. **Response** - Get transcription result immediately

### Supported Audio Formats

MP3, WAV, M4A, MP4, AAC, OGG, FLAC, WMA, WEBM, MKV, AVI, MOV

        """

        tags_metadata = [
            {
                "name": "Transcription",
                "description": "Direct audio transcription from URL.",
            },
            {
                "name": "Async Transcription",
                "description": "Async transcription with polling pattern for long-running jobs.",
            },
            {
                "name": "Health",
                "description": "Health check endpoints for monitoring API status.",
            },
            {
                "name": "Development",
                "description": "Development-only endpoints (disabled in production).",
            },
        ]

        # Create FastAPI application
        app = FastAPI(
            title=settings.app_name,
            version=settings.app_version,
            description=description,
            lifespan=lifespan,
            openapi_tags=tags_metadata,
            contact={
                "name": "Development Team",
                "email": "nguyentantai.dev@gmail.com",
            },
            license_info={},
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json",
        )

        # Add CORS middleware
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # Configure appropriately for production
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Mount swagger static files for /swagger/index.html access
        try:
            from pathlib import Path

            swagger_dir = Path(__file__).parent / "swagger_static"
            if swagger_dir.exists():
                app.mount(
                    "/swagger",
                    StaticFiles(directory=str(swagger_dir), html=True),
                    name="swagger",
                )
        except Exception as e:
            logger.warning(f"Failed to mount swagger static files: {e}")

        # Include API routes
        app.include_router(transcribe_router)  # /transcribe (sync)
        app.include_router(async_transcribe_router)  # /api/transcribe (async)
        health_router = create_health_routes(app)
        app.include_router(health_router)  # / and /health

        # Add exception handlers for unified response format
        @app.exception_handler(RequestValidationError)
        async def validation_exception_handler(
            request: Request, exc: RequestValidationError
        ):
            """Handle validation errors - return 422 with errors field."""
            raw_errors = exc.errors()
            # Build errors dict: field -> message
            errors_dict = {}
            for e in raw_errors:
                field = e["loc"][-1] if e["loc"] else "unknown"
                errors_dict[str(field)] = e["msg"]

            error_msg = "; ".join([f"{k}: {v}" for k, v in errors_dict.items()])
            logger.error(f"Validation error: {error_msg}")

            return JSONResponse(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=error_response(
                    message="Validation error",
                    error_code=1,
                    errors=errors_dict,
                ),
            )

        @app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            """Handle HTTP exceptions with unified format."""
            logger.error(f"HTTP error: {exc.detail}")
            return JSONResponse(
                status_code=exc.status_code,
                content=error_response(
                    message=exc.detail,
                    error_code=1,
                    errors={"detail": exc.detail},
                ),
            )

        @app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            """Handle all other exceptions with unified format."""
            logger.error(f"Unhandled exception: {str(exc)}")
            logger.exception("Exception details:")
            return JSONResponse(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=error_response(
                    message="Internal server error",
                    error_code=1,
                    errors={"detail": str(exc)},
                ),
            )

        return app

    except Exception as e:
        logger.error(f"Failed to create FastAPI application: {e}")
        logger.exception("Application creation error details:")
        raise


# Create application instance
try:
    app = create_app()
except Exception as e:
    logger.error(f"Failed to create application instance: {e}")
    logger.exception("Startup error details:")
    raise


# Run with: uvicorn cmd.api.main:app --host 0.0.0.0 --port 8000 --reload
if __name__ == "__main__":
    import uvicorn  # type: ignore
    import sys
    import os

    try:
        settings = get_settings()

        logger.info("========== Starting Uvicorn Server ==========")
        logger.info(f"Host: {settings.api_host}")
        logger.info(f"Port: {settings.api_port}")
        logger.info(f"Reload: {settings.api_reload}")
        logger.info(f"Workers: {settings.api_workers}")

        # When using reload=True, uvicorn spawns subprocess which needs PYTHONPATH
        # Ensure project root is in PYTHONPATH for subprocess
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        if project_root not in sys.path:
            sys.path.insert(0, project_root)

        # Set PYTHONPATH environment variable for subprocess (uvicorn reload)
        current_pythonpath = os.environ.get("PYTHONPATH", "")
        if project_root not in current_pythonpath:
            new_pythonpath = (
                f"{project_root}:{current_pythonpath}"
                if current_pythonpath
                else project_root
            )
            os.environ["PYTHONPATH"] = new_pythonpath

        # Use string path when reload=True, app instance when reload=False
        if settings.api_reload:
            # For reload, uvicorn needs string path and will import it
            # PYTHONPATH is already set above for subprocess
            uvicorn.run(
                "cmd.api.main:app",
                host=settings.api_host,
                port=settings.api_port,
                reload=True,
                log_level="info" if settings.debug else "warning",
            )
        else:
            # For production, pass app instance directly
            uvicorn.run(
                app,
                host=settings.api_host,
                port=settings.api_port,
                reload=False,
                log_level="info" if settings.debug else "warning",
            )

    except Exception as e:
        logger.error(f"Failed to start Uvicorn server: {e}")
        logger.exception("Uvicorn startup error details:")
        raise
