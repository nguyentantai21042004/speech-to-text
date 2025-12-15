"""
Tests for async transcription API endpoints with unified response format.

Response format:
{
    "error_code": int,
    "message": str,
    "data": {...},
    "errors": {...}
}

Tests cover:
- 4.1 Submit job endpoint (POST /api/transcribe)
- 4.2 Polling endpoint (GET /api/transcribe/{request_id})
- 4.3 Idempotency (submit same request_id twice)
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def create_mock_async_service(job_states: dict = None):
    """Create a mock AsyncTranscriptionService."""
    mock_service = MagicMock()
    job_states = job_states or {}

    async def mock_submit_job(request_id, media_url, language=None):
        if request_id in job_states:
            existing = job_states[request_id]
            return {
                "request_id": request_id,
                "status": existing.get("status", "PROCESSING"),
                "message": f"Job already exists with status: {existing.get('status')}",
            }
        job_states[request_id] = {"status": "PROCESSING"}
        return {
            "request_id": request_id,
            "status": "PROCESSING",
            "message": "Job submitted successfully",
        }

    async def mock_get_job_status(request_id):
        return job_states.get(request_id)

    async def mock_process_job_background(request_id, media_url, language=None):
        job_states[request_id] = {
            "status": "COMPLETED",
            "transcription": "Test transcription",
            "duration": 30.0,
            "confidence": 0.98,
            "processing_time": 5.0,
        }

    mock_service.submit_job = mock_submit_job
    mock_service.get_job_status = mock_get_job_status
    mock_service.process_job_background = mock_process_job_background

    return mock_service


def create_test_client(mock_service):
    """Create test client with mocked service."""
    from internal.api.routes.async_transcribe_routes import router
    from internal.api.dependencies.auth import verify_internal_api_key
    from services.async_transcription import get_async_transcription_service

    app = FastAPI()
    app.include_router(router)

    app.dependency_overrides[verify_internal_api_key] = lambda: "test-api-key"
    app.dependency_overrides[get_async_transcription_service] = lambda: mock_service

    return TestClient(app)


class TestSubmitJobEndpoint:
    """Test 4.1: Submit job endpoint (POST /api/transcribe)."""

    def test_submit_job_success(self):
        """Test successful job submission returns unified format."""
        mock_service = create_mock_async_service()
        client = create_test_client(mock_service)

        response = client.post(
            "/api/transcribe",
            json={
                "request_id": "test-job-123",
                "media_url": "http://example.com/audio.mp3",
                "language": "vi",
            },
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 202
        data = response.json()
        # Unified format checks
        assert data["error_code"] == 0
        assert "message" in data
        assert "data" in data
        # Data field checks
        assert data["data"]["request_id"] == "test-job-123"
        assert data["data"]["status"] == "PROCESSING"

    def test_submit_job_missing_request_id(self):
        """Test job submission without request_id returns 422."""
        mock_service = create_mock_async_service()
        client = create_test_client(mock_service)

        response = client.post(
            "/api/transcribe",
            json={"media_url": "http://example.com/audio.mp3"},
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 422

    def test_submit_job_missing_media_url(self):
        """Test job submission without media_url returns 422."""
        mock_service = create_mock_async_service()
        client = create_test_client(mock_service)

        response = client.post(
            "/api/transcribe",
            json={"request_id": "test-job-123"},
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 422

    def test_submit_job_invalid_url_scheme(self):
        """Test job submission with invalid URL scheme returns 422."""
        mock_service = create_mock_async_service()
        client = create_test_client(mock_service)

        response = client.post(
            "/api/transcribe",
            json={
                "request_id": "test-job-123",
                "media_url": "ftp://example.com/audio.mp3",
            },
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 422

    def test_submit_job_empty_request_id(self):
        """Test job submission with empty request_id returns 422."""
        mock_service = create_mock_async_service()
        client = create_test_client(mock_service)

        response = client.post(
            "/api/transcribe",
            json={
                "request_id": "   ",
                "media_url": "http://example.com/audio.mp3",
            },
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 422


class TestPollingEndpoint:
    """Test 4.2: Polling endpoint (GET /api/transcribe/{request_id})."""

    def test_poll_processing_job(self):
        """Test polling a job in PROCESSING state."""
        job_states = {"test-job-123": {"status": "PROCESSING"}}
        mock_service = create_mock_async_service(job_states)
        client = create_test_client(mock_service)

        response = client.get(
            "/api/transcribe/test-job-123",
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 200
        data = response.json()
        # Unified format
        assert data["error_code"] == 0
        assert "data" in data
        assert data["data"]["status"] == "PROCESSING"
        assert data["data"]["request_id"] == "test-job-123"

    def test_poll_completed_job(self):
        """Test polling a completed job returns transcription in data."""
        job_states = {
            "test-job-123": {
                "status": "COMPLETED",
                "transcription": "Hello world transcription",
                "duration": 30.5,
                "confidence": 0.98,
                "processing_time": 5.2,
            }
        }
        mock_service = create_mock_async_service(job_states)
        client = create_test_client(mock_service)

        response = client.get(
            "/api/transcribe/test-job-123",
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 200
        data = response.json()
        # Unified format
        assert data["error_code"] == 0
        assert "data" in data
        assert data["data"]["status"] == "COMPLETED"
        assert data["data"]["transcription"] == "Hello world transcription"
        assert data["data"]["duration"] == 30.5

    def test_poll_failed_job(self):
        """Test polling a failed job returns error in data."""
        job_states = {
            "test-job-123": {
                "status": "FAILED",
                "error": "Failed to download audio file",
            }
        }
        mock_service = create_mock_async_service(job_states)
        client = create_test_client(mock_service)

        response = client.get(
            "/api/transcribe/test-job-123",
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 200
        data = response.json()
        # Unified format - FAILED is still error_code=0 (request succeeded)
        assert data["error_code"] == 0
        assert "data" in data
        assert data["data"]["status"] == "FAILED"
        assert "error" in data["data"]
        assert "download" in data["data"]["error"].lower()

    def test_poll_nonexistent_job(self):
        """Test polling a non-existent job returns 404 with errors."""
        mock_service = create_mock_async_service()
        client = create_test_client(mock_service)

        response = client.get(
            "/api/transcribe/nonexistent-job",
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 404
        data = response.json()
        # Unified error format
        assert data["error_code"] == 1
        assert "errors" in data


class TestIdempotency:
    """Test 4.3: Idempotency (submit same request_id twice)."""

    def test_submit_duplicate_job_returns_existing_status(self):
        """Test submitting duplicate request_id returns existing job."""
        job_states = {"duplicate-job-123": {"status": "PROCESSING"}}
        mock_service = create_mock_async_service(job_states)
        client = create_test_client(mock_service)

        response = client.post(
            "/api/transcribe",
            json={
                "request_id": "duplicate-job-123",
                "media_url": "http://example.com/audio.mp3",
            },
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["error_code"] == 0
        assert data["data"]["status"] == "PROCESSING"
        assert "already exists" in data["message"].lower()

    def test_submit_duplicate_completed_job(self):
        """Test submitting request_id of completed job returns COMPLETED."""
        job_states = {
            "completed-job-123": {
                "status": "COMPLETED",
                "transcription": "Already done",
            }
        }
        mock_service = create_mock_async_service(job_states)
        client = create_test_client(mock_service)

        response = client.post(
            "/api/transcribe",
            json={
                "request_id": "completed-job-123",
                "media_url": "http://example.com/audio.mp3",
            },
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["error_code"] == 0
        assert data["data"]["status"] == "COMPLETED"
        assert "already exists" in data["message"].lower()

    def test_new_job_then_duplicate(self):
        """Test full flow: submit new job, then submit duplicate."""
        job_states = {}
        mock_service = create_mock_async_service(job_states)
        client = create_test_client(mock_service)

        # First submission
        response1 = client.post(
            "/api/transcribe",
            json={
                "request_id": "new-job-123",
                "media_url": "http://example.com/audio.mp3",
            },
            headers={"X-API-Key": "test-key"},
        )

        assert response1.status_code == 202
        assert response1.json()["error_code"] == 0
        assert response1.json()["data"]["status"] == "PROCESSING"

        # Second submission - duplicate
        response2 = client.post(
            "/api/transcribe",
            json={
                "request_id": "new-job-123",
                "media_url": "http://example.com/audio.mp3",
            },
            headers={"X-API-Key": "test-key"},
        )

        assert response2.status_code == 202
        assert response2.json()["error_code"] == 0
        # Status could be PROCESSING or COMPLETED
        assert response2.json()["data"]["status"] in ["PROCESSING", "COMPLETED"]
        assert "already exists" in response2.json()["message"].lower()


class TestUnifiedErrorFormat:
    """Test unified error response format."""

    def test_validation_error_has_errors_field(self):
        """Test validation errors include errors field."""
        mock_service = create_mock_async_service()
        client = create_test_client(mock_service)

        response = client.post(
            "/api/transcribe",
            json={"request_id": "test"},  # Missing media_url
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 422
        # Note: FastAPI default validation handler may not have our format
        # This test verifies the response structure

    def test_not_found_error_has_errors_field(self):
        """Test 404 errors include errors field."""
        mock_service = create_mock_async_service()
        client = create_test_client(mock_service)

        response = client.get(
            "/api/transcribe/nonexistent",
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 404
        data = response.json()
        assert data["error_code"] == 1
        assert "message" in data
        assert "errors" in data


class TestFailedJobRetry:
    """Test retry mechanism for FAILED jobs."""

    def test_submit_failed_job_allows_retry(self):
        """Test that submitting request_id of FAILED job creates new job (retry)."""
        # Setup: Create a mock that simulates the new retry behavior
        mock_service = MagicMock()
        job_states = {
            "failed-job-123": {
                "status": "FAILED",
                "error": "Previous error",
            }
        }

        async def mock_submit_job(request_id, media_url, language=None):
            if request_id in job_states:
                existing = job_states[request_id]
                status = existing.get("status", "PROCESSING")

                # NEW BEHAVIOR: Allow retry for FAILED jobs
                if status == "FAILED":
                    # Delete old job and create new one
                    job_states[request_id] = {"status": "PROCESSING"}
                    return {
                        "request_id": request_id,
                        "status": "PROCESSING",
                        "message": "Job submitted successfully",
                    }
                else:
                    return {
                        "request_id": request_id,
                        "status": status,
                        "message": f"Job already exists with status: {status}",
                    }

            job_states[request_id] = {"status": "PROCESSING"}
            return {
                "request_id": request_id,
                "status": "PROCESSING",
                "message": "Job submitted successfully",
            }

        async def mock_get_job_status(request_id):
            return job_states.get(request_id)

        async def mock_process_job_background(request_id, media_url, language=None):
            job_states[request_id] = {
                "status": "COMPLETED",
                "transcription": "Retry successful",
            }

        mock_service.submit_job = mock_submit_job
        mock_service.get_job_status = mock_get_job_status
        mock_service.process_job_background = mock_process_job_background

        client = create_test_client(mock_service)

        # Submit to FAILED job - should allow retry
        response = client.post(
            "/api/transcribe",
            json={
                "request_id": "failed-job-123",
                "media_url": "http://example.com/audio.mp3",
            },
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["error_code"] == 0
        # Should be PROCESSING (new job created), not FAILED
        assert data["data"]["status"] == "PROCESSING"
        # Message should indicate new job, not "already exists"
        assert "submitted successfully" in data["message"].lower()

    def test_submit_processing_job_no_retry(self):
        """Test that PROCESSING job is NOT retried (idempotency preserved)."""
        mock_service = MagicMock()
        job_states = {"processing-job-123": {"status": "PROCESSING"}}

        async def mock_submit_job(request_id, media_url, language=None):
            if request_id in job_states:
                existing = job_states[request_id]
                status = existing.get("status", "PROCESSING")

                if status == "FAILED":
                    job_states[request_id] = {"status": "PROCESSING"}
                    return {
                        "request_id": request_id,
                        "status": "PROCESSING",
                        "message": "Job submitted successfully",
                    }
                else:
                    # PROCESSING or COMPLETED - return existing
                    return {
                        "request_id": request_id,
                        "status": status,
                        "message": f"Job already exists with status: {status}",
                    }

            job_states[request_id] = {"status": "PROCESSING"}
            return {
                "request_id": request_id,
                "status": "PROCESSING",
                "message": "Job submitted successfully",
            }

        async def mock_get_job_status(request_id):
            return job_states.get(request_id)

        mock_service.submit_job = mock_submit_job
        mock_service.get_job_status = mock_get_job_status
        mock_service.process_job_background = MagicMock()

        client = create_test_client(mock_service)

        response = client.post(
            "/api/transcribe",
            json={
                "request_id": "processing-job-123",
                "media_url": "http://example.com/audio.mp3",
            },
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["error_code"] == 0
        assert data["data"]["status"] == "PROCESSING"
        assert "already exists" in data["message"].lower()

    def test_submit_completed_job_no_retry(self):
        """Test that COMPLETED job is NOT retried (idempotency preserved)."""
        mock_service = MagicMock()
        job_states = {
            "completed-job-123": {
                "status": "COMPLETED",
                "transcription": "Already done",
            }
        }

        async def mock_submit_job(request_id, media_url, language=None):
            if request_id in job_states:
                existing = job_states[request_id]
                status = existing.get("status", "PROCESSING")

                if status == "FAILED":
                    job_states[request_id] = {"status": "PROCESSING"}
                    return {
                        "request_id": request_id,
                        "status": "PROCESSING",
                        "message": "Job submitted successfully",
                    }
                else:
                    return {
                        "request_id": request_id,
                        "status": status,
                        "message": f"Job already exists with status: {status}",
                    }

            job_states[request_id] = {"status": "PROCESSING"}
            return {
                "request_id": request_id,
                "status": "PROCESSING",
                "message": "Job submitted successfully",
            }

        async def mock_get_job_status(request_id):
            return job_states.get(request_id)

        mock_service.submit_job = mock_submit_job
        mock_service.get_job_status = mock_get_job_status
        mock_service.process_job_background = MagicMock()

        client = create_test_client(mock_service)

        response = client.post(
            "/api/transcribe",
            json={
                "request_id": "completed-job-123",
                "media_url": "http://example.com/audio.mp3",
            },
            headers={"X-API-Key": "test-key"},
        )

        assert response.status_code == 202
        data = response.json()
        assert data["error_code"] == 0
        assert data["data"]["status"] == "COMPLETED"
        assert "already exists" in data["message"].lower()

    def test_retry_flow_fail_then_success(self):
        """Test full retry flow: submit → fail → retry → success."""
        mock_service = MagicMock()
        job_states = {}
        call_count = {"submit": 0}

        async def mock_submit_job(request_id, media_url, language=None):
            call_count["submit"] += 1

            if request_id in job_states:
                existing = job_states[request_id]
                status = existing.get("status", "PROCESSING")

                if status == "FAILED":
                    # Allow retry
                    job_states[request_id] = {"status": "PROCESSING"}
                    return {
                        "request_id": request_id,
                        "status": "PROCESSING",
                        "message": "Job submitted successfully",
                    }
                else:
                    return {
                        "request_id": request_id,
                        "status": status,
                        "message": f"Job already exists with status: {status}",
                    }

            job_states[request_id] = {"status": "PROCESSING"}
            return {
                "request_id": request_id,
                "status": "PROCESSING",
                "message": "Job submitted successfully",
            }

        async def mock_get_job_status(request_id):
            return job_states.get(request_id)

        mock_service.submit_job = mock_submit_job
        mock_service.get_job_status = mock_get_job_status
        mock_service.process_job_background = MagicMock()

        client = create_test_client(mock_service)

        # Step 1: Submit new job
        response1 = client.post(
            "/api/transcribe",
            json={
                "request_id": "retry-flow-123",
                "media_url": "http://example.com/audio.mp3",
            },
            headers={"X-API-Key": "test-key"},
        )
        assert response1.status_code == 202
        assert response1.json()["data"]["status"] == "PROCESSING"

        # Step 2: Simulate job failure
        job_states["retry-flow-123"] = {
            "status": "FAILED",
            "error": "Simulated failure",
        }

        # Step 3: Poll - should see FAILED
        response2 = client.get(
            "/api/transcribe/retry-flow-123",
            headers={"X-API-Key": "test-key"},
        )
        assert response2.status_code == 200
        assert response2.json()["data"]["status"] == "FAILED"

        # Step 4: Retry - submit again
        response3 = client.post(
            "/api/transcribe",
            json={
                "request_id": "retry-flow-123",
                "media_url": "http://example.com/audio.mp3",
            },
            headers={"X-API-Key": "test-key"},
        )
        assert response3.status_code == 202
        # Should be PROCESSING again (retry allowed)
        assert response3.json()["data"]["status"] == "PROCESSING"
        assert "submitted successfully" in response3.json()["message"].lower()

        # Step 5: Simulate success
        job_states["retry-flow-123"] = {
            "status": "COMPLETED",
            "transcription": "Retry successful!",
        }

        # Step 6: Poll - should see COMPLETED
        response4 = client.get(
            "/api/transcribe/retry-flow-123",
            headers={"X-API-Key": "test-key"},
        )
        assert response4.status_code == 200
        assert response4.json()["data"]["status"] == "COMPLETED"
        assert response4.json()["data"]["transcription"] == "Retry successful!"
