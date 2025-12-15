# STT Service - Hướng Dẫn Tích Hợp

## Tổng Quan Kiến Trúc

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           External Systems                              │
├─────────────────┬─────────────────┬─────────────────┬───────────────────┤
│   Crawler       │   Backend       │   Other         │   Monitoring      │
│   Service       │   Services      │   Consumers     │   Systems         │
└────────┬────────┴────────┬────────┴────────┬────────┴─────────┬─────────┘
         │                 │                 │                   │
         │    HTTP/REST    │                 │                   │
         ▼                 ▼                 ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         STT API Service                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ /transcribe │  │ /api/       │  │ /health     │  │ /docs       │     │
│  │ (sync)      │  │ transcribe  │  │             │  │ (Swagger)   │     │
│  │             │  │ (async)     │  │             │  │             │     │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │
└────────┬────────────────┬────────────────┬──────────────────────────────┘
         │                │                │
         ▼                ▼                ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│     MinIO       │ │     Redis       │ │   Whisper.cpp   │
│ (Audio Storage) │ │ (Job State)     │ │ (Transcription) │
└─────────────────┘ └─────────────────┘ └─────────────────┘
```

## Các Service Tương Tác

### 1. MinIO (Object Storage)

**Mục đích:** Lưu trữ và cung cấp audio files

**Cấu hình:**

```env
MINIO_ENDPOINT=http://172.16.19.115:9000
MINIO_ACCESS_KEY=smap
MINIO_SECRET_KEY=hcmut2025
```

**URL Format:**

```
minio://bucket-name/path/to/audio.mp3
```

**Luồng tương tác:**

```
STT Service                          MinIO
     │                                 │
     │  1. stat_object (check size)    │
     │────────────────────────────────▶│
     │◀────────────────────────────────│
     │                                 │
     │  2. fget_object (download)      │
     │────────────────────────────────▶│
     │◀────────────────────────────────│
     │     (audio file)                │
```

**Lưu ý:**

- STT Service hỗ trợ cả `minio://` và `http://` URLs
- Với `minio://`: download trực tiếp qua S3 API (nhanh hơn)
- Với `http://`: download qua HTTP streaming

### 2. Redis (Job State Management)

**Mục đích:** Lưu trữ trạng thái job cho async transcription

**Cấu hình:**

```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=
REDIS_DB=0
REDIS_JOB_TTL=3600
```

**Key Format:**

```
stt:job:{request_id}
```

**Data Structure:**

```json
// PROCESSING state
{
  "status": "PROCESSING",
  "media_url": "minio://bucket/audio.mp3",
  "language": "vi",
  "submitted_at": 1702000000.123
}

// COMPLETED state
{
  "status": "COMPLETED",
  "transcription": "Nội dung...",
  "duration": 45.5,
  "confidence": 0.98,
  "processing_time": 12.3,
  "completed_at": 1702000012.456
}

// FAILED state
{
  "status": "FAILED",
  "error": "Download failed: Connection timeout",
  "processing_time": 5.2,
  "failed_at": 1702000005.789
}
```

**Luồng tương tác:**

```
STT Service                          Redis
     │                                 │
     │  1. GET stt:job:{id}            │
     │    (check existing)             │
     │────────────────────────────────▶│
     │◀────────────────────────────────│
     │                                 │
     │  2. SETEX stt:job:{id}          │
     │    (set with TTL)               │
     │────────────────────────────────▶│
     │◀────────────────────────────────│
     │                                 │
     │  3. GET stt:job:{id}            │
     │    (polling)                    │
     │────────────────────────────────▶│
     │◀────────────────────────────────│
```

### 3. HTTP Sources (External Audio)

**Mục đích:** Download audio từ external URLs

**Cấu hình:**

```env
MAX_UPLOAD_SIZE_MB=500
```

**Connection Pool:**

```python
# Limits
max_keepalive_connections = 10
max_connections = 20
keepalive_expiry = 30.0

# Timeouts
connect_timeout = 10.0
read_timeout = 60.0
write_timeout = 10.0
pool_timeout = 5.0
```

**Luồng tương tác:**

```
STT Service                     External Server
     │                                 │
     │  1. GET (streaming)             │
     │────────────────────────────────▶│
     │◀────────────────────────────────│
     │     (chunked response)          │
     │                                 │
     │  2. Validate size               │
     │  3. Save to temp file           │
```

## API Endpoints

### Sync Transcription

```http
POST /transcribe
X-API-Key: {api_key}
Content-Type: application/json

{
  "media_url": "minio://bucket/audio.mp3",
  "language": "vi"
}
```

**Response:**

```json
{
  "error_code": 0,
  "message": "Transcription successful",
  "data": {
    "transcription": "Nội dung transcription...",
    "duration": 45.5,
    "confidence": 0.98,
    "processing_time": 12.3
  }
}
```

### Async Transcription

**Submit Job:**

```http
POST /api/transcribe
X-API-Key: {api_key}
Content-Type: application/json

{
  "request_id": "post_123456",
  "media_url": "minio://bucket/audio.mp3",
  "language": "vi"
}
```

**Response (202 Accepted):**

```json
{
  "error_code": 0,
  "message": "Job submitted successfully",
  "data": {
    "request_id": "post_123456",
    "status": "PROCESSING"
  }
}
```

**Idempotency & Retry Behavior:**

| Current Status | Behavior                                  |
| -------------- | ----------------------------------------- |
| PROCESSING     | Return current status (idempotent)        |
| COMPLETED      | Return existing result (no re-processing) |
| FAILED         | Delete old job → Create new job (retry)   |
| Not exists     | Create new job                            |

**Poll Status:**

```http
GET /api/transcribe/{request_id}
X-API-Key: {api_key}
```

**Response (COMPLETED):**

```json
{
  "error_code": 0,
  "message": "Transcription completed",
  "data": {
    "request_id": "post_123456",
    "status": "COMPLETED",
    "transcription": "Nội dung...",
    "duration": 45.5,
    "confidence": 0.98,
    "processing_time": 12.3
  }
}
```

### Health Check

```http
GET /health
```

**Response:**

```json
{
  "error_code": 0,
  "message": "Service is healthy",
  "data": {
    "status": "healthy",
    "service": "Speech-to-Text API",
    "version": "1.0.0",
    "model": {
      "initialized": true,
      "size": "base",
      "ram_mb": 1000,
      "uptime_seconds": 3600.5
    },
    "redis": {
      "healthy": true
    }
  }
}
```

## Authentication

### API Key

Tất cả endpoints (trừ `/health` và `/`) yêu cầu API key:

```http
X-API-Key: {INTERNAL_API_KEY}
```

**Cấu hình:**

```env
INTERNAL_API_KEY=smap-internal-key-changeme
```

## Error Codes

| HTTP Status | Error Code | Mô Tả                          |
| ----------- | ---------- | ------------------------------ |
| 200         | 0          | Success                        |
| 202         | 0          | Job accepted (async)           |
| 400         | 1          | Bad request                    |
| 401         | 1          | Unauthorized (invalid API key) |
| 404         | 1          | Job not found                  |
| 408         | 1          | Request timeout                |
| 413         | 1          | File too large                 |
| 422         | 1          | Validation error               |
| 500         | 1          | Internal server error          |

## Deployment

### Docker Compose

```yaml
services:
  stt-api:
    build:
      context: .
      dockerfile: cmd/api/Dockerfile
    ports:
      - "8000:8000"
    environment:
      - REDIS_HOST=redis
      - MINIO_ENDPOINT=http://minio:9000
    depends_on:
      - redis
      - minio

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  minio:
    image: minio/minio
    ports:
      - "9000:9000"
    command: server /data
```

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: stt-api
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: stt-api
          image: stt-api:latest
          resources:
            requests:
              memory: "2Gi"
              cpu: "2"
            limits:
              memory: "4Gi"
              cpu: "4"
          env:
            - name: REDIS_HOST
              value: "redis-service"
            - name: WHISPER_MODEL_SIZE
              value: "base"
```

## Monitoring

### Health Check Endpoint

```
GET /health
```

Kiểm tra:

- Model initialization status
- Redis connectivity
- Service uptime

### Logging

Logs được output theo format:

- `console`: Human-readable (development)
- `json`: Structured logging (production)

**Cấu hình:**

```env
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE_ENABLED=true
```

## Best Practices

### Khi Tích Hợp

1. **Sử dụng Async API cho audio dài (> 1 phút)**

   - Tránh timeout
   - Không block client

2. **Retry mechanism đã được tích hợp sẵn**

   - FAILED jobs tự động cho phép retry khi submit lại cùng `request_id`
   - PROCESSING/COMPLETED jobs giữ nguyên (idempotency)
   - Client chỉ cần submit lại request nếu job FAILED

3. **Sử dụng MinIO URLs khi có thể**

   - Download nhanh hơn qua internal network
   - Giảm bandwidth external

4. **Polling interval hợp lý**
   - Bắt đầu: 2-3 giây
   - Tăng dần nếu job chưa complete
   - Max: 10-15 giây

### Ví Dụ Polling Pattern

```python
import time
import requests

def transcribe_async(media_url: str, request_id: str) -> dict:
    # Submit job
    response = requests.post(
        "http://stt-api:8000/api/transcribe",
        headers={"X-API-Key": API_KEY},
        json={
            "request_id": request_id,
            "media_url": media_url,
            "language": "vi"
        }
    )

    if response.status_code != 202:
        raise Exception(f"Submit failed: {response.json()}")

    # Polling with exponential backoff
    interval = 2
    max_interval = 15
    max_attempts = 60

    for attempt in range(max_attempts):
        time.sleep(interval)

        status_response = requests.get(
            f"http://stt-api:8000/api/transcribe/{request_id}",
            headers={"X-API-Key": API_KEY}
        )

        data = status_response.json()
        status = data.get("data", {}).get("status")

        if status == "COMPLETED":
            return data["data"]
        elif status == "FAILED":
            raise Exception(data["data"].get("error"))

        # Increase interval
        interval = min(interval * 1.5, max_interval)

    raise Exception("Polling timeout")
```

## Troubleshooting

### Common Issues

| Vấn Đề              | Nguyên Nhân                    | Giải Pháp                             |
| ------------------- | ------------------------------ | ------------------------------------- |
| 401 Unauthorized    | API key sai/thiếu              | Kiểm tra `X-API-Key` header           |
| 408 Timeout         | Audio quá dài                  | Sử dụng async API                     |
| 413 File too large  | File > 500MB                   | Giảm kích thước hoặc tăng limit       |
| 404 Job not found   | Job expired hoặc không tồn tại | Kiểm tra `request_id`, tăng TTL       |
| Empty transcription | Audio silent/noise             | Kiểm tra chất lượng audio             |
| Job stuck at FAILED | Lỗi trước đó                   | Submit lại cùng `request_id` để retry |

### Debug Mode

```env
DEBUG=true
LOG_LEVEL=DEBUG
```

Khi bật debug:

- Chi tiết logs cho mỗi request
- Audio statistics (max, mean, std)
- Chunk processing details
