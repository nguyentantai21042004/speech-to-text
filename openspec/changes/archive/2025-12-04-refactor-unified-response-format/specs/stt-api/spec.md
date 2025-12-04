# stt-api Specification Delta

## MODIFIED Requirements

### Requirement: Async Transcription Job Submission
The system SHALL expose a POST `/api/v1/transcribe` endpoint that accepts a JSON payload with `request_id` (client-generated) and `audio_url` (presigned URL), stores job state in Redis, and returns 202 Accepted with unified response format.

#### Scenario: Submit new job successfully
- **WHEN** client sends POST `/api/v1/transcribe` with valid `request_id` and `audio_url`
- **THEN** the service SHALL return HTTP 202 with unified JSON format:
  ```json
  {
    "error_code": 0,
    "message": "Job submitted successfully",
    "data": {
      "request_id": "...",
      "status": "PROCESSING"
    }
  }
  ```

#### Scenario: Submit duplicate job (idempotency)
- **WHEN** client sends POST `/api/v1/transcribe` with `request_id` that already exists
- **THEN** the service SHALL return HTTP 202 with current job status wrapped in `data` field

#### Scenario: Validation error
- **WHEN** client sends invalid request (missing fields, invalid URL)
- **THEN** the service SHALL return HTTP 422 with unified error format:
  ```json
  {
    "error_code": 1,
    "message": "Validation error",
    "errors": {
      "media_url": "media_url must start with http://, https://, or minio://"
    }
  }
  ```

### Requirement: Async Transcription Status Polling
The system SHALL expose a GET `/api/v1/transcribe/{request_id}` endpoint that returns current job status in unified response format.

#### Scenario: Job completed successfully
- **WHEN** client polls a completed job
- **THEN** the service SHALL return HTTP 200 with unified format:
  ```json
  {
    "error_code": 0,
    "message": "Transcription completed",
    "data": {
      "request_id": "...",
      "status": "COMPLETED",
      "transcription": "...",
      "duration": 45.5,
      "confidence": 0.98,
      "processing_time": 12.3
    }
  }
  ```

#### Scenario: Job not found
- **WHEN** client polls non-existent job
- **THEN** the service SHALL return HTTP 404 with unified error format:
  ```json
  {
    "error_code": 1,
    "message": "Job not found",
    "errors": {
      "request_id": "Job xxx does not exist or has expired"
    }
  }
  ```

### Requirement: Presigned URL Transcription API
The system SHALL expose a POST `/transcribe` endpoint with unified response format.

#### Scenario: Successful transcription
- **WHEN** client sends valid transcription request
- **THEN** the service SHALL return HTTP 200 with unified format:
  ```json
  {
    "error_code": 0,
    "message": "Transcription successful",
    "data": {
      "transcription": "...",
      "duration": 45.5,
      "confidence": 0.98,
      "processing_time": 12.3
    }
  }
  ```

#### Scenario: Transcription error
- **WHEN** transcription fails
- **THEN** the service SHALL return appropriate HTTP status with unified error format:
  ```json
  {
    "error_code": 1,
    "message": "Transcription failed",
    "errors": {
      "detail": "Download failed: 403 Forbidden"
    }
  }
  ```
