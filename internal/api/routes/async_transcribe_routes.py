"""
Async Transcription Routes - API endpoints for async transcription with polling pattern.

All responses use unified format:
{
    "error_code": int,
    "message": str,
    "data": {...},
    "errors": {...}  // only on error
}

Endpoints:
- POST /api/v1/transcribe - Submit job (returns 202 Accepted)
- GET /api/v1/transcribe/{request_id} - Poll job status
"""

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from typing import Optional

from core.logger import logger
from internal.api.dependencies.auth import verify_internal_api_key
from internal.api.schemas.common_schemas import (
    StandardResponse,
    JobStatus,
    AsyncJobData,
    TranscriptionData,
    FailedJobData,
)
from internal.api.utils import success_response, json_error_response
from services.async_transcription import (
    get_async_transcription_service,
    AsyncTranscriptionService,
)

router = APIRouter(prefix="/api/v1", tags=["Async Transcription"])


# ============================================================================
# Request Models
# ============================================================================


class AsyncTranscribeRequest(BaseModel):
    """Request model for async transcription job submission."""

    request_id: str = Field(
        ...,
        description="Client-generated unique request ID (e.g., post_id)",
        min_length=1,
        max_length=256,
    )
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

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("request_id cannot be empty")
        return v.strip()


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    "/transcribe",
    response_model=StandardResponse,
    status_code=202,
    summary="Submit async transcription job",
    description="""
Submit an async transcription job with client-provided request_id.

**Response Format:**
```json
{
  "error_code": 0,
  "message": "Job submitted successfully",
  "data": {
    "request_id": "post_123456",
    "status": "PROCESSING"
  }
}
```

**Idempotency**: If job exists, returns current status without creating new job.
""",
    responses={
        202: {"description": "Job submitted/exists"},
        400: {"description": "Bad request"},
        401: {"description": "Unauthorized"},
        422: {"description": "Validation error"},
        500: {"description": "Internal server error"},
    },
)
async def submit_transcription_job(
    request: AsyncTranscribeRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_internal_api_key),
    service: AsyncTranscriptionService = Depends(get_async_transcription_service),
) -> JSONResponse:
    """Submit async transcription job."""
    try:
        logger.info(f"Async job submission: request_id={request.request_id}")

        result = await service.submit_job(
            request_id=request.request_id,
            media_url=request.media_url,
            language=request.language,
        )

        # Add background task for new jobs only
        if (
            result["status"] == "PROCESSING"
            and "submitted successfully" in result["message"]
        ):
            background_tasks.add_task(
                service.process_job_background,
                request_id=request.request_id,
                media_url=request.media_url,
                language=request.language,
            )
            logger.info(f"Background task added for job {request.request_id}")

        # Build response data
        data = AsyncJobData(
            request_id=result["request_id"],
            status=JobStatus(result["status"]),
        )

        return JSONResponse(
            status_code=202,
            content=success_response(
                message=result["message"],
                data=data.model_dump(),
            ),
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return json_error_response(
            message="Validation error",
            status_code=400,
            errors={"detail": str(e)},
        )

    except Exception as e:
        logger.error(f"Failed to submit job: {e}")
        return json_error_response(
            message="Internal server error",
            status_code=500,
            errors={"detail": str(e)},
        )


@router.get(
    "/transcribe/{request_id}",
    response_model=StandardResponse,
    summary="Poll job status",
    description="""
Poll the status of an async transcription job.

**Response Format (COMPLETED):**
```json
{
  "error_code": 0,
  "message": "Transcription completed",
  "data": {
    "request_id": "post_123456",
    "status": "COMPLETED",
    "transcription": "...",
    "duration": 45.5,
    "confidence": 0.98,
    "processing_time": 12.3
  }
}
```

**Response Format (FAILED):**
```json
{
  "error_code": 0,
  "message": "Transcription failed",
  "data": {
    "request_id": "post_123456",
    "status": "FAILED",
    "error": "Download failed"
  }
}
```
""",
    responses={
        200: {"description": "Job status returned"},
        401: {"description": "Unauthorized"},
        404: {"description": "Job not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_transcription_status(
    request_id: str,
    api_key: str = Depends(verify_internal_api_key),
    service: AsyncTranscriptionService = Depends(get_async_transcription_service),
) -> JSONResponse:
    """Get job status by request_id."""
    try:
        logger.debug(f"Status poll for job {request_id}")

        state = await service.get_job_status(request_id)

        if state is None:
            logger.warning(f"Job {request_id} not found")
            return json_error_response(
                message="Job not found",
                status_code=404,
                errors={
                    "request_id": f"Job {request_id} does not exist or has expired"
                },
            )

        status = state.get("status", "PROCESSING")

        # Build response based on status
        if status == "COMPLETED":
            data = TranscriptionData(
                request_id=request_id,
                status=JobStatus.COMPLETED,
                transcription=state.get("transcription", ""),
                duration=state.get("duration", 0.0),
                confidence=state.get("confidence", 0.0),
                processing_time=state.get("processing_time", 0.0),
            )
            return JSONResponse(
                status_code=200,
                content=success_response(
                    message="Transcription completed",
                    data=data.model_dump(),
                ),
            )

        elif status == "FAILED":
            data = FailedJobData(
                request_id=request_id,
                status=JobStatus.FAILED,
                error=state.get("error", "Unknown error"),
            )
            return JSONResponse(
                status_code=200,
                content=success_response(
                    message="Transcription failed",
                    data=data.model_dump(),
                ),
            )

        else:  # PROCESSING
            data = AsyncJobData(
                request_id=request_id,
                status=JobStatus.PROCESSING,
            )
            return JSONResponse(
                status_code=200,
                content=success_response(
                    message="Transcription in progress",
                    data=data.model_dump(),
                ),
            )

    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        return json_error_response(
            message="Internal server error",
            status_code=500,
            errors={"detail": str(e)},
        )
