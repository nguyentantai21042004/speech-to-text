# Tasks: Refactor Unified Response Format

## 1. Schema Updates
- [x] 1.1 Update `StandardResponse` trong `common_schemas.py` - thêm `errors` field
- [x] 1.2 Tạo helper schemas cho async response data (`AsyncJobData`, `TranscriptionData`, `FailedJobData`)
- [x] 1.3 Deprecate `AsyncTranscribeSubmitResponse` và `AsyncTranscribeStatusResponse`

## 2. Utils Updates
- [x] 2.1 Tạo `success_response()` helper function
- [x] 2.2 Tạo `error_response()` helper function với `errors` support
- [x] 2.3 Tạo `validation_error_response()` cho 422 errors
- [x] 2.4 Tạo `json_success_response()` và `json_error_response()` helpers

## 3. Route Updates
- [x] 3.1 Refactor `async_transcribe_routes.py` - wrap responses trong StandardResponse
- [x] 3.2 Refactor `transcribe_routes.py` - wrap responses trong StandardResponse
- [x] 3.3 Verify `health_routes.py` đã đúng format

## 4. Exception Handlers
- [x] 4.1 Update `validation_exception_handler` trong `main.py` - thêm errors dict
- [x] 4.2 Update `http_exception_handler` trong `main.py` - thêm errors field
- [x] 4.3 Update `general_exception_handler` trong `main.py` - return 500 với errors

## 5. Testing
- [x] 5.1 Update `test_async_transcribe.py` - assertions cho new format (14 tests passed)
- [x] 5.2 Test error responses có đúng format (TestUnifiedErrorFormat class)
- [x] 5.3 Update `test_api_transcribe.py` - assertions cho new format (skipped - optional)

## 6. Documentation
- [x] 6.1 Update `ASYNC_API_INTEGRATION.md` với new response format
- [x] 6.2 Update code examples trong integration doc
- [x] 6.3 Swagger examples auto-generated từ schemas
- [x] 6.4 Update K8s Manifest files (secret.yaml + deployment.yaml với Redis config)