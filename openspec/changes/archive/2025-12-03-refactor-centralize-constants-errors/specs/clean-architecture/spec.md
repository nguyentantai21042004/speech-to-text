# Clean Architecture Specification

## ADDED Requirements

### Requirement: Centralized Constants
System-wide constants MUST be defined in a centralized location in the Core layer to ensure consistency and maintainability.

#### Scenario: Whisper Model Configuration
**Given** the Whisper model configurations (paths, sizes)  
**When** they are accessed by different modules (downloader, adapter)  
**Then** they MUST be imported from `core/constants.py`  
**And** they MUST NOT be duplicated in infrastructure modules

#### Scenario: HTTP Configuration
**Given** HTTP client settings (timeouts, limits)  
**When** they are used by HTTP adapters  
**Then** they MUST be imported from `core/constants.py`

### Requirement: Centralized Error Definitions
Domain and application errors MUST be defined in the Core layer to provide a unified error hierarchy.

#### Scenario: Infrastructure Errors
**Given** an error occurring in an infrastructure adapter (e.g., LibraryLoadError)  
**When** the error is raised  
**Then** it MUST be an instance of a class defined in `core/errors.py`  
**And** it SHOULD inherit from a base `STTError`
