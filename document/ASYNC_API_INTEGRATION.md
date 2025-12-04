# Async STT API Integration Guide

Hướng dẫn tích hợp Async Speech-to-Text API với polling pattern cho các service khác (Crawler, Backend, etc.)

---

## Tổng quan

### Vấn đề cần giải quyết
- API đồng bộ (`POST /transcribe`) bị timeout với video dài (> 1 phút)
- Connection bị ngắt trước khi transcription hoàn thành
- Crawler báo lỗi dù STT vẫn đang xử lý ngầm

### Giải pháp: Polling Pattern
1. **Submit** - Gửi job với `request_id` (client-generated)
2. **Process** - STT xử lý ngầm, trả về 202 Accepted ngay lập tức
3. **Poll** - Client hỏi thăm định kỳ cho đến khi COMPLETED/FAILED

---

## API Endpoints

### 1. Submit Job

```
POST /api/v1/transcribe
```

**Headers:**
```
Content-Type: application/json
X-API-Key: <your-api-key>
```

**Request Body:**
```json
{
  "request_id": "7577034049470926087",
  "media_url": "http://minio-host/bucket/audio.mp3?token=...",
  "language": "vi"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `request_id` | string | ✅ | ID duy nhất từ client (dùng `post_id`) |
| `media_url` | string | ✅ | URL audio (http/https/minio) |
| `language` | string | ❌ | Ngôn ngữ (default: "vi") |

**Response (202 Accepted):**
```json
{
  "request_id": "7577034049470926087",
  "status": "PROCESSING",
  "message": "Job submitted successfully"
}
```

**Idempotency:** Nếu `request_id` đã tồn tại, trả về status hiện tại thay vì tạo job mới.

---

### 2. Poll Status

```
GET /api/v1/transcribe/{request_id}
```

**Headers:**
```
X-API-Key: <your-api-key>
```

**Response States:**

#### PROCESSING (đang xử lý)
```json
{
  "request_id": "7577034049470926087",
  "status": "PROCESSING",
  "message": "Transcription in progress"
}
```

#### COMPLETED (hoàn thành)
```json
{
  "request_id": "7577034049470926087",
  "status": "COMPLETED",
  "message": "Transcription completed successfully",
  "transcription": "Nội dung video đã được bóc tách...",
  "duration": 45.5,
  "confidence": 0.98,
  "processing_time": 12.3
}
```

#### FAILED (lỗi)
```json
{
  "request_id": "7577034049470926087",
  "status": "FAILED",
  "message": "Transcription failed",
  "error": "Failed to download audio file: 403 Forbidden"
}
```

#### NOT FOUND (404)
```json
{
  "detail": "Job not found: 7577034049470926087"
}
```

---

## Code Examples

### Python (requests)

```python
import time
import requests
from typing import Optional

def get_stt_result(audio_url: str, post_id: str, api_key: str) -> Optional[str]:
    """
    Gọi Async STT API với polling pattern.
    
    Args:
        audio_url: URL của file audio (presigned URL từ MinIO)
        post_id: ID bài viết (dùng làm request_id)
        api_key: API key để authenticate
        
    Returns:
        Transcription text nếu thành công, None nếu thất bại
    """
    stt_host = "http://stt-service:8000"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key
    }
    
    # 1. Submit job
    try:
        resp = requests.post(
            f"{stt_host}/api/v1/transcribe",
            json={
                "request_id": post_id,
                "media_url": audio_url,
                "language": "vi"
            },
            headers=headers,
            timeout=10  # Timeout ngắn cho submit
        )
        resp.raise_for_status()
        
        submit_data = resp.json()
        print(f"Job submitted: {submit_data}")
        
    except requests.RequestException as e:
        print(f"Submit failed: {e}")
        return None

    # 2. Polling loop
    max_retries = 60      # Tối đa 60 lần
    wait_time = 3         # Mỗi lần chờ 3s → Tổng 3 phút
    
    for attempt in range(max_retries):
        try:
            status_resp = requests.get(
                f"{stt_host}/api/v1/transcribe/{post_id}",
                headers=headers,
                timeout=10
            )
            
            if status_resp.status_code == 404:
                print(f"Job not found (expired?)")
                return None
                
            if status_resp.status_code == 200:
                data = status_resp.json()
                status = data.get("status")
                
                if status == "COMPLETED":
                    print(f"Transcription completed in {data.get('processing_time', 0):.1f}s")
                    return data.get("transcription")
                
                if status == "FAILED":
                    print(f"Transcription failed: {data.get('error')}")
                    return None
                
                # PROCESSING - tiếp tục polling
                print(f"[{attempt+1}/{max_retries}] Still processing...")
            
            time.sleep(wait_time)
            
        except requests.RequestException as e:
            print(f"Polling error: {e}")
            time.sleep(wait_time)
            continue

    print("Polling timeout - job may still be processing")
    return None


# Usage
if __name__ == "__main__":
    result = get_stt_result(
        audio_url="http://minio:9000/bucket/video.mp3?token=xyz",
        post_id="7577034049470926087",
        api_key="your-api-key"
    )
    
    if result:
        print(f"Transcription: {result[:100]}...")
    else:
        print("Failed to get transcription")
```

### Python (httpx async)

```python
import asyncio
import httpx
from typing import Optional

async def get_stt_result_async(
    audio_url: str, 
    post_id: str, 
    api_key: str,
    max_wait_seconds: int = 180
) -> Optional[str]:
    """
    Async version với httpx.
    """
    stt_host = "http://stt-service:8000"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key
    }
    
    async with httpx.AsyncClient(timeout=30) as client:
        # 1. Submit
        try:
            resp = await client.post(
                f"{stt_host}/api/v1/transcribe",
                json={
                    "request_id": post_id,
                    "media_url": audio_url,
                    "language": "vi"
                },
                headers=headers
            )
            resp.raise_for_status()
        except httpx.HTTPError as e:
            print(f"Submit failed: {e}")
            return None

        # 2. Polling
        wait_interval = 3
        elapsed = 0
        
        while elapsed < max_wait_seconds:
            try:
                status_resp = await client.get(
                    f"{stt_host}/api/v1/transcribe/{post_id}",
                    headers=headers
                )
                
                if status_resp.status_code == 404:
                    return None
                    
                data = status_resp.json()
                status = data.get("status")
                
                if status == "COMPLETED":
                    return data.get("transcription")
                    
                if status == "FAILED":
                    print(f"Failed: {data.get('error')}")
                    return None
                    
            except httpx.HTTPError:
                pass
                
            await asyncio.sleep(wait_interval)
            elapsed += wait_interval
            
        return None


# Usage
async def main():
    result = await get_stt_result_async(
        audio_url="http://minio:9000/bucket/video.mp3",
        post_id="123456",
        api_key="your-key"
    )
    print(result)

asyncio.run(main())
```

### cURL

```bash
# 1. Submit job
curl -X POST http://localhost:8000/api/v1/transcribe \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "request_id": "test-123",
    "media_url": "http://example.com/audio.mp3",
    "language": "vi"
  }'

# 2. Poll status (repeat until COMPLETED/FAILED)
curl -X GET http://localhost:8000/api/v1/transcribe/test-123 \
  -H "X-API-Key: your-api-key"
```

---

## Best Practices

### 1. Request ID Strategy
```python
# Dùng post_id làm request_id để đảm bảo idempotency
request_id = str(post.id)  # "7577034049470926087"

# Hoặc combine với timestamp nếu cần retry
request_id = f"{post.id}_{int(time.time())}"
```

### 2. Polling Configuration

| Scenario | Wait Time | Max Retries | Total Wait |
|----------|-----------|-------------|------------|
| Short audio (< 1 min) | 2s | 30 | 1 min |
| Medium audio (1-5 min) | 3s | 60 | 3 min |
| Long audio (5-15 min) | 5s | 120 | 10 min |
| Very long (> 15 min) | 10s | 180 | 30 min |

### 3. Error Handling

```python
def handle_stt_result(post_id: str, audio_url: str):
    result = get_stt_result(audio_url, post_id, API_KEY)
    
    if result is None:
        # Retry với exponential backoff
        for attempt in range(3):
            time.sleep(2 ** attempt)  # 1s, 2s, 4s
            result = get_stt_result(audio_url, post_id, API_KEY)
            if result:
                break
    
    if result is None:
        # Log và mark post để manual review
        logger.error(f"STT failed for post {post_id}")
        mark_post_for_review(post_id)
        return
    
    # Success - save transcription
    save_transcription(post_id, result)
```

### 4. Concurrent Processing

```python
import asyncio
from typing import List, Tuple

async def process_batch(posts: List[dict], api_key: str) -> List[Tuple[str, str]]:
    """Process multiple posts concurrently."""
    
    async def process_one(post):
        result = await get_stt_result_async(
            audio_url=post["audio_url"],
            post_id=str(post["id"]),
            api_key=api_key
        )
        return (post["id"], result)
    
    # Limit concurrency to avoid overwhelming STT service
    semaphore = asyncio.Semaphore(5)  # Max 5 concurrent jobs
    
    async def limited_process(post):
        async with semaphore:
            return await process_one(post)
    
    results = await asyncio.gather(*[limited_process(p) for p in posts])
    return results
```

---

## Configuration

### Environment Variables (STT Service)

```bash
# Redis (required for async API)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_PASSWORD=your-password
REDIS_DB=0
REDIS_JOB_TTL=3600  # Job expires after 1 hour
```

### Docker Compose

```yaml
services:
  stt-service:
    image: stt-api:latest
    environment:
      - REDIS_HOST=redis
      - REDIS_PORT=6379
      - REDIS_PASSWORD=${REDIS_PASSWORD}
    depends_on:
      - redis
    
  redis:
    image: redis:7.4-alpine
    command: ["redis-server", "--requirepass", "${REDIS_PASSWORD}"]
    ports:
      - "6379:6379"
```

---

## Troubleshooting

### Job not found (404)
- Job đã hết TTL (default 1 giờ)
- Request ID sai
- Job chưa được submit

### Polling timeout
- Audio quá dài, tăng `max_retries`
- STT service quá tải, check logs
- Network issues

### Submit returns existing status
- Đây là behavior đúng (idempotency)
- Nếu muốn retry, dùng request_id mới

### FAILED status
- Check `error` field trong response
- Common errors:
  - Download failed: URL không accessible
  - Timeout: Audio quá dài
  - Invalid format: File không phải audio

---

## Migration từ Sync API

### Before (Sync)
```python
# Dễ bị timeout với video dài
resp = requests.post(
    "http://stt:8000/transcribe",
    json={"media_url": url},
    timeout=90  # Không đủ cho video > 1 phút
)
```

### After (Async)
```python
# Không bao giờ timeout
result = get_stt_result(
    audio_url=url,
    post_id=post_id,
    api_key=api_key
)
```

---

## Support

- **API Docs**: http://stt-service:8000/docs
- **Health Check**: http://stt-service:8000/health
- **Contact**: nguyentantai.dev@gmail.com
