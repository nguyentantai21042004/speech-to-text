## ADDED Requirements

### Requirement: Logging Usage Standards
The system SHALL force the use of modern Python logging patterns (f-strings or Loguru format-style) and reject legacy printf-style formatting.

#### Scenario: F-string usage (Recommended)
- **Given** a variable `user_id="123"`
- **When** logging an info message
- **Then** the code SHALL use f-string: `logger.info(f"User {user_id} logged in")`
- **And** the code SHALL NOT use printf-style: `logger.info("User %s logged in", user_id)`

#### Scenario: Loguru format-style (Supported)
- **Given** a variable `count=42`
- **When** logging a debug message
- **Then** the code SHALL use brace formatting: `logger.debug("Processing count={}", count)`
- **And** the code SHALL NOT use printf-style: `logger.debug("Processing count=%d", count)`

#### Scenario: Exception Logging
- **Given** an exception `e` occurs
- **When** logging the error
- **Then** the code SHALL use `logger.exception` or `logger.error` with f-string: `logger.error(f"Failed: {e}")`
- **And** the code SHALL NOT use printf-style: `logger.error("Failed: %s", e)`
