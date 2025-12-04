"""
Transcription Routes - API endpoints for synchronous audio transcription.

All responses use unified format:
{
    "error_code": int,
    "message": str,
    "data": {...},
    "errors": {...}  // only on error
}
"""

import asyncio
import time
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from core.config import get_settings
from core.dependencies import get_transcribe_service_dependency
from core.logger import logger
from internal.api.dependencies.auth import verify_internal_api_key
from internal.api.schemas.common_schemas import StandardResponse, TranscriptionData
from internal.api.utils import success_response, json_error_response
from services.transcription import TranscribeService

router = APIRouter()


# ============================================================================
# Request Models
# ============================================================================


class TranscribeRequest(BaseModel):
    """Request model for transcription from URL."""

    media_url: str = Field(
        ...,
        description="URL to audio/video file (http/https/minio)",
    )
    language: Optional[str] = Field(
        default="vi",
        description="Language hint (e.g., 'vi', 'en')",
    )

    @field_validator("media_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v:
            raise ValueError("media_url cannot be empty")
        if not v.startswith(("http://", "https://", "minio://")):
            raise ValueError("media_url must start with http://, https://, or minio://")
        return v


class LocalTranscribeRequest(BaseModel):
    """Request model for transcription from local file (dev only)."""

    file_path: str = Field(..., description="Local file path to audio file")
    language: Optional[str] = Field(default="vi", description="Language hint")


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/transcribe",
    response_model=StandardResponse,
    tags=["Transcription"],
    summary="Transcribe audio from URL (sync)",
    description="""
Transcribe audio from a URL (MinIO or HTTP) synchronously.

**Authentication**: Requires `X-API-Key` header.

**Response Format:**
```json
{
  "error_code": 0,
  "message": "Transcription successful",
  "data": {
    "transcription": "...",
    "duration": 34.06,
    "confidence": 0.98,
    "processing_time": 8.5
  }
}
```

**Note**: For long audio (> 1 min), use async API `/api/v1/transcribe` instead.
""",
    responses={
        200: {"description": "Transcription successful"},
        400: {"description": "Bad request"},
        401: {"description": "Unauthorized"},
        408: {"description": "Request timeout"},
        413: {"description": "File too large"},
        500: {"description": "Internal server error"},
    },
)
async def transcribe(
    request: TranscribeRequest,
    api_key: str = Depends(verify_internal_api_key),
    service: TranscribeService = Depends(get_transcribe_service_dependency),
) -> JSONResponse:
    """Transcribe audio from URL with authentication and timeout."""
    try:
        logger.info(f"Transcription request for language={request.language}")

        result = await service.transcribe_from_url(
            audio_url=request.media_url,
            language=request.language,
        )

        data = TranscriptionData(
            transcription=result["text"],
            duration=result.get("audio_duration", 0.0),
            confidence=result.get("confidence", 0.98),
            processing_time=result["duration"],
        )

        return JSONResponse(
            status_code=200,
            content=success_response(
                message="Transcription successful",
                data=data.model_dump(exclude_none=True),
            ),
        )

    except asyncio.TimeoutError:
        logger.error("Transcription timeout exceeded")
        return json_error_response(
            message="Transcription timeout exceeded",
            status_code=408,
            errors={"detail": "Request took too long. Use async API for long audio."},
        )

    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Validation error: {error_msg}")

        if "too large" in error_msg.lower():
            return json_error_response(
                message="File too large",
                status_code=413,
                errors={"detail": error_msg},
            )

        return json_error_response(
            message="Bad request",
            status_code=400,
            errors={"detail": error_msg},
        )

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return json_error_response(
            message="Internal server error",
            status_code=500,
            errors={"detail": str(e)},
        )


@router.post(
    "/transcribe/local",
    response_model=StandardResponse,
    tags=["Development"],
    summary="[DEV ONLY] Transcribe from local file",
)
async def transcribe_local(
    request: LocalTranscribeRequest,
    api_key: str = Depends(verify_internal_api_key),
    service: TranscribeService = Depends(get_transcribe_service_dependency),
) -> JSONResponse:
    """Transcribe audio from local file path (development only)."""
    settings = get_settings()

    if settings.environment.lower() not in ("development", "dev", "local"):
        return json_error_response(
            message="Forbidden",
            status_code=403,
            errors={"detail": "This endpoint is only available in development"},
        )

    try:
        file_path = Path(request.file_path)

        if not file_path.exists():
            return json_error_response(
                message="File not found",
                status_code=404,
                errors={"file_path": f"File not found: {request.file_path}"},
            )

        if not file_path.is_file():
            return json_error_response(
                message="Invalid path",
                status_code=400,
                errors={"file_path": f"Path is not a file: {request.file_path}"},
            )

        logger.info(f"[DEV] Local transcription: {request.file_path}")

        start_time = time.time()
        transcriber = service.transcriber
        result_text = transcriber.transcribe(str(file_path), language=request.language)
        processing_time = time.time() - start_time

        try:
            audio_duration = transcriber.get_audio_duration(str(file_path))
        except Exception:
            audio_duration = 0.0

        logger.info(
            f"[DEV] Complete: {len(result_text)} chars in {processing_time:.2f}s"
        )

        data = TranscriptionData(
            transcription=result_text,
            duration=audio_duration,
            confidence=0.98,
            processing_time=processing_time,
        )

        return JSONResponse(
            status_code=200,
            content=success_response(
                message="Transcription successful",
                data=data.model_dump(exclude_none=True),
            ),
        )

    except Exception as e:
        logger.error(f"[DEV] Local transcription error: {e}")
        return json_error_response(
            message="Transcription error",
            status_code=500,
            errors={"detail": str(e)},
        )
