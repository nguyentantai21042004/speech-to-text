"""
Transcription Routes - API endpoints for audio transcription.

Uses dependency injection for TranscribeService.
"""

import time
from pathlib import Path
from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import asyncio

from core.logger import logger
from core.config import get_settings
from core.dependencies import get_transcribe_service_dependency
from services.transcription import TranscribeService
from internal.api.dependencies.auth import verify_internal_api_key

router = APIRouter()


class TranscribeRequest(BaseModel):
    """Request model for transcription from URL."""

    media_url: str = Field(
        ...,
        description="URL to audio/video file. Supports: http://, https://, minio://bucket/path",
    )
    language: Optional[str] = Field(
        default="vi", description="Language hint for transcription (e.g., 'vi', 'en')"
    )

    @field_validator("media_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate URL scheme (http, https, or minio)."""
        if not v:
            raise ValueError("media_url cannot be empty")
        if not v.startswith(("http://", "https://", "minio://")):
            raise ValueError("media_url must start with http://, https://, or minio://")
        return v


class TranscribeResponse(BaseModel):
    """
    Unified response model for transcription API.

    This response format is ALWAYS returned regardless of success or error.
    """

    error_code: int = Field(
        ..., description="Error code: 0 = success, 1 = error/timeout"
    )
    message: str = Field(
        ..., description="Human-readable message describing the result"
    )
    transcription: str = Field(default="", description="Transcribed text")
    duration: float = Field(default=0.0, description="Audio duration in seconds")
    confidence: float = Field(default=0.0, description="Confidence score (0.0-1.0)")
    processing_time: float = Field(
        default=0.0, description="Processing time in seconds"
    )


def _success_response(
    transcription: str,
    duration: float,
    confidence: float,
    processing_time: float,
) -> TranscribeResponse:
    """Create success response."""
    return TranscribeResponse(
        error_code=0,
        message="Transcription successful",
        transcription=transcription,
        duration=duration,
        confidence=confidence,
        processing_time=processing_time,
    )


def _error_response(message: str, http_status: int = 500) -> JSONResponse:
    """Create error response with consistent format."""
    return JSONResponse(
        status_code=http_status,
        content=TranscribeResponse(
            error_code=1,
            message=message,
            transcription="",
            duration=0.0,
            confidence=0.0,
            processing_time=0.0,
        ).model_dump(),
    )


@router.post(
    "/transcribe",
    response_model=TranscribeResponse,
    tags=["Transcription"],
    summary="Transcribe audio from URL",
    description="""
Transcribe audio from a URL (MinIO or HTTP).

**Authentication**: Requires `X-API-Key` header.

**Response Format** (always consistent):
```json
{
  "error_code": 0,        // 0 = success, 1 = error
  "message": "...",       // Human-readable message
  "transcription": "...", // Transcribed text (empty on error)
  "duration": 34.06,      // Audio duration in seconds
  "confidence": 0.98,     // Confidence score
  "processing_time": 8.5  // Processing time in seconds
}
```

**HTTP Status Codes**:
- 200: Success
- 400: Bad request (invalid URL format)
- 401: Unauthorized (missing/invalid API key)
- 408: Request timeout
- 413: File too large
- 500: Internal server error
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
) -> Response:
    """Transcribe audio from URL with authentication and timeout."""
    try:
        logger.info(
            f"Transcription request from authenticated client for language={request.language}"
        )

        result = await service.transcribe_from_url(
            audio_url=request.media_url,
            language=request.language,
        )

        return _success_response(
            transcription=result["text"],
            duration=result.get("audio_duration", 0.0),
            confidence=result.get("confidence", 0.98),
            processing_time=result["duration"],
        )

    except asyncio.TimeoutError:
        logger.error("Transcription timeout exceeded")
        return _error_response("Transcription timeout exceeded", http_status=408)

    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Validation error: {error_msg}")
        if "too large" in error_msg.lower():
            return _error_response(error_msg, http_status=413)
        return _error_response(error_msg, http_status=400)

    except Exception as e:
        logger.error(f"Transcription error: {e}")
        return _error_response(f"Internal server error: {str(e)}", http_status=500)


# ============================================================================
# Local File Test Endpoint (Development Only)
# ============================================================================


class LocalTranscribeRequest(BaseModel):
    """Request model for transcription from local file path (dev only)."""

    file_path: str = Field(
        ...,
        description="Local file path to audio file",
    )
    language: Optional[str] = Field(
        default="vi", description="Language hint for transcription"
    )


@router.post(
    "/transcribe/local",
    response_model=TranscribeResponse,
    tags=["Transcription", "Development"],
    summary="[DEV ONLY] Transcribe from local file",
)
async def transcribe_local(
    request: LocalTranscribeRequest,
    api_key: str = Depends(verify_internal_api_key),
    service: TranscribeService = Depends(get_transcribe_service_dependency),
) -> Response:
    """Transcribe audio from local file path (development only)."""
    settings = get_settings()

    if settings.environment.lower() not in ("development", "dev", "local"):
        return _error_response(
            "This endpoint is only available in development environment",
            http_status=403,
        )

    try:
        file_path = Path(request.file_path)

        if not file_path.exists():
            return _error_response(
                f"File not found: {request.file_path}", http_status=404
            )

        if not file_path.is_file():
            return _error_response(
                f"Path is not a file: {request.file_path}", http_status=400
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

        return _success_response(
            transcription=result_text,
            duration=audio_duration,
            confidence=0.98,
            processing_time=processing_time,
        )

    except Exception as e:
        logger.error(f"[DEV] Local transcription error: {e}")
        return _error_response(f"Transcription error: {str(e)}", http_status=500)
