# STT Service - Mô Tả Business Logic

## Tổng Quan

Speech-to-Text (STT) Service là một dịch vụ chuyển đổi âm thanh thành văn bản sử dụng Whisper.cpp. Service được thiết kế theo kiến trúc stateless, hỗ trợ cả xử lý đồng bộ (sync) và bất đồng bộ (async).

## Luồng Xử Lý Chính

### 1. Transcription Flow (Đồng Bộ)

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Client    │────▶│  /transcribe     │────▶│ TranscribeService│────▶│   Whisper    │
│             │     │  (API Endpoint)  │     │                  │     │   Engine     │
└─────────────┘     └──────────────────┘     └──────────────────┘     └──────────────┘
                            │                        │
                            │                        ▼
                            │               ┌─────────────────┐
                            │               │ AudioDownloader │
                            │               │ (MinIO/HTTP)    │
                            │               └─────────────────┘
                            ▼
                    ┌──────────────────┐
                    │  JSON Response   │
                    │  (transcription) │
                    └──────────────────┘
```

**Các bước xử lý:**

1. Client gửi request với `media_url` và `language`
2. Service download audio từ URL (hỗ trợ HTTP và MinIO)
3. Phát hiện độ dài audio để tính adaptive timeout
4. Nếu audio > 30s: sử dụng chunked transcription
5. Nếu audio ≤ 30s: transcription trực tiếp
6. Trả về kết quả transcription

### 2. Async Transcription Flow (Bất Đồng Bộ)

```
┌─────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Client    │────▶│ POST /api/       │────▶│ AsyncTranscribe │
│             │     │ transcribe       │     │ Service         │
└─────────────┘     └──────────────────┘     └─────────────────┘
      │                     │                        │
      │                     │ 202 Accepted           │
      │◀────────────────────┘                        │
      │                                              ▼
      │                                     ┌─────────────────┐
      │                                     │ Background Task │
      │                                     │ (Transcription) │
      │                                     └─────────────────┘
      │                                              │
      │     ┌──────────────────┐                     │
      │────▶│ GET /api/        │                     │
      │     │ transcribe/{id}  │                     ▼
      │     └──────────────────┘            ┌─────────────────┐
      │             │                       │     Redis       │
      │             │◀──────────────────────│  (Job State)    │
      │◀────────────┘                       └─────────────────┘
      │     (PROCESSING/COMPLETED/FAILED)
```

**Các bước xử lý:**

1. Client submit job với `request_id`, `media_url`, `language`
2. Service kiểm tra job đã tồn tại chưa:
   - **PROCESSING**: Trả về status hiện tại
   - **COMPLETED**: Trả về kết quả cũ
   - **FAILED**: Xóa job cũ, tạo job mới (retry)
   - **Không tồn tại**: Tạo job mới
3. Lưu trạng thái PROCESSING vào Redis
4. Trả về 202 Accepted ngay lập tức
5. Background task thực hiện transcription
6. Cập nhật Redis với COMPLETED hoặc FAILED
7. Client polling để lấy kết quả

## Business Rules

### Xử Lý Audio

| Rule                 | Mô Tả                                                 |
| -------------------- | ----------------------------------------------------- |
| **Chunking**         | Audio > 30s được chia thành chunks 30s với overlap 3s |
| **Min Chunk**        | Chunk < 2s sẽ được merge với chunk trước đó           |
| **Adaptive Timeout** | Timeout = max(base_timeout, audio_duration \* 1.5)    |
| **File Size Limit**  | Mặc định 500MB                                        |

### Định Dạng Audio Hỗ Trợ

```
MP3, WAV, M4A, MP4, AAC, OGG, FLAC, WMA, WEBM, MKV, AVI, MOV
```

### Ngôn Ngữ Hỗ Trợ

- `vi` - Tiếng Việt (mặc định)
- `en` - Tiếng Anh
- Các ngôn ngữ khác theo Whisper model

### Whisper Models

| Model  | RAM    | Kích Thước | Độ Chính Xác |
| ------ | ------ | ---------- | ------------ |
| base   | ~1GB   | 60MB       | Trung bình   |
| small  | ~500MB | 181MB      | Khá          |
| medium | ~2GB   | 1.5GB      | Cao          |

## Xử Lý Lỗi

### Transient Errors (Có thể retry)

- `TimeoutError` - Transcription timeout
- `WhisperCrashError` - Whisper process crash
- `NetworkError` - Lỗi mạng
- `OutOfMemoryError` - Hết bộ nhớ

### Permanent Errors (Không retry)

- `InvalidAudioFormatError` - Định dạng không hỗ trợ
- `FileTooLargeError` - File quá lớn
- `FileNotFoundError` - Không tìm thấy file
- `TranscriptionError` - Lỗi transcription chung

## Chunked Transcription Logic

### Thuật Toán Chia Chunk

```python
chunk_duration = 30s  # Độ dài mỗi chunk
chunk_overlap = 3s    # Overlap giữa các chunk

# Tính toán chunks
while start < duration:
    end = min(start + chunk_duration, duration)
    chunks.append((start, end))
    start = end - overlap
```

### Smart Merge

Khi merge các chunk, service thực hiện:

1. Loại bỏ duplicate text ở boundary (do overlap)
2. So sánh 5 từ cuối chunk trước với 5 từ đầu chunk sau
3. Xóa các từ trùng lặp
4. Xử lý chunk rỗng hoặc `[inaudible]`

### Audio Validation

Trước khi transcribe, audio được validate:

- **Silent Audio**: max amplitude < 0.01 → warning
- **Constant Noise**: std deviation < 0.001 → warning
- **Empty Audio**: 0 samples → error

## Job State Management (Async)

### Trạng Thái Job

```
PROCESSING → COMPLETED
          → FAILED → (retry) → PROCESSING
```

### Redis Key Format

```
stt:job:{request_id}
```

### TTL

- Mặc định: 1 giờ (3600s)
- Configurable qua `REDIS_JOB_TTL`

### Idempotency & Retry Mechanism

| Trạng thái hiện tại | Hành vi khi submit cùng `request_id`      |
| ------------------- | ----------------------------------------- |
| **PROCESSING**      | Trả về status hiện tại (idempotency)      |
| **COMPLETED**       | Trả về kết quả cũ (không xử lý lại)       |
| **FAILED**          | Xóa job cũ → Tạo job mới (cho phép retry) |

**Chi tiết:**

- **PROCESSING**: Job đang được xử lý → trả về status để client tiếp tục polling
- **COMPLETED**: Job đã hoàn thành → trả về kết quả cũ, tiết kiệm tài nguyên
- **FAILED**: Job đã thất bại → cho phép retry bằng cách xóa job cũ và tạo job mới

**Lý do cho phép retry FAILED jobs:**

- `request_id` được tạo từ MD5 hash của `media_url` (phía client)
- Cùng video → Cùng URL → Cùng `request_id`
- Nếu không cho retry, các job FAILED sẽ block vĩnh viễn

## Response Format

### Success Response

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

### Error Response

```json
{
  "error_code": 1,
  "message": "Transcription timeout exceeded",
  "errors": {
    "detail": "Request took too long. Use async API for long audio."
  }
}
```

## Performance Considerations

### Thread Pool

- Dedicated ThreadPoolExecutor với 2 workers
- Tách biệt CPU-bound transcription khỏi async I/O

### Connection Pooling

- HTTP client sử dụng connection pooling
- Max 20 concurrent connections
- Keep-alive 30s

### Model Loading

- Eager loading: Model được load khi startup
- Singleton pattern: Một instance duy nhất
- Thread-safe: Lock khi access Whisper context
