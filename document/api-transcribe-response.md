# Transcribe API Response Specification

## Endpoint

```
POST /transcribe
```

## Authentication

Header: `X-API-Key: <your-api-key>`

## Request Body

```json
{
  "media_url": "minio://bucket/path/file.mp3",
  "language": "vi"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `media_url` | string | Yes | URL to audio file. Supports: `http://`, `https://`, `minio://bucket/path` |
| `language` | string | No | Language hint (default: `vi`). Examples: `vi`, `en`, `ja` |

---

## Response Format

**The API ALWAYS returns this JSON structure**, regardless of success or error:

```json
{
  "error_code": 0,
  "message": "Transcription successful",
  "transcription": "Nội dung được chuyển đổi từ audio...",
  "duration": 34.06,
  "confidence": 0.98,
  "processing_time": 8.52
}
```

### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `error_code` | int | `0` = success, `1` = error/timeout |
| `message` | string | Human-readable result message |
| `transcription` | string | Transcribed text (empty string on error) |
| `duration` | float | Audio duration in seconds (0.0 on error) |
| `confidence` | float | Confidence score 0.0-1.0 (0.0 on error) |
| `processing_time` | float | Processing time in seconds (0.0 on error) |

---

## HTTP Status Codes

| Code | Condition | Example Message |
|------|-----------|-----------------|
| 200 | Success | `Transcription successful` |
| 400 | Invalid request | `media_url must start with http://, https://, or minio://` |
| 401 | Unauthorized | `Invalid or missing API key` |
| 408 | Timeout | `Transcription timeout exceeded` |
| 413 | File too large | `File too large: 550MB > 500MB` |
| 500 | Server error | `Internal server error: S3 operation failed...` |

---

## Response Examples

### Success (HTTP 200)

```json
{
  "error_code": 0,
  "message": "Transcription successful",
  "transcription": "Xin chào, đây là nội dung audio được chuyển đổi thành văn bản.",
  "duration": 34.06,
  "confidence": 0.98,
  "processing_time": 8.52
}
```

### Timeout (HTTP 408)

```json
{
  "error_code": 1,
  "message": "Transcription timeout exceeded",
  "transcription": "",
  "duration": 0.0,
  "confidence": 0.0,
  "processing_time": 0.0
}
```

### File Not Found (HTTP 500)

```json
{
  "error_code": 1,
  "message": "Internal server error: S3 operation failed; code: NoSuchKey, message: Object does not exist",
  "transcription": "",
  "duration": 0.0,
  "confidence": 0.0,
  "processing_time": 0.0
}
```

### File Too Large (HTTP 413)

```json
{
  "error_code": 1,
  "message": "File too large: 550.00MB > 500MB",
  "transcription": "",
  "duration": 0.0,
  "confidence": 0.0,
  "processing_time": 0.0
}
```

### Invalid URL (HTTP 400)

```json
{
  "error_code": 1,
  "message": "media_url must start with http://, https://, or minio://",
  "transcription": "",
  "duration": 0.0,
  "confidence": 0.0,
  "processing_time": 0.0
}
```

---

## Client Integration Example

```python
import requests

response = requests.post(
    "http://localhost:8000/transcribe",
    headers={"X-API-Key": "your-api-key"},
    json={
        "media_url": "minio://smap-stt-audio-files/downloads/audio.mp3",
        "language": "vi"
    }
)

data = response.json()

if data["error_code"] == 0:
    print(f"Transcription: {data['transcription']}")
    print(f"Duration: {data['duration']}s")
else:
    print(f"Error: {data['message']}")
```

```bash
# cURL example
curl -X POST http://localhost:8000/transcribe \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{"media_url": "minio://bucket/file.mp3", "language": "vi"}'
```

---

## Notes

1. **Consistent Response**: All responses (success and error) use the same JSON structure
2. **Error Detection**: Check `error_code` field, not HTTP status code for business logic
3. **Timeout**: Default timeout is adaptive based on audio duration (max 90s base + 1.5x audio length)
4. **File Size Limit**: Maximum 500MB (configurable via `MAX_UPLOAD_SIZE_MB`)
5. **Supported Formats**: MP3, WAV, M4A, and other formats supported by FFmpeg
