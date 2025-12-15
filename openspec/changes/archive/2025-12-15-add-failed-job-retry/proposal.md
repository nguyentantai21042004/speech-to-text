# Change: Add Retry Mechanism for Failed Transcription Jobs

## Why

STT Service hiện tại **không thể xử lý lại** các request transcription đã từng thất bại. Khi Crawler gửi request cho cùng một video (cùng `request_id`), hệ thống trả về kết quả FAILED cũ từ Redis thay vì xử lý lại.

**Nguyên nhân gốc rễ:**

- `request_id` được tạo từ MD5 hash của `media_url` (phía client)
- Cùng video → Cùng URL → Cùng `request_id`
- Idempotency check block mọi request trùng ID, kể cả khi job đã FAILED

**Hậu quả trên Production:**

- ~75% request bị block bởi stale FAILED jobs trong Redis
- Không có cơ chế retry
- Transcription service không hoạt động đúng chức năng

## What Changes

- **MODIFIED**: Logic `submit_job()` trong `AsyncTranscriptionService` để cho phép retry khi job đã FAILED
- Khi phát hiện job đã tồn tại với status `FAILED`:
  - Xóa job cũ khỏi Redis
  - Tạo job mới và xử lý lại
- Giữ nguyên behavior cho `PROCESSING` và `COMPLETED`:
  - `PROCESSING`: Trả về status hiện tại (đang xử lý)
  - `COMPLETED`: Trả về kết quả cũ (không xử lý lại - idempotency)

## Impact

- **Affected specs**: `stt-api`
- **Affected code**:
  - `services/async_transcription.py` - Logic submit_job
- **Risk**: Low - Thay đổi nhỏ, backward compatible
- **Effort**: ~1-2 hours implementation + testing
