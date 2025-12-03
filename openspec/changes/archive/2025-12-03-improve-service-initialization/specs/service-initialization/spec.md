# Service Initialization Specification

## ADDED Requirements

### Requirement: Eager Model Initialization
The system SHALL initialize the Whisper model at service startup rather than on first request to ensure fast startup validation and consistent request latency.

#### Scenario: Initialize model at startup
**Given** the API service is starting up  
**And** Whisper model files are available  
**When** the lifespan context manager executes  
**Then** the system SHALL call `bootstrap_container()` to initialize DI container  
**And** the system SHALL explicitly resolve `ITranscriber` to trigger model loading  
**And** the system SHALL log model initialization start time  
**And** the system SHALL log model initialization completion with duration  
**And** the system SHALL log estimated memory usage for the loaded model

#### Scenario: Fail fast on missing model
**Given** the API service is starting up  
**And** Whisper model files are NOT available  
**When** the lifespan context manager attempts to initialize the model  
**Then** the system SHALL raise a clear error indicating which model files are missing  
**And** the system SHALL log the error with full context (model size, expected path, etc.)  
**And** the system SHALL exit with non-zero status code  
**And** the system SHALL NOT accept any HTTP requests

#### Scenario: Fail fast on corrupted model
**Given** the API service is starting up  
**And** Whisper model files exist but are corrupted  
**When** the lifespan context manager attempts to initialize the model  
**Then** the system SHALL detect the corruption during `whisper_init_from_file()`  
**And** the system SHALL raise a clear error indicating model corruption  
**And** the system SHALL log the error with file path and size information  
**And** the system SHALL exit with non-zero status code

#### Scenario: First request has no loading delay
**Given** the API service has started successfully  
**And** the Whisper model is already loaded  
**When** the first transcription request arrives  
**Then** the system SHALL NOT load the model again  
**And** the request SHALL complete without model loading overhead  
**And** the response time SHALL be consistent with subsequent requests

## ADDED Requirements

### Requirement: Health Check Validation
The system SHALL include model initialization status in health check responses.

#### Scenario: Health check includes model status
**Given** the API service is running  
**And** the Whisper model is initialized  
**When** a health check request is received at `/health`  
**Then** the response SHALL include `model_initialized: true`  
**And** the response SHALL include `model_size` (base/small/medium)  
**And** the response SHALL include `model_loaded_at` timestamp  
**And** the response SHALL include HTTP status 200

#### Scenario: Health check before model initialization (edge case)
**Given** the API service is starting up  
**And** the model initialization is still in progress  
**When** a health check request is received  
**Then** the response SHALL indicate initialization in progress  
**Or** the request SHALL be rejected until startup completes

### Requirement: Dependency Injection Container
The system SHALL ensure the DI container bootstrap is idempotent and properly initializes all singletons.

#### Scenario: Container bootstrap is idempotent
**Given** the DI container has been bootstrapped once  
**When** `bootstrap_container()` is called again  
**Then** the system SHALL detect existing initialization  
**And** the system SHALL NOT reinitialize singletons  
**And** the system SHALL log that container is already initialized

#### Scenario: Container logs all registrations
**Given** the DI container is being bootstrapped  
**When** each interface implementation is registered  
**Then** the system SHALL log each registration with interface and implementation names  
**And** the system SHALL log successful completion of bootstrap

#### Scenario: Singleton resolution after eager initialization
**Given** the model has been eagerly initialized at startup  
**When** a request handler resolves `ITranscriber` from the container  
**Then** the system SHALL return the same instance that was initialized at startup  
**And** the system SHALL NOT create a new instance  
**And** the system SHALL NOT reload the model
