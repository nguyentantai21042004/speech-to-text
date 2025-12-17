## 1. Analysis & Preparation
- [x] 1.1 Scan codebase for printf-style logging patterns (`%s`, `%d`, `%f` inside logger calls).
- [x] 1.2 Identify any custom logging wrappers that might need adjustment.

## 2. Implementation
- [x] 2.1 Refactor printf-style logs to f-strings in `core/`.
- [x] 2.2 Refactor printf-style logs to f-strings in `services/`.
- [x] 2.3 Refactor printf-style logs to f-strings in `infrastructure/`.
- [x] 2.4 Refactor printf-style logs to f-strings in other directories (`internal`, `cmd`, etc.).

## 3. Verification
- [x] 3.1 Run `make test` to ensure no functionality is broken.
- [x] 3.2 Verify logs in `app.log` (if available) or console output to ensure formatting is correct.
- [x] 3.3 Grep codebase again to confirm 0 occurrences of printf-style logging.
