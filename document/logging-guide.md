# Logging Guide - Loguru Best Practices

Hướng dẫn chi tiết về cách sử dụng Loguru logging trong các Python services.

## Quick Start

```python
from core.logger import logger

# ✅ ĐÚNG - Sử dụng f-string
logger.info(f"Processing post_id={post_id}")
logger.error(f"Failed to process {item_id}: {error}")

# ✅ ĐÚNG - Sử dụng Loguru format-style
logger.info("Processing post_id={}", post_id)
logger.warning("Unexpected value: expected={}, actual={}", expected, actual)

# ❌ SAI - Printf-style KHÔNG hoạt động với Loguru
logger.info("Processing post_id=%s", post_id)  # Output: "Processing post_id=%s"
logger.error("Error: %s", error)  # Output: "Error: %s"
```

## Tại sao không dùng printf-style?

Loguru khác với Python's standard `logging` module:

| Feature             | Standard logging | Loguru                 |
| ------------------- | ---------------- | ---------------------- |
| Printf-style (`%s`) | ✅ Supported     | ❌ Not supported       |
| Format-style (`{}`) | ❌ Not supported | ✅ Supported           |
| F-strings           | ✅ Works         | ✅ Works (recommended) |

## Cú pháp Loguru

### 1. F-strings (Khuyến nghị)

```python
# Simple values
logger.info(f"User {user_id} logged in")
logger.debug(f"Processing batch: size={batch_size}, index={batch_index}")

# With formatting
logger.info(f"Completed in {duration:.2f}ms")
logger.info(f"Progress: {progress:.1%}")

# Complex objects
logger.debug(f"Request payload: {payload}")
```

### 2. Loguru Format-style

```python
# Positional arguments
logger.info("User {} logged in", user_id)
logger.debug("Processing batch: size={}, index={}", batch_size, batch_index)

# Keyword arguments
logger.info("User {uid} logged in", uid=user_id)
logger.debug("Batch: size={size}, index={idx}", size=batch_size, idx=batch_index)
```

### 3. Structured Logging với Extra Data

```python
# Bind context data
logger.bind(job_id=job_id, batch_index=batch_index).info("Processing started")

# Or use opt() for one-time extra data
logger.opt(record=True).info("Event processed")
```

## Log Levels

| Level      | Khi nào sử dụng                        | Ví dụ                                         |
| ---------- | -------------------------------------- | --------------------------------------------- |
| `DEBUG`    | Chi tiết diagnostic, chỉ cần khi debug | `logger.debug(f"SQL query: {query}")`         |
| `INFO`     | Operational events bình thường         | `logger.info(f"User {user_id} created")`      |
| `WARNING`  | Unexpected nhưng đã xử lý được         | `logger.warning(f"Retry attempt {n}/3")`      |
| `ERROR`    | Lỗi cần attention                      | `logger.error(f"Failed to save: {exc}")`      |
| `CRITICAL` | System failures                        | `logger.critical("Database connection lost")` |

## Exception Logging

```python
try:
    process_data(data)
except Exception as exc:
    # Log với traceback
    logger.exception(f"Failed to process data: {exc}")

    # Hoặc log error không có traceback
    logger.error(f"Processing failed: {exc}")

    # Với context
    logger.opt(exception=True).error(f"Error in batch {batch_id}")
```

## Configuration

### Environment Variables

```bash
# Log level cho console output (default: INFO)
LOG_LEVEL=DEBUG

# Debug mode (fallback nếu LOG_LEVEL không set)
DEBUG=true
```

### File Outputs

Logger tự động tạo 2 file trong `logs/`:

| File        | Level | Mục đích               |
| ----------- | ----- | ---------------------- |
| `app.log`   | DEBUG | Tất cả logs            |
| `error.log` | ERROR | Chỉ errors và critical |

Cả hai file đều:

- Rotate khi đạt 100MB
- Giữ lại 30 ngày
- Nén bằng zip

## Patterns Thường Dùng

### Request/Response Logging

```python
logger.info(f"Received request: method={method}, path={path}")
logger.info(f"Response: status={status_code}, duration={duration_ms}ms")
```

### Batch Processing

```python
logger.info(f"Starting batch: job_id={job_id}, size={batch_size}")
for i, item in enumerate(items):
    logger.debug(f"Processing item {i+1}/{len(items)}: id={item.id}")
logger.info(f"Batch completed: success={success_count}, errors={error_count}")
```

### Database Operations

```python
logger.debug(f"Executing query: {query[:100]}...")
logger.info(f"Saved {count} records to {table_name}")
logger.error(f"Database error: {exc}")
```

### External Service Calls

```python
logger.info(f"Calling {service_name}: endpoint={endpoint}")
logger.debug(f"Request payload: {payload}")
logger.info(f"Response from {service_name}: status={status}, latency={latency}ms")
```

## Migration từ Printf-style

Nếu bạn có code cũ dùng printf-style, convert như sau:

```python
# TRƯỚC
logger.info("Processing %s with %d items", job_id, count)
logger.warning("Value %.2f exceeds threshold", value)

# SAU (f-string)
logger.info(f"Processing {job_id} with {count} items")
logger.warning(f"Value {value:.2f} exceeds threshold")

# SAU (format-style)
logger.info("Processing {} with {} items", job_id, count)
logger.warning("Value {:.2f} exceeds threshold", value)
```

## Import

```python
# Từ core module
from core.logger import logger

# Hoặc trực tiếp từ loguru (nếu đã setup)
from loguru import logger
```

## Checklist cho Code Review

- [ ] Không có printf-style formatting (`%s`, `%d`, `%f`)
- [ ] Sử dụng f-string hoặc Loguru format-style
- [ ] Log level phù hợp với severity
- [ ] Không log sensitive data (passwords, tokens, PII)
- [ ] Exception logging có đủ context
