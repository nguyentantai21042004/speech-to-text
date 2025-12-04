"""
Common API schemas shared across different endpoints.

Unified response format:
{
    "error_code": int,      # 0 = success, 1+ = error
    "message": str,         # Human-readable message
    "data": Any,            # Response data (omit if empty)
    "errors": Any           # Validation/error details (omit if none)
}
"""

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job status enum for async transcription."""

    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class StandardResponse(BaseModel):
    """
    Unified API response format for all endpoints.

    - error_code: 0 = success, 1+ = error
    - message: Human-readable message
    - data: Response data (omit if empty)
    - errors: Validation/error details (omit if none)
    """

    error_code: int = Field(default=0, description="0 = success, 1+ = error")
    message: str = Field(..., description="Human-readable message")
    data: Optional[Any] = Field(default=None, description="Response data")
    errors: Optional[Any] = Field(default=None, description="Error details")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "error_code": 0,
                    "message": "Job submitted successfully",
                    "data": {"request_id": "123", "status": "PROCESSING"},
                },
                {
                    "error_code": 1,
                    "message": "Validation error",
                    "errors": {"media_url": "Invalid URL format"},
                },
            ]
        }


# ============================================================================
# Data Models (for wrapping in StandardResponse.data)
# ============================================================================


class AsyncJobData(BaseModel):
    """Data model for async job submission response."""

    request_id: str = Field(..., description="Job ID for polling")
    status: JobStatus = Field(..., description="Job status")


class TranscriptionData(BaseModel):
    """Data model for completed transcription."""

    request_id: Optional[str] = Field(default=None, description="Job ID (async only)")
    status: Optional[JobStatus] = Field(
        default=None, description="Job status (async only)"
    )
    transcription: str = Field(default="", description="Transcribed text")
    duration: float = Field(default=0.0, description="Audio duration in seconds")
    confidence: float = Field(default=0.0, description="Confidence score (0.0-1.0)")
    processing_time: float = Field(
        default=0.0, description="Processing time in seconds"
    )


class FailedJobData(BaseModel):
    """Data model for failed job."""

    request_id: str = Field(..., description="Job ID")
    status: JobStatus = Field(default=JobStatus.FAILED, description="Job status")
    error: str = Field(..., description="Error message")


class HealthData(BaseModel):
    """Data model for health check response."""

    status: str = Field(..., description="Health status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
    model: Optional[dict] = Field(default=None, description="Model info")
    redis: Optional[dict] = Field(default=None, description="Redis info")


# ============================================================================
# Legacy schemas (deprecated, kept for backward compatibility)
# ============================================================================


class HealthResponse(BaseModel):
    """Response model for health check (deprecated - use HealthData)."""

    status: str
    service: str
    version: str

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "status": "healthy",
                    "service": "Speech-to-Text API",
                    "version": "1.0.0",
                }
            ]
        }
