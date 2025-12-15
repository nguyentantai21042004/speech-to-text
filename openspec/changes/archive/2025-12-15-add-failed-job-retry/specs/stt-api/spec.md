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

#### Scenario: Submit duplicate job - PROCESSING (idempotency)

- **WHEN** client sends POST `/api/v1/transcribe` with `request_id` that already exists with status `PROCESSING`
- **THEN** the service SHALL return HTTP 202 with current job status wrapped in `data` field
- **AND** the service SHALL NOT create a new job

#### Scenario: Submit duplicate job - COMPLETED (idempotency)

- **WHEN** client sends POST `/api/v1/transcribe` with `request_id` that already exists with status `COMPLETED`
- **THEN** the service SHALL return HTTP 202 with current job status wrapped in `data` field
- **AND** the service SHALL NOT create a new job
- **AND** the service SHALL NOT re-process the transcription

#### Scenario: Submit duplicate job - FAILED (retry allowed)

- **WHEN** client sends POST `/api/v1/transcribe` with `request_id` that already exists with status `FAILED`
- **THEN** the service SHALL delete the existing FAILED job from Redis
- **AND** the service SHALL create a new job with status `PROCESSING`
- **AND** the service SHALL return HTTP 202 with unified JSON format:
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
- **AND** the service SHALL start background transcription processing

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
