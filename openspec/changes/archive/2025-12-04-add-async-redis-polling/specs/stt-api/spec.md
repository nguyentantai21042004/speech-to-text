# stt-api Specification Delta

## ADDED Requirements

### Requirement: Async Transcription Job Submission
The system SHALL expose a POST `/api/v1/transcribe` endpoint that accepts a JSON payload with `request_id` (client-generated) and `audio_url` (presigned URL), stores job state in Redis, and returns 202 Accepted immediately while processing in background.

#### Scenario: Submit new job successfully
- **WHEN** client sends POST `/api/v1/transcribe` with valid `request_id` and `audio_url`
- **THEN** the service SHALL store initial state `{status: "PROCESSING"}` in Redis with key `stt:job:{request_id}`
- **AND** the service SHALL return HTTP 202 with JSON `{message: "Job accepted", request_id: "...", status: "PROCESSING"}`
- **AND** the service SHALL start background task to download and transcribe audio

#### Scenario: Submit duplicate job (idempotency)
- **WHEN** client sends POST `/api/v1/transcribe` with `request_id` that already exists in Redis
- **THEN** the service SHALL return HTTP 202 with current job status
- **AND** the service SHALL NOT create a new background task

#### Scenario: Missing required fields
- **WHEN** client sends POST `/api/v1/transcribe` without `request_id` or `audio_url`
- **THEN** the service SHALL return HTTP 400 with error details

### Requirement: Async Transcription Status Polling
The system SHALL expose a GET `/api/v1/transcribe/{request_id}` endpoint that returns current job status from Redis.

#### Scenario: Job is processing
- **WHEN** client sends GET `/api/v1/transcribe/{request_id}` for a job in PROCESSING state
- **THEN** the service SHALL return HTTP 200 with JSON `{status: "PROCESSING"}`

#### Scenario: Job completed successfully
- **WHEN** client sends GET `/api/v1/transcribe/{request_id}` for a completed job
- **THEN** the service SHALL return HTTP 200 with JSON containing `status: "COMPLETED"`, `text`, `duration`, and other metadata

#### Scenario: Job failed
- **WHEN** client sends GET `/api/v1/transcribe/{request_id}` for a failed job
- **THEN** the service SHALL return HTTP 200 with JSON `{status: "FAILED", error: "..."}`

#### Scenario: Job not found
- **WHEN** client sends GET `/api/v1/transcribe/{request_id}` for non-existent job
- **THEN** the service SHALL return HTTP 404 with error message

### Requirement: Redis Job State Management
The system SHALL use Redis to store and manage async job states with automatic expiration.

#### Scenario: Job state TTL
- **WHEN** a job is created or updated in Redis
- **THEN** the key SHALL have TTL of 3600 seconds (1 hour)
- **AND** the key SHALL be automatically deleted after TTL expires

#### Scenario: Redis connection failure
- **WHEN** Redis is unavailable during job submission
- **THEN** the service SHALL return HTTP 503 Service Unavailable
- **AND** the health check SHALL report unhealthy status
