# Tasks: Add Async STT Service with Redis Polling

## 1. Infrastructure Setup
- [x] 1.1 Thêm `redis` dependency vào `pyproject.toml`
- [x] 1.2 Thêm Redis configuration vào `core/config.py`
- [x] 1.3 Tạo Redis adapter trong `infrastructure/redis/`

## 2. API Implementation
- [x] 2.1 Tạo request/response schemas cho async API
- [x] 2.2 Tạo async transcribe routes (`POST /api/v1/transcribe`, `GET /api/v1/transcribe/{request_id}`)
- [x] 2.3 Tạo async transcription service với background task

## 3. Integration
- [x] 3.1 Register routes trong FastAPI app
- [x] 3.2 Thêm Redis health check vào `/health` endpoint

## 4. Testing
- [x] 4.1 Test submit job endpoint
- [x] 4.2 Test polling endpoint
- [x] 4.3 Test idempotency (submit same request_id twice)
- [x] 4.4 Test với Redis integration thực tế

## 5. Documentation
- [x] 5.1 Update API documentation (README.md với async endpoints)
- [x] 5.2 Update Swagger UI (auto-generated từ FastAPI routes)
- [x] 5.3 Update ReDoc (auto-generated từ FastAPI routes)
- [x] 5.4 Update .env.example với Redis config
