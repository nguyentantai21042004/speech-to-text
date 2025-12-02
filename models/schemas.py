"""
Pydantic Schemas - Request/Response DTOs for the API.

This module consolidates all Pydantic models used across the application.
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, Any


# =============================================================================
# Common Response Schemas
# =============================================================================


class StandardResponse(BaseModel):
    """
    Standard API response format for all endpoints.

    - error_code: 0 = success, 1 = error
    - message: Success or error message
    - data: Response data (optional, only present on success)
    """

    error_code: int = 0
    message: str
    data: Optional[Any] = None

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "error_code": 0,
                    "message": "Success",
                    "data": {"text": "Transcribed content here"},
                },
                {"error_code": 1, "message": "Transcription failed", "data": None},
            ]
        }


class HealthResponse(BaseModel):
    """Response model for health check endpoint."""

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


# =============================================================================
# Transcription Schemas
# =============================================================================


class TranscribeRequest(BaseModel):
    """Request model for transcription endpoint."""

    media_url: str = Field(
        ...,
        description="URL of the audio/video file to transcribe",
        examples=["https://example.com/audio.mp3"],
    )
    language: Optional[str] = Field(
        default=None,
        description="Language code for transcription (e.g., 'vi', 'en'). Defaults to configured language.",
        examples=["vi", "en"],
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "media_url": "https://example.com/audio.mp3",
                    "language": "vi",
                }
            ]
        }


class TranscriptionResult(BaseModel):
    """Detailed transcription result with metadata."""

    text: str = Field(..., description="Transcribed text content")
    duration: float = Field(..., description="Transcription processing time in seconds")
    download_duration: float = Field(..., description="Audio download time in seconds")
    file_size_mb: float = Field(..., description="Downloaded file size in MB")
    model: str = Field(..., description="Whisper model used for transcription")
    language: str = Field(..., description="Language used for transcription")
    audio_duration: float = Field(default=0.0, description="Audio duration in seconds")

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "text": "Xin chào, đây là bản ghi âm thử nghiệm.",
                    "duration": 2.5,
                    "download_duration": 1.2,
                    "file_size_mb": 5.3,
                    "model": "ggml-base-q5_1.bin",
                    "language": "vi",
                    "audio_duration": 30.5,
                }
            ]
        }


class TranscribeResponse(BaseModel):
    """Response model for transcription endpoint."""

    error_code: int = Field(default=0, description="0 = success, 1 = error")
    message: str = Field(..., description="Success or error message")
    data: Optional[TranscriptionResult] = Field(
        default=None, description="Transcription result (only on success)"
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "error_code": 0,
                    "message": "Transcription successful",
                    "data": {
                        "text": "Xin chào, đây là bản ghi âm thử nghiệm.",
                        "duration": 2.5,
                        "download_duration": 1.2,
                        "file_size_mb": 5.3,
                        "model": "ggml-base-q5_1.bin",
                        "language": "vi",
                        "audio_duration": 30.5,
                    },
                }
            ]
        }
