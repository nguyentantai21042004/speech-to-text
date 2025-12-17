# logging-configuration Specification

## Purpose
TBD - created by archiving change improve-service-initialization. Update Purpose after archive.
## Requirements
### Requirement: Centralized Logging Configuration
The system SHALL provide a centralized logging configuration through `core/logger.py` that all components use for consistent, structured logging.

#### Scenario: Logger initialization
**Given** any Python module in the application  
**When** the module imports logger from `core.logger`  
**Then** the logger SHALL be pre-configured with appropriate handlers  
**And** the logger SHALL use Loguru for structured logging  
**And** the logger SHALL respect LOG_LEVEL environment variable

#### Scenario: Standard library logging interception
**Given** third-party libraries use Python's standard `logging` module  
**When** the application starts  
**Then** the system SHALL intercept standard library logging  
**And** the system SHALL route all logs through Loguru  
**And** the system SHALL maintain consistent log format across all sources

#### Scenario: Third-party library logger configuration
**Given** libraries like httpx, urllib3, boto3 have their own loggers  
**When** the application configures logging  
**Then** the system SHALL set appropriate log levels for each library  
**And** the system SHALL suppress verbose debug logs from libraries  
**And** the system SHALL allow important warnings and errors through

### Requirement: Script Logging Standardization
The system SHALL provide a `configure_script_logging()` function for standalone scripts to use structured logging instead of print statements.

#### Scenario: Script uses structured logging
**Given** a standalone script in `scripts/` directory  
**When** the script imports and calls `configure_script_logging()`  
**Then** the logger SHALL be configured with console output only (no file logging)  
**And** the logger SHALL use a simplified format suitable for scripts  
**And** the logger SHALL respect SCRIPT_LOG_LEVEL environment variable

#### Scenario: Replace print statements
**Given** a script that previously used print() statements  
**When** the script is migrated to use logger  
**Then** informational messages SHALL use `logger.info()`  
**And** error messages SHALL use `logger.error()`  
**And** debug messages SHALL use `logger.debug()`  
**And** warnings SHALL use `logger.warning()`  
**And** the output SHALL include timestamps and log levels

### Requirement: Log Format Configuration
The system SHALL support multiple log formats for different deployment environments.

#### Scenario: Console format for development
**Given** LOG_FORMAT is set to "console" or not set  
**When** the application logs a message  
**Then** the output SHALL use colored, human-readable format  
**And** the output SHALL include timestamp, level, module, function, line, and message  
**And** the output SHALL use ANSI color codes for different log levels

#### Scenario: JSON format for production
**Given** LOG_FORMAT is set to "json"  
**When** the application logs a message  
**Then** the output SHALL be valid JSON  
**And** the JSON SHALL include fields: timestamp, level, module, function, line, message  
**And** the JSON SHALL be parseable by log aggregation tools (ELK, Datadog, etc.)

#### Scenario: File logging configuration
**Given** LOG_FILE_ENABLED is set to true (default)  
**When** the application starts  
**Then** the system SHALL create `logs/` directory if it doesn't exist  
**And** the system SHALL write logs to `logs/app.log`  
**And** the system SHALL write errors to `logs/error.log`  
**And** the system SHALL rotate logs at 100MB  
**And** the system SHALL retain logs for 30 days  
**And** the system SHALL compress rotated logs

### Requirement: Log Level Control
The system SHALL support fine-grained log level control for different components.

#### Scenario: Application log level
**Given** LOG_LEVEL environment variable is set  
**When** the application starts  
**Then** the console handler SHALL use the configured log level  
**And** valid levels SHALL be: DEBUG, INFO, WARNING, ERROR, CRITICAL  
**And** invalid levels SHALL default to INFO with a warning

#### Scenario: Script log level
**Given** SCRIPT_LOG_LEVEL environment variable is set  
**When** a script calls `configure_script_logging()`  
**Then** the script logger SHALL use SCRIPT_LOG_LEVEL  
**And** if SCRIPT_LOG_LEVEL is not set, it SHALL default to INFO

#### Scenario: Library log level suppression
**Given** third-party libraries generate verbose logs  
**When** the application configures logging  
**Then** httpx logs SHALL be set to WARNING level  
**And** urllib3 logs SHALL be set to WARNING level  
**And** boto3 logs SHALL be set to INFO level  
**And** this SHALL reduce noise in application logs

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

