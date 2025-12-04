"""
Schemas for async transcription API with polling pattern.

Based on design spec:
- Client submits job with request_id
- POST returns 202 Accepted immediately
- GET allows polling for job status
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class JobStatus(str, Enum):
    """Job status enum for async transcription."""

    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AsyncTranscribeRequest(BaseModel):
    """
    Request model for async transcription job submission.

    Client provides request_id (e.g., post_id from Crawler) for idempotency.
    """

    request_id: str = Field(
        ...,
        description="Client-generated unique request ID (e.g., post_id from Crawler)",
        min_length=1,
        max_length=256,
    )
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

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, v: str) -> str:
        """Validate request_id is not empty and has reasonable length."""
        if not v or not v.strip():
            raise ValueError("request_id cannot be empty")
        return v.strip()


class AsyncTranscribeSubmitResponse(BaseModel):
    """
    Response for job submission (POST /api/v1/transcribe).

    Returns 202 Accepted with request_id for polling.
    """

    request_id: str = Field(..., description="Job ID for polling status")
    status: JobStatus = Field(..., description="Initial job status (PROCESSING)")
    message: str = Field(default="Job submitted successfully")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "request_id": "post_123456",
                    "status": "PROCESSING",
                    "message": "Job submitted successfully",
                }
            ]
        }


class AsyncTranscribeStatusResponse(BaseModel):
    """
    Response for job status polling (GET /api/v1/transcribe/{request_id}).

    Status can be:
    - PROCESSING: Job is still running
    - COMPLETED: Job finished successfully (includes transcription data)
    - FAILED: Job failed (includes error message)
    """

    request_id: str = Field(..., description="Job ID")
    status: JobStatus = Field(..., description="Current job status")
    message: str = Field(..., description="Human-readable status message")

    # Fields present only when status = COMPLETED
    transcription: Optional[str] = Field(
        default=None, description="Transcribed text (only present when COMPLETED)"
    )
    duration: Optional[float] = Field(
        default=None,
        description="Audio duration in seconds (only present when COMPLETED)",
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Confidence score 0.0-1.0 (only present when COMPLETED)",
    )
    processing_time: Optional[float] = Field(
        default=None,
        description="Processing time in seconds (only present when COMPLETED)",
    )

    # Field present only when status = FAILED
    error: Optional[str] = Field(
        default=None, description="Error message (only present when FAILED)"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "request_id": "post_123456",
                    "status": "PROCESSING",
                    "message": "Transcription in progress",
                },
                {
                    "request_id": "post_123456",
                    "status": "COMPLETED",
                    "message": "Transcription completed successfully",
                    "transcription": "Xin chào, đây là video test...",
                    "duration": 45.5,
                    "confidence": 0.98,
                    "processing_time": 12.3,
                },
                {
                    "request_id": "post_123456",
                    "status": "FAILED",
                    "message": "Transcription failed",
                    "error": "Failed to download audio file: Connection timeout",
                },
            ]
        }
