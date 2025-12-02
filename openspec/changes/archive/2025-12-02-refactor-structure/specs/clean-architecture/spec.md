## MODIFIED Requirements

### Requirement: Clean Architecture Layer Separation

The system SHALL organize code into distinct architectural layers following Clean Architecture principles:
- **Command Layer** (`cmd/`): Entry points for services
- **Internal Layer** (`internal/`): Service implementation (routes, consumers)
- **Core Layer** (`core/`): Shared configuration and utilities
- **Interface Layer** (`interfaces/`): Abstract interfaces for dependency injection
- **Models Layer** (`models/`): Data models and Pydantic schemas
- **Services Layer** (`services/`): Business logic
- **Infrastructure Layer** (`infrastructure/`): External system integrations

#### Scenario: Interface layer provides abstractions
- **WHEN** a service needs to use an external system (e.g., Whisper transcriber)
- **THEN** the service SHALL depend on an interface from `interfaces/`
- **AND** the concrete implementation SHALL be in `infrastructure/`

#### Scenario: Dependency injection via container
- **WHEN** the application starts
- **THEN** the system SHALL register all interface implementations in `core/container.py`
- **AND** services SHALL resolve dependencies through the container

#### Scenario: Infrastructure implementations
- **WHEN** integrating with external systems (Whisper, FFmpeg, etc.)
- **THEN** implementations SHALL be placed in `infrastructure/<system>/`
- **AND** implementations SHALL implement the corresponding interface from `interfaces/`

### Requirement: Import Organization

The system SHALL use absolute imports from project root for all internal modules.

#### Scenario: Consistent import paths
- **WHEN** importing internal modules
- **THEN** imports SHALL use absolute paths (e.g., `from interfaces.transcriber import ITranscriber`)
- **AND** relative imports SHALL NOT be used for cross-layer dependencies
