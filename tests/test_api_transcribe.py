"""
Tests for transcription API endpoints.
These tests mock the TranscribeService to avoid needing Whisper libraries.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import importlib.util
import sys
from pathlib import Path

# Get project root (parent of tests directory)
PROJECT_ROOT = Path(__file__).parent.parent

# Add project root to sys.path for imports
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def mock_transcribe_service():
    """Create a mock TranscribeService."""
    mock_service = MagicMock()
    mock_service.transcribe_from_url = AsyncMock()
    return mock_service


@pytest.fixture
def client(mock_transcribe_service):
    """Create test client with mocked dependencies."""
    # Import after adding to path
    from fastapi import FastAPI
    from internal.api.routes.transcribe_routes import router as transcribe_router
    from internal.api.routes.health_routes import create_health_routes

    # Create a test app
    app = FastAPI()
    app.include_router(transcribe_router)

    # Override the dependency
    from core.dependencies import get_transcribe_service_dependency

    app.dependency_overrides[get_transcribe_service_dependency] = (
        lambda: mock_transcribe_service
    )

    # Also override auth dependency to always pass
    from internal.api.dependencies.auth import verify_internal_api_key

    app.dependency_overrides[verify_internal_api_key] = lambda: "test-api-key"

    return TestClient(app)


def test_transcribe_endpoint_success(client, mock_transcribe_service):
    """Test successful transcription."""
    mock_result = {
        "text": "Hello World",
        "duration": 1.5,
        "audio_duration": 30.0,
        "confidence": 0.98,
        "download_duration": 0.5,
        "file_size_mb": 1.0,
        "model": "small",
    }
    mock_transcribe_service.transcribe_from_url.return_value = mock_result

    response = client.post(
        "/transcribe",
        json={"media_url": "http://example.com/audio.mp3"},
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["transcription"] == "Hello World"


def test_transcribe_endpoint_too_large(client, mock_transcribe_service):
    """Test file too large error."""
    mock_transcribe_service.transcribe_from_url.side_effect = ValueError(
        "File too large: 600MB > 500MB"
    )

    response = client.post(
        "/transcribe",
        json={"media_url": "http://example.com/large.mp3"},
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 413
    assert "too large" in response.json()["detail"]


def test_transcribe_endpoint_error(client, mock_transcribe_service):
    """Test internal server error."""
    mock_transcribe_service.transcribe_from_url.side_effect = Exception(
        "Internal error"
    )

    response = client.post(
        "/transcribe",
        json={"media_url": "http://example.com/error.mp3"},
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 500
    assert "Internal server error" in response.json()["detail"]


def test_transcribe_endpoint_timeout(client, mock_transcribe_service):
    """Test timeout handling."""
    import asyncio

    mock_transcribe_service.transcribe_from_url.side_effect = asyncio.TimeoutError()

    response = client.post(
        "/transcribe",
        json={"media_url": "http://example.com/slow.mp3"},
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "timeout"
    assert data["transcription"] == ""


def test_transcribe_endpoint_invalid_url(client, mock_transcribe_service):
    """Test invalid URL error."""
    mock_transcribe_service.transcribe_from_url.side_effect = ValueError(
        "Failed to download file: HTTP 404"
    )

    response = client.post(
        "/transcribe",
        json={"media_url": "http://example.com/notfound.mp3"},
        headers={"X-API-Key": "test-key"},
    )

    assert response.status_code == 400
    assert "Failed to download" in response.json()["detail"]
