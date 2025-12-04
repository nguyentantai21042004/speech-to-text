# Design: Async STT Service with Redis Polling

## Context
- Crawler hiện tại gọi STT Service đồng bộ, gặp timeout với video dài
- Không muốn dùng Webhook vì Crawler không mở port lắng nghe
- Redis đã có sẵn trong infrastructure (container đang chạy)

## Goals / Non-Goals
**Goals:**
- Xử lý video dài (> 1 phút) không bị timeout
- Client-generated ID (dùng `post_id` từ Crawler)
- Idempotent job submission
- Backward compatible với API cũ

**Non-Goals:**
- Job queue với priority
- Distributed workers
- Persistent job history

## Decisions

### 1. Polling Pattern với Client-Generated ID
- **Decision**: Crawler tự sinh ID (dùng `post_id`), gửi kèm request
- **Why**: Đơn giản, không cần server generate ID, dễ track từ phía Crawler

### 2. Redis làm State Store
- **Decision**: Dùng Redis với TTL 1 giờ
- **Why**: Lightweight, fast, tự cleanup, đã có trong infrastructure
- **Alternatives**: 
  - PostgreSQL: Overkill cho temporary state
  - In-memory: Mất state khi restart

### 3. FastAPI BackgroundTasks
- **Decision**: Dùng BackgroundTasks thay vì Celery/RQ
- **Why**: Đơn giản, không cần thêm dependency, đủ cho use case hiện tại
- **Trade-off**: Không có retry mechanism, job mất nếu server crash

### 4. API Versioning
- **Decision**: Đặt async API tại `/api/v1/transcribe`
- **Why**: Tách biệt với API cũ `/transcribe`, dễ migrate dần

## Redis Schema

```
Key: stt:job:{request_id}
TTL: 3600 seconds (1 hour)
Value: JSON string

States:
- PROCESSING: {"status": "PROCESSING"}
- COMPLETED: {"status": "COMPLETED", "text": "...", "duration": 45.5, ...}
- FAILED: {"status": "FAILED", "error": "..."}
```

## Sequence Diagram

```
Crawler                    STT Service                    Redis
   |                            |                           |
   |-- POST /api/v1/transcribe ->|                           |
   |   {request_id, audio_url}  |                           |
   |                            |-- SET stt:job:{id} ------->|
   |                            |   {status: PROCESSING}     |
   |<-- 202 Accepted -----------|                           |
   |                            |                           |
   |                            |-- Background Task -------->|
   |                            |   (download + transcribe)  |
   |                            |                           |
   |-- GET /api/v1/transcribe/{id} ->|                      |
   |                            |-- GET stt:job:{id} ------->|
   |<-- {status: PROCESSING} ---|<--------------------------|
   |                            |                           |
   |   ... (polling) ...        |                           |
   |                            |                           |
   |                            |-- SET stt:job:{id} ------->|
   |                            |   {status: COMPLETED, ...} |
   |                            |                           |
   |-- GET /api/v1/transcribe/{id} ->|                      |
   |                            |-- GET stt:job:{id} ------->|
   |<-- {status: COMPLETED, text: ...} |<-------------------|
```

## Risks / Trade-offs

| Risk | Mitigation |
|------|------------|
| Job mất nếu server crash | Crawler có thể retry với cùng request_id |
| Redis down | Health check sẽ báo unhealthy |
| Memory leak nếu nhiều job | TTL 1 giờ tự cleanup |

## Migration Plan
1. Deploy Redis config (đã có container)
2. Deploy async API endpoints
3. Crawler migrate sang API mới
4. Monitor và tune TTL nếu cần

## Open Questions
- Có cần retry mechanism cho failed jobs?
- TTL 1 giờ có đủ cho Crawler polling?
