"""
Transcription Routes - API endpoints for audio transcription.

Uses dependency injection for TranscribeService.
"""

import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, HttpUrl, Field
from typing import Optional
import asyncio

from core.logger import logger
from core.config import get_settings
from core.dependencies import get_transcribe_service_dependency
from services.transcription import TranscribeService
from internal.api.dependencies.auth import verify_internal_api_key

router = APIRouter()


class TranscribeRequest(BaseModel):
    """Request model for transcription from presigned URL."""

    media_url: HttpUrl = Field(
        ..., description="Presigned URL to audio/video file (e.g., MinIO)"
    )
    language: Optional[str] = Field(
        default="vi", description="Language hint for transcription (e.g., 'vi', 'en')"
    )


class TranscribeResponse(BaseModel):
    """Response model for transcription result."""

    status: str = Field(
        ..., description="Status of transcription (success, timeout, error)"
    )
    transcription: str = Field(..., description="Transcribed text")
    duration: float = Field(..., description="Audio duration in seconds")
    confidence: float = Field(..., description="Confidence score (0.0-1.0)")
    processing_time: float = Field(..., description="Processing time in seconds")


@router.post(
    "/transcribe",
    status_code=status.HTTP_200_OK,
    response_model=TranscribeResponse,
    tags=["Transcription"],
    summary="Transcribe audio from presigned URL",
    description="""
    Transcribe audio from a presigned URL (e.g., MinIO).
    
    **Authentication**: Requires `X-API-Key` header with internal API key.
    
    **Flow**:
    1. Download audio from `media_url` (streaming, not stored permanently)
    2. Optional: Extract audio from video using ffmpeg if needed
    3. Transcribe using Whisper backend with timeout protection
    4. Return transcription metadata
    
    **Timeout**: Processing will abort after configured timeout (default 30s).
    """,
)
async def transcribe(
    request: TranscribeRequest,
    api_key: str = Depends(verify_internal_api_key),
    service: TranscribeService = Depends(get_transcribe_service_dependency),
):
    """
    Transcribe audio from presigned URL with authentication and timeout.

    Uses dependency injection for TranscribeService.
    """
    try:
        logger.info(
            f"Transcription request from authenticated client for language={request.language}"
        )

        # Convert HttpUrl to string
        url_str = str(request.media_url)

        # Call transcription service with timeout (service is injected via DI)
        result = await service.transcribe_from_url(
            audio_url=url_str,
            language=request.language,
        )

        # Map service result to response schema
        return TranscribeResponse(
            status="success",
            transcription=result["text"],
            duration=result.get("audio_duration", 0.0),
            confidence=result.get("confidence", 0.98),
            processing_time=result["duration"],
        )

    except asyncio.TimeoutError:
        logger.error("Transcription timeout exceeded")
        return TranscribeResponse(
            status="timeout",
            transcription="",
            duration=0.0,
            confidence=0.0,
            processing_time=0.0,
        )
    except ValueError as e:
        error_msg = str(e)
        logger.error(f"Validation error: {error_msg}")
        if "too large" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=error_msg
            )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)
    except Exception as e:
        logger.error(f"Transcription error: {e}")
        logger.exception("Exception details:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}",
        )


# ============================================================================
# Local File Test Endpoint (Development Only)
# ============================================================================


class LocalTranscribeRequest(BaseModel):
    """Request model for transcription from local file path (dev only)."""

    file_path: str = Field(
        ...,
        description="Local file path to audio file (e.g., /app/scripts/test_audio/benchmark_30s.wav)",
    )
    language: Optional[str] = Field(
        default="vi", description="Language hint for transcription (e.g., 'vi', 'en')"
    )


@router.post(
    "/transcribe/local",
    status_code=status.HTTP_200_OK,
    response_model=TranscribeResponse,
    tags=["Transcription", "Development"],
    summary="[DEV ONLY] Transcribe audio from local file path",
    description="""
    **DEVELOPMENT ONLY** - Transcribe audio from a local file path.
    
    This endpoint is only available in development environment for testing purposes.
    It allows testing transcription without needing MinIO or external URLs.
    
    **Authentication**: Requires `X-API-Key` header with internal API key.
    
    **Example file paths**:
    - `/app/scripts/test_audio/benchmark_30s.wav` (30s English audio)
    - `/app/scripts/test_audio/7553444429583944980.mp3` (Vietnamese audio)
    """,
)
async def transcribe_local(
    request: LocalTranscribeRequest,
    api_key: str = Depends(verify_internal_api_key),
    service: TranscribeService = Depends(get_transcribe_service_dependency),
):
    """
    Transcribe audio from local file path (development only).

    This endpoint bypasses URL download and reads directly from filesystem.
    Only enabled in development environment.
    """
    settings = get_settings()

    # Security: Only allow in development environment
    if settings.environment.lower() not in ("development", "dev", "local"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is only available in development environment",
        )

    try:
        file_path = Path(request.file_path)

        # Validate file exists
        if not file_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File not found: {request.file_path}",
            )

        # Validate file is readable
        if not file_path.is_file():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Path is not a file: {request.file_path}",
            )

        # Get file size
        file_size = file_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)

        logger.info(
            f"[DEV] Local transcription request: path={request.file_path}, "
            f"size={file_size_mb:.2f}MB, language={request.language}"
        )

        # Call transcription service directly with file path
        import time

        start_time = time.time()

        # Use transcriber directly for local file
        transcriber = service.transcriber
        result_text = transcriber.transcribe(str(file_path), language=request.language)

        processing_time = time.time() - start_time

        # Get audio duration
        try:
            audio_duration = transcriber.get_audio_duration(str(file_path))
        except Exception:
            audio_duration = 0.0

        logger.info(
            f"[DEV] Local transcription complete: {len(result_text)} chars in {processing_time:.2f}s"
        )

        # Check for [inaudible] markers
        if "[inaudible]" in result_text.lower():
            inaudible_count = result_text.lower().count("[inaudible]")
            logger.warning(
                f"[DEV] Found {inaudible_count} [inaudible] markers in result"
            )

        return TranscribeResponse(
            status="success",
            transcription=result_text,
            duration=audio_duration,
            confidence=0.98,
            processing_time=processing_time,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[DEV] Local transcription error: {e}")
        logger.exception("Exception details:")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transcription error: {str(e)}",
        )
