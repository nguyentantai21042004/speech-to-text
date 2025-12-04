"""
Async Transcription Service - Background job processing with Redis state management.

Handles async transcription jobs:
1. Submit job → Set PROCESSING state in Redis → Return immediately
2. Background task → Download + Transcribe → Update Redis to COMPLETED/FAILED
3. Polling endpoint → Read state from Redis
"""

import time
from typing import Dict, Any, Optional

from core.config import get_settings
from core.logger import logger
from infrastructure.redis import get_redis_client
from services.transcription import TranscribeService


class AsyncTranscriptionService:
    """
    Service for async transcription with Redis-backed job state management.

    Uses TranscribeService for actual transcription work.
    """

    def __init__(self, transcribe_service: Optional[TranscribeService] = None):
        """
        Initialize AsyncTranscriptionService.

        Args:
            transcribe_service: TranscribeService instance (will create default if None)
        """
        self.transcribe_service = transcribe_service or TranscribeService()
        self.redis_client = get_redis_client()
        self.settings = get_settings()

        logger.info("AsyncTranscriptionService initialized")

    async def submit_job(
        self, request_id: str, media_url: str, language: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Submit async transcription job.

        Checks for idempotency (if job exists, return existing status).
        Sets PROCESSING state in Redis and returns immediately.

        Args:
            request_id: Client-provided unique ID
            media_url: URL to audio/video file
            language: Language hint (default: vi)

        Returns:
            Dict with request_id and status
        """
        # Check if job already exists (idempotency)
        existing_state = await self.redis_client.get_job_state(request_id)
        if existing_state:
            logger.info(
                f"Job {request_id} already exists with status: {existing_state.get('status')}"
            )
            return {
                "request_id": request_id,
                "status": existing_state.get("status", "PROCESSING"),
                "message": f"Job already exists with status: {existing_state.get('status')}",
            }

        # Set initial PROCESSING state
        initial_state = {
            "status": "PROCESSING",
            "media_url": media_url,
            "language": language or "vi",
            "submitted_at": time.time(),
        }

        success = await self.redis_client.set_job_state(request_id, initial_state)
        if not success:
            raise RuntimeError("Failed to set initial job state in Redis")

        logger.info(f"Job {request_id} submitted successfully")

        return {
            "request_id": request_id,
            "status": "PROCESSING",
            "message": "Job submitted successfully",
        }

    async def get_job_status(self, request_id: str) -> Optional[Dict[str, Any]]:
        """
        Get job status from Redis.

        Args:
            request_id: Job ID to query

        Returns:
            Job state dict if exists, None if not found
        """
        state = await self.redis_client.get_job_state(request_id)

        if state is None:
            logger.debug(f"Job {request_id} not found")
            return None

        logger.debug(f"Job {request_id} status: {state.get('status')}")
        return state

    async def process_job_background(
        self, request_id: str, media_url: str, language: Optional[str] = None
    ):
        """
        Background task to process transcription job.

        This runs in the background after submit_job returns.
        Updates Redis state to COMPLETED or FAILED.

        Args:
            request_id: Job ID
            media_url: URL to audio/video file
            language: Language hint
        """
        logger.info(f"Background processing started for job {request_id}")
        start_time = time.time()

        try:
            # Perform transcription using TranscribeService
            result = await self.transcribe_service.transcribe_from_url(
                audio_url=media_url,
                language=language or "vi",
            )

            processing_time = time.time() - start_time

            # Update Redis with COMPLETED state
            completed_state = {
                "status": "COMPLETED",
                "transcription": result["text"],
                "duration": result.get("audio_duration", 0.0),
                "confidence": result.get("confidence", 0.98),
                "processing_time": processing_time,
                "completed_at": time.time(),
            }

            await self.redis_client.set_job_state(request_id, completed_state)

            logger.info(
                f"Job {request_id} completed successfully in {processing_time:.2f}s"
            )

        except Exception as e:
            processing_time = time.time() - start_time
            error_msg = str(e)

            logger.error(
                f"Job {request_id} failed after {processing_time:.2f}s: {error_msg}"
            )

            # Update Redis with FAILED state
            failed_state = {
                "status": "FAILED",
                "error": error_msg,
                "processing_time": processing_time,
                "failed_at": time.time(),
            }

            await self.redis_client.set_job_state(request_id, failed_state)


# Global singleton
_async_transcription_service: Optional[AsyncTranscriptionService] = None


def get_async_transcription_service() -> AsyncTranscriptionService:
    """Get or create AsyncTranscriptionService singleton."""
    global _async_transcription_service
    if _async_transcription_service is None:
        logger.info("Creating AsyncTranscriptionService instance...")
        _async_transcription_service = AsyncTranscriptionService()
    return _async_transcription_service
