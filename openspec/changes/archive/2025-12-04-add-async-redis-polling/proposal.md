# Change: Add Async STT Service with Redis Polling

## Why
Crawler gọi STT Service theo cơ chế đồng bộ (Synchronous HTTP). Với video dài (> 1 phút), thời gian xử lý AI vượt quá timeout mặc định (90s) → Connection bị ngắt → Crawler báo lỗi dù STT vẫn đang chạy ngầm. Cần chuyển sang cơ chế bất đồng bộ (Asynchronous) với Polling pattern để tránh Crawler phải mở port lắng nghe webhook.

## What Changes
- **ADDED**: `POST /api/v1/transcribe` - Submit job endpoint (trả về 202 Accepted ngay lập tức)
- **ADDED**: `GET /api/v1/transcribe/{request_id}` - Check status endpoint (polling)
- **ADDED**: Redis integration cho job state management
- **ADDED**: Background task processing với FastAPI BackgroundTasks
- **ADDED**: Redis configuration trong Settings
- **MODIFIED**: Giữ nguyên endpoint `/transcribe` cũ cho backward compatibility

## Impact
- Affected specs: `stt-api`
- Affected code:
  - `core/config.py` - Thêm Redis settings
  - `internal/api/routes/` - Thêm async transcribe routes
  - `internal/api/schemas/` - Thêm request/response schemas
  - `services/` - Thêm async transcription service
  - `infrastructure/` - Thêm Redis adapter
  - `pyproject.toml` - Thêm redis dependency

## Technical Decisions
- **Redis Key Format**: `stt:job:{request_id}` với TTL 1 giờ (3600s)
- **Job States**: `PROCESSING` → `COMPLETED` | `FAILED`
- **Idempotency**: Nếu job đã tồn tại, trả về status hiện tại thay vì tạo mới
- **Local Testing**: Sử dụng Redis container đang chạy tại `localhost:6379`
