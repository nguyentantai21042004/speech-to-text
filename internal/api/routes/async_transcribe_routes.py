"""
Async Transcription Routes - API endpoints for async transcription with polling pattern.

Endpoints:
- POST /api/v1/transcribe - Submit job (returns 202 Accepted)
- GET /api/v1/transcribe/{request_id} - Poll job status
"""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse

from core.logger import logger
from internal.api.dependencies.auth import verify_internal_api_key
from internal.api.schemas.async_transcribe_schemas import (
    AsyncTranscribeRequest,
    AsyncTranscribeSubmitResponse,
    AsyncTranscribeStatusResponse,
    JobStatus,
)
from services.async_transcription import (
    get_async_transcription_service,
    AsyncTranscriptionService,
)

router = APIRouter(prefix="/api/v1", tags=["Async Transcription"])


@router.post(
    "/transcribe",
    response_model=AsyncTranscribeSubmitResponse,
    status_code=202,
    summary="Submit async transcription job",
    description="""
Submit an async transcription job with client-provided request_id.

**Authentication**: Requires `X-API-Key` header.

**Idempotency**: If a job with the same request_id already exists, returns the existing job status.

**Response**: Returns 202 Accepted immediately with request_id for polling.

**Flow**:
1. Submit job with request_id (e.g., post_id)
2. Job is queued for background processing
3. Poll GET /api/v1/transcribe/{request_id} to check status

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/transcribe \\
  -H "X-API-Key: your-api-key" \\
  -H "Content-Type: application/json" \\
  -d '{
    "request_id": "post_123456",
    "media_url": "minio://bucket/audio.mp3",
    "language": "vi"
  }'
```
""",
    responses={
        202: {"description": "Job submitted successfully"},
        400: {"description": "Bad request (invalid URL or request_id)"},
        401: {"description": "Unauthorized (missing/invalid API key)"},
        500: {"description": "Internal server error"},
    },
)
async def submit_transcription_job(
    request: AsyncTranscribeRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_internal_api_key),
    service: AsyncTranscriptionService = Depends(get_async_transcription_service),
) -> AsyncTranscribeSubmitResponse:
    """
    Submit async transcription job.

    Returns 202 Accepted immediately, job processes in background.
    """
    try:
        logger.info(
            f"Async job submission: request_id={request.request_id}, language={request.language}"
        )

        # Submit job (sets PROCESSING state in Redis)
        result = await service.submit_job(
            request_id=request.request_id,
            media_url=request.media_url,
            language=request.language,
        )

        # Add background task to process transcription
        # Only add if this is a new job (status is PROCESSING and message is "Job submitted successfully")
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

        return AsyncTranscribeSubmitResponse(
            request_id=result["request_id"],
            status=JobStatus(result["status"]),
            message=result["message"],
        )

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Failed to submit job: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get(
    "/transcribe/{request_id}",
    response_model=AsyncTranscribeStatusResponse,
    summary="Poll job status",
    description="""
Poll the status of an async transcription job.

**Authentication**: Requires `X-API-Key` header.

**Job States**:
- `PROCESSING`: Job is still running (keep polling)
- `COMPLETED`: Job finished successfully (includes transcription data)
- `FAILED`: Job failed (includes error message)

**Polling Strategy**:
- Poll every 2-5 seconds until status is COMPLETED or FAILED
- Jobs expire after 1 hour (TTL in Redis)

**Example**:
```bash
curl -X GET http://localhost:8000/api/v1/transcribe/post_123456 \\
  -H "X-API-Key: your-api-key"
```
""",
    responses={
        200: {"description": "Job status returned"},
        401: {"description": "Unauthorized (missing/invalid API key)"},
        404: {"description": "Job not found"},
        500: {"description": "Internal server error"},
    },
)
async def get_transcription_status(
    request_id: str,
    api_key: str = Depends(verify_internal_api_key),
    service: AsyncTranscriptionService = Depends(get_async_transcription_service),
) -> AsyncTranscribeStatusResponse:
    """
    Get job status by request_id.

    Returns current job state from Redis.
    """
    try:
        logger.debug(f"Status poll for job {request_id}")

        state = await service.get_job_status(request_id)

        if state is None:
            logger.warning(f"Job {request_id} not found")
            raise HTTPException(
                status_code=404,
                detail=f"Job not found: {request_id}",
            )

        status = state.get("status", "PROCESSING")

        # Build response based on status
        if status == "COMPLETED":
            return AsyncTranscribeStatusResponse(
                request_id=request_id,
                status=JobStatus.COMPLETED,
                message="Transcription completed successfully",
                transcription=state.get("transcription"),
                duration=state.get("duration"),
                confidence=state.get("confidence"),
                processing_time=state.get("processing_time"),
            )

        elif status == "FAILED":
            return AsyncTranscribeStatusResponse(
                request_id=request_id,
                status=JobStatus.FAILED,
                message="Transcription failed",
                error=state.get("error"),
            )

        else:  # PROCESSING
            return AsyncTranscribeStatusResponse(
                request_id=request_id,
                status=JobStatus.PROCESSING,
                message="Transcription in progress",
            )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Failed to get job status: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
