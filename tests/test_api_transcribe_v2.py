"""
Tests for transcription API v2 with authentication.
These tests mock the TranscribeService to avoid needing Whisper libraries.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
import sys
from pathlib import Path

# Get project root (parent of tests directory)
PROJECT_ROOT = Path(__file__).parent.parent

# Add project root to sys.path for imports
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Test constants
VALID_API_KEY = "your-api-key-here"
INVALID_API_KEY = "wrong-key"
TEST_MEDIA_URL = "https://minio.internal/bucket/audio_123.mp3?token=xyz"


@pytest.fixture
def mock_transcribe_service():
    """Create a mock TranscribeService."""
    mock_service = MagicMock()
    mock_service.transcribe_from_url = AsyncMock()
    return mock_service


@pytest.fixture
def client_no_auth(mock_transcribe_service):
    """Create test client WITHOUT auth override (to test auth)."""
    from fastapi import FastAPI
    from internal.api.routes.transcribe_routes import router as transcribe_router

    app = FastAPI()
    app.include_router(transcribe_router)

    # Override only the service dependency, NOT auth
    from core.dependencies import get_transcribe_service_dependency

    app.dependency_overrides[get_transcribe_service_dependency] = (
        lambda: mock_transcribe_service
    )

    return TestClient(app)


@pytest.fixture
def client_with_auth(mock_transcribe_service):
    """Create test client WITH auth override."""
    from fastapi import FastAPI
    from internal.api.routes.transcribe_routes import router as transcribe_router

    app = FastAPI()
    app.include_router(transcribe_router)

    from core.dependencies import get_transcribe_service_dependency
    from internal.api.dependencies.auth import verify_internal_api_key

    app.dependency_overrides[get_transcribe_service_dependency] = (
        lambda: mock_transcribe_service
    )
    app.dependency_overrides[verify_internal_api_key] = lambda: "test-api-key"

    return TestClient(app)


class TestTranscribeV2Authentication:
    """Test authentication for /transcribe endpoint."""

    def test_missing_api_key(self, client_no_auth):
        """Should return 401 when API key is missing."""
        response = client_no_auth.post(
            "/transcribe",
            json={"media_url": TEST_MEDIA_URL, "language": "vi"},
        )
        assert response.status_code == 401
        data = response.json()
        # Auth dependency might return simple dict or unified error.
        # Assuming unified error from exception handler or simple detail from FastAPI
        detail = data.get("detail") or data.get("message")
        assert "Missing API key" in detail

    def test_invalid_api_key(self, client_no_auth):
        """Should return 401 when API key is invalid."""
        response = client_no_auth.post(
            "/transcribe",
            json={"media_url": TEST_MEDIA_URL, "language": "vi"},
            headers={"X-API-Key": INVALID_API_KEY},
        )
        assert response.status_code == 401

    def test_valid_api_key_success(self, client_with_auth, mock_transcribe_service):
        """Should succeed with valid API key."""
        mock_transcribe_service.transcribe_from_url.return_value = {
            "text": "Test transcription",
            "duration": 2.5,
            "audio_duration": 45.5,
            "confidence": 0.98,
            "download_duration": 1.0,
            "file_size_mb": 5.2,
            "model": "small",
            "language": "vi",
        }

        response = client_with_auth.post(
            "/transcribe",
            json={"media_url": TEST_MEDIA_URL, "language": "vi"},
            headers={"X-API-Key": VALID_API_KEY},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["error_code"] == 0
        assert data["message"] == "Transcription successful"
        assert data["data"]["transcription"] == "Test transcription"


class TestTranscribeV2RequestValidation:
    """Test request validation for /transcribe endpoint."""

    def test_missing_media_url(self, client_with_auth):
        """Should return 422 when media_url is missing."""
        response = client_with_auth.post(
            "/transcribe",
            json={"language": "vi"},
            headers={"X-API-Key": VALID_API_KEY},
        )
        assert response.status_code == 422

    def test_invalid_media_url_format(self, client_with_auth):
        """Should return 422 when media_url is not a valid URL."""
        response = client_with_auth.post(
            "/transcribe",
            json={"media_url": "not-a-url", "language": "vi"},
            headers={"X-API-Key": VALID_API_KEY},
        )
        assert response.status_code == 422

    def test_optional_language_parameter(
        self, client_with_auth, mock_transcribe_service
    ):
        """Should use default language when not provided."""
        mock_transcribe_service.transcribe_from_url.return_value = {
            "text": "Test",
            "duration": 1.0,
            "audio_duration": 10.0,
            "confidence": 0.95,
        }

        response = client_with_auth.post(
            "/transcribe",
            json={"media_url": TEST_MEDIA_URL},
            headers={"X-API-Key": VALID_API_KEY},
        )
        assert response.status_code == 200
        mock_transcribe_service.transcribe_from_url.assert_called_once()


class TestTranscribeV2ResponseFormat:
    """Test response format for /transcribe endpoint."""

    def test_success_response_structure(
        self, client_with_auth, mock_transcribe_service
    ):
        """Should return proper response structure on success."""
        mock_transcribe_service.transcribe_from_url.return_value = {
            "text": "Nội dung video nói về xe VinFast VF3",
            "duration": 2.1,
            "audio_duration": 45.5,
            "confidence": 0.98,
        }

        response = client_with_auth.post(
            "/transcribe",
            json={"media_url": TEST_MEDIA_URL, "language": "vi"},
            headers={"X-API-Key": VALID_API_KEY},
        )
        assert response.status_code == 200
        data = response.json()

        # Verify unified format fields
        assert "error_code" in data
        assert "message" in data
        assert "data" in data

        # Verify values
        assert data["error_code"] == 0
        assert data["message"] == "Transcription successful"

        # Verify data payload
        payload = data["data"]
        assert "transcription" in payload
        assert "duration" in payload
        assert "confidence" in payload
        assert "processing_time" in payload
        assert payload["transcription"] == "Nội dung video nói về xe VinFast VF3"


class TestTranscribeV2ErrorHandling:
    """Test error handling for /transcribe endpoint."""

    def test_timeout_error(self, client_with_auth, mock_transcribe_service):
        """Should return timeout status when processing exceeds limit."""
        import asyncio

        mock_transcribe_service.transcribe_from_url.side_effect = asyncio.TimeoutError()

        response = client_with_auth.post(
            "/transcribe",
            json={"media_url": TEST_MEDIA_URL, "language": "vi"},
            headers={"X-API-Key": VALID_API_KEY},
        )
        assert response.status_code == 408
        data = response.json()
        assert data["error_code"] == 1
        assert "timeout" in data["message"].lower()

    def test_file_too_large_error(self, client_with_auth, mock_transcribe_service):
        """Should return 413 when file exceeds size limit."""
        mock_transcribe_service.transcribe_from_url.side_effect = ValueError(
            "File too large: 600MB > 500MB"
        )

        response = client_with_auth.post(
            "/transcribe",
            json={"media_url": TEST_MEDIA_URL, "language": "vi"},
            headers={"X-API-Key": VALID_API_KEY},
        )
        assert response.status_code == 413
        data = response.json()
        assert "too large" in data["errors"]["detail"]

    def test_invalid_url_error(self, client_with_auth, mock_transcribe_service):
        """Should return 400 when URL cannot be fetched."""
        mock_transcribe_service.transcribe_from_url.side_effect = ValueError(
            "Failed to download file: HTTP 404"
        )

        response = client_with_auth.post(
            "/transcribe",
            json={"media_url": TEST_MEDIA_URL, "language": "vi"},
            headers={"X-API-Key": VALID_API_KEY},
        )
        assert response.status_code == 400
        data = response.json()
        assert "Failed to download" in data["errors"]["detail"]

    def test_internal_server_error(self, client_with_auth, mock_transcribe_service):
        """Should return 500 on unexpected errors."""
        mock_transcribe_service.transcribe_from_url.side_effect = Exception(
            "Unexpected error"
        )

        response = client_with_auth.post(
            "/transcribe",
            json={"media_url": TEST_MEDIA_URL, "language": "vi"},
            headers={"X-API-Key": VALID_API_KEY},
        )
        assert response.status_code == 500
        data = response.json()
        assert "Unexpected error" in data["errors"]["detail"]
