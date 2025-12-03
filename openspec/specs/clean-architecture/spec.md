# clean-architecture Specification

## Purpose
TBD - created by archiving change refactor-structure. Update Purpose after archive.
## Requirements
### Requirement: Domain Layer Independence
The domain layer MUST remain independent of infrastructure concerns to ensure testability and maintainability.

#### Scenario: Domain Independence
The domain layer MUST NOT depend on infrastructure or external libraries (except standard library and pydantic/dataclasses).
- **Given** a domain entity or service in `domain/`
- **When** it is implemented
- **Then** it must not import from `adapters/`, `repositories/` (legacy), or `infrastructure/`.

### Requirement: Dependency Injection Pattern
The system MUST use dependency injection to manage dependencies, facilitating loose coupling.

#### Scenario: Dependency Injection
All services and use cases MUST receive their dependencies via constructor injection (defined as Ports).
- **Given** a Use Case class
- **When** it is initialized
- **Then** it receives dependencies typed as Ports (e.g., `TaskRepositoryPort`) rather than concrete implementations.

### Requirement: Port and Adapter Pattern
External interactions MUST be abstracted via Ports and implemented by Adapters.

#### Scenario: Port Definitions
All external I/O (Database, Queue, Storage, External APIs) MUST have an abstract interface defined in `ports/`.
- **Given** a need to access an external system
- **When** defining the interaction
- **Then** an abstract base class (ABC) or Protocol must be defined in `ports/` defining the methods.

#### Scenario: Adapter Implementation
Infrastructure adapters MUST implement the corresponding Port interfaces.
- **Given** a concrete adapter (e.g., `MongoTaskRepository`)
- **When** it is defined
- **Then** it must inherit from and implement the `TaskRepositoryPort`.

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

