# Change: Refactor Unified Response Format

## Why

Response format hiện tại không thống nhất giữa các endpoints:

- Health routes: dùng `StandardResponse` (đúng format)
- Async routes: trả về data fields trực tiếp (không wrap)
- Transcribe routes: dùng format riêng với `status`, `transcription`, etc.

Cần thống nhất tất cả responses theo format chuẩn để dễ parse ở client side.

## Target Format

```go
type Resp struct {
    ErrorCode int    `json:"error_code"`
    Message   string `json:"message"`
    Data      any    `json:"data,omitempty"`
    Errors    any    `json:"errors,omitempty"`
}
```

**Rules:**

- `error_code`: 0 = success, 1+ = error
- `message`: Human-readable message
- `data`: Chứa tất cả response data (omit nếu empty)
- `errors`: Chi tiết lỗi validation (omit nếu không có)

## What Changes

### Before (hiện tại)

```json
// Async submit - KHÔNG đúng format
{
  "request_id": "123",
  "status": "PROCESSING",
  "message": "Job submitted"
}

// Async poll COMPLETED - KHÔNG đúng format
{
  "request_id": "123",
  "status": "COMPLETED",
  "transcription": "...",
  "duration": 45.5
}

// Transcribe - KHÔNG đúng format
{
  "error_code": 0,
  "message": "Success",
  "transcription": "...",
  "duration": 45.5
}
```

### After (target)

```json
// Async submit - ĐÚNG format
{
  "error_code": 0,
  "message": "Job submitted successfully",
  "data": {
    "request_id": "123",
    "status": "PROCESSING"
  }
}

// Async poll COMPLETED - ĐÚNG format
{
  "error_code": 0,
  "message": "Transcription completed",
  "data": {
    "request_id": "123",
    "status": "COMPLETED",
    "transcription": "...",
    "duration": 45.5,
    "confidence": 0.98,
    "processing_time": 12.3
  }
}

// Error response - ĐÚNG format
{
  "error_code": 1,
  "message": "Job not found",
  "errors": {
    "request_id": "Job 123 does not exist or has expired"
  }
}
```

## Impact

- Affected specs: `stt-api`
- Affected code:
  - `internal/api/schemas/common_schemas.py` - Thêm `errors` field
  - `internal/api/schemas/async_transcribe_schemas.py` - Wrap trong StandardResponse
  - `internal/api/routes/async_transcribe_routes.py` - Return StandardResponse
  - `internal/api/routes/transcribe_routes.py` - Return StandardResponse
  - `internal/api/utils.py` - Thêm helper functions
  - `tests/test_async_transcribe.py` - Update assertions
  - `document/ASYNC_API_INTEGRATION.md` - Update examples

## Breaking Change

**YES** - Client code cần update để parse `data` field thay vì top-level fields.
