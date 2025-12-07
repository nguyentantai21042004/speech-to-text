# Architecture Documentation - Analytics Engine

## Overview

This document describes the project structure and architectural patterns used in the Analytics Engine service. This structure can be replicated across other repositories for consistency.

## Directory Structure

```
analytics_engine/
├── cmd/                        # Entry Points (Command Layer)
│   ├── api/                    # API service entry point
│   │   ├── __init__.py
│   │   └── main.py            # Loads config, initializes instances, starts FastAPI
│   └── consumer/               # Consumer service entry point
│       ├── __init__.py
│       └── main.py            # Loads config, initializes instances, starts consumer
│
├── internal/                   # Internal Implementation Layer
│   ├── api/                    # API route registration
│   │   ├── __init__.py
│   │   └── main.py            # Registers FastAPI routes and middleware
│   └── consumers/              # Consumer registration
│       ├── __init__.py
│       └── main.py            # Registers message queue consumers
│
├── core/                       # Core Shared Layer
│   ├── __init__.py
│   ├── config.py              # Application settings (Pydantic Settings)
│   ├── logger.py              # Logging configuration (Loguru)
│   ├── constants.py           # Application constants
│   ├── dependencies.py        # Dependency injection
│   └── errors.py              # Custom exceptions
│
├── models/                     # Data Models Layer
│   ├── __init__.py
│   ├── database.py            # SQLAlchemy database models
│   └── schemas.py             # Pydantic schemas (API DTOs) - future
│
├── interfaces/                 # Interface Layer (Abstractions)
│   ├── __init__.py
│   ├── repository.py          # Abstract repository interface
│   ├── storage.py             # Abstract storage interface (MinIO)
│   ├── queue.py               # Abstract message queue interface
│   └── cache.py               # Abstract cache interface (Redis)
│
├── repositories/               # Repository Implementations
│   ├── __init__.py
│   └── analytics_repository.py # PostAnalytics repository (future)
│
├── services/                   # Business Logic Layer
│   └── (future: analytics_service.py, etc.)
│
├── infrastructure/             # Infrastructure Implementations
│   ├── storage/               # Storage implementations (MinIO)
│   ├── queue/                 # Queue implementations (RabbitMQ)
│   └── cache/                 # Cache implementations (Redis)
│
├── migrations/                 # Database Migrations (Alembic)
│   ├── versions/
│   └── env.py                 # Alembic environment configuration
│
├── document/                   # Documentation
├── openspec/                   # OpenSpec specifications
├── pyproject.toml             # Python project configuration (uv)
├── docker-compose.dev.yml     # Development environment
├── Makefile                   # Common commands
└── README.md
```

## Architectural Layers

### 1. Command Layer (`cmd/`)

**Purpose**: Entry points for services. Each service has its own directory.

**Responsibilities**:

- Load application configuration from `core.config`
- Initialize logging from `core.logger`
- Bootstrap dependency injection container (if applicable)
- Import and start the internal implementation
- Handle process lifecycle (startup, shutdown)

**Pattern**:

```python
# cmd/analytics_api/main.py
from core.config import settings
from core.logger import logger
from internal.api.main import app

def create_app():
    # Load config, initialize instances
    logger.info(f"Starting {settings.service_name}")
    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("cmd.analytics_api.main:app", ...)
```

**Key Points**:

- One entry point per service (API, Consumer, Worker, etc.)
- Minimal logic - just wiring and initialization
- Uses `internal/` for actual implementation

### 2. Internal Layer (`internal/`)

**Purpose**: Internal implementation of services. Registers routes, consumers, and handlers.

**Responsibilities**:

- Register API routes (FastAPI routers)
- Register message queue consumers
- Define middleware and exception handlers
- Implement service-specific logic

**Pattern**:

```python
# internal/api/main.py
from fastapi import FastAPI

app = FastAPI(title="Analytics Engine")

# Register routes
@app.get("/health")
async def health():
    return {"status": "healthy"}

# More route registrations...
```

**Key Points**:

- Contains the actual service implementation
- Separated by service type (api, consumers, workers)
- Does NOT handle initialization - that's `cmd/`'s job

### 3. Core Layer (`core/`)

**Purpose**: Shared core functionality used across all services.

**Components**:

#### `config.py` - Application Settings

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    service_name: str = "analytics-engine"
    database_url: str = "postgresql://..."
    # ...

settings = Settings()

def get_settings() -> Settings:
    return settings
```

#### `logger.py` - Logging Configuration

```python
from loguru import logger

def setup_logger():
    # Configure loguru handlers
    pass

setup_logger()
```

**Key Points**:

- Shared across all services
- No service-specific logic
- Provides common utilities and configurations
- Does NOT contain models (moved to `models/` layer)

### 4. Models Layer (`models/`)

**Purpose**: Data models and schemas.

**Components**:

#### `database.py` - SQLAlchemy Models

```python
from sqlalchemy import Column, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class PostAnalytics(Base):
    __tablename__ = "post_analytics"
    id = Column(String(50), primary_key=True)
    # ...
```

#### `schemas.py` - Pydantic Schemas (Future)

```python
from pydantic import BaseModel

class PostAnalyticsCreate(BaseModel):
    project_id: str
    platform: str
    # ...
```

**Key Points**:

- Centralized location for all data models
- Separate database models from API schemas
- Easy to import: `from models.database import PostAnalytics`

### 5. Interfaces Layer (`interfaces/`)

**Purpose**: Abstract base classes for dependency injection.

**Responsibilities**:

- Define contracts for repositories
- Define contracts for external services (storage, queue, cache)
- Enable dependency injection and testing

**Pattern**:

```python
# interfaces/repository.py
from abc import ABC, abstractmethod

class IAnalyticsRepository(ABC):
    @abstractmethod
    async def create(self, analytics: PostAnalytics) -> PostAnalytics:
        pass

    @abstractmethod
    async def get_by_id(self, analytics_id: str) -> Optional[PostAnalytics]:
        pass
```

**Key Points**:

- All interfaces use ABC (Abstract Base Class)
- Enables easy mocking for tests
- Decouples business logic from infrastructure

### 6. Repositories Layer (`repositories/`)

**Purpose**: Implement data access patterns.

**Responsibilities**:

- Implement `IAnalyticsRepository` interface
- Handle database operations
- Use SQLAlchemy for queries

**Pattern** (Future):

```python
# repositories/analytics_repository.py
from interfaces.repository import IAnalyticsRepository
from models.database import PostAnalytics

class AnalyticsRepository(IAnalyticsRepository):
    def __init__(self, db_session):
        self.db = db_session

    async def create(self, analytics: PostAnalytics) -> PostAnalytics:
        self.db.add(analytics)
        await self.db.commit()
        return analytics
```

**Key Points**:

- Implements interfaces from `interfaces/`
- Handles all database operations
- Can be easily swapped for testing

### 7. Services Layer (`services/`)

**Purpose**: Business logic and domain services.

**Responsibilities**:

- Implement business logic
- Orchestrate operations
- Use dependency injection for infrastructure

**Pattern** (Future):

```python
# services/analytics_service.py
class AnalyticsService:
    def __init__(self, storage, database):
        self.storage = storage
        self.database = database

    def process_post(self, post_id):
        # Business logic here
        pass
```

#### 7.1 Analytics Orchestrator (`services/analytics/orchestrator.py`)

**Role**: Central coordinator for the full analytics pipeline.

**Pipeline**:

- Input: A single Atomic JSON post (`meta`, `content`, `interaction`, `author`, `comments`).
- Steps:
  1. **Preprocessing** (`TextPreprocessor`):
     - Merge caption, transcription, and top comments.
     - Normalize Vietnamese text and compute noise stats (spam, too short, etc.).
  2. **Intent** (`IntentClassifier`):
     - Classify post intent and produce a `should_skip` signal.
  3. **Skip Logic**:
     - Combines preprocessor stats + intent to decide whether to skip spam/noise/seeding posts.
     - Skipped posts still persist a minimal `PostAnalytics` record with neutral sentiment and low risk.
  4. **Keyword Extraction** (`KeywordExtractor`):
     - Hybrid dictionary + SpaCy-YAKE extraction with aspect mapping.
  5. **Sentiment** (`SentimentAnalyzer`):
     - Overall + aspect-based sentiment using PhoBERT with smart context windowing.
  6. **Impact & Risk** (`ImpactCalculator`):
     - Compute engagement, reach, impact score (0–100), and risk level (LOW→CRITICAL).
  7. **Persistence** (`AnalyticsRepository`):
     - Save final `PostAnalytics` payload (overall, aspects, keywords, impact, raw metrics).

**Entry Points**:

- **Queue Consumer** (`internal/consumers/main.py`):
  - Reads messages from RabbitMQ.
  - If message contains `data_ref`:
    - Uses `MinioAdapter` (`infrastructure/storage/minio_client.py`) to download the Atomic JSON from MinIO.
  - Otherwise treats the message body as a full Atomic JSON post.
  - Creates a DB session (via `settings.database_url_sync` and `models.database.Base`), wraps it with `AnalyticsRepository`, and delegates processing to:
    - `AnalyticsOrchestrator.process_post(post_data)`.
- **Dev/Test API** (`internal/api/routes/orchestrator.py`):
  - `POST /dev/process-post-direct`
  - Accepts a full Atomic JSON body directly from the client (bypasses MinIO and queue).
  - Constructs an `AnalyticsRepository` with a sync session and an optional `SentimentAnalyzer` (if PhoBERT is available).
  - Delegates to `AnalyticsOrchestrator.process_post(post_data)` and returns the final analytics payload for debugging.

**End-to-End Flow**:

```text
MinIO (Atomic JSON) ──▶ internal/consumers/main.py
    │                         │
    │                         ├─▶ MinioAdapter.download_json()
    │                         └─▶ AnalyticsOrchestrator.process_post()
    │                                  └─▶ AnalyticsRepository.save() ──▶ PostgreSQL (PostAnalytics)
    │
    └──(dev/test)──▶ internal/api/routes/orchestrator.py (POST /dev/process-post-direct)
                              └─▶ AnalyticsOrchestrator.process_post()
                                       └─▶ AnalyticsRepository.save() ──▶ PostgreSQL (PostAnalytics)
```

### 5. Migrations Layer (`migrations/`)

**Purpose**: Database schema versioning with Alembic.

**Configuration**:

```python
# migrations/env.py
from core.models import Base
from core.config import settings

target_metadata = Base.metadata
config.set_main_option("sqlalchemy.url", settings.database_url_sync)
```

## Dependency Flow

```
cmd/analytics_api/main.py
    ↓ imports
internal/api/main.py
    ↓ uses
core/config.py, core/logger.py, core/models.py
    ↓ uses
services/ (business logic)
```

## Key Principles

### 1. Separation of Concerns

- **cmd/**: Process management and initialization
- **internal/**: Service implementation
- **core/**: Shared utilities
- **services/**: Business logic

### 2. Dependency Injection

- Configuration loaded once in `cmd/`
- Passed down to `internal/` and `services/`
- No global state in business logic

### 3. Testability

- `internal/` and `services/` can be tested independently
- Mock `core/` components for unit tests
- Integration tests use `cmd/` entry points

### 4. Scalability

- Easy to add new services (new `cmd/` entry point)
- Easy to add new routes (register in `internal/api/`)
- Easy to add new consumers (register in `internal/consumers/`)

## Configuration Management

### Environment Variables

Managed via `.env` file and `core/config.py`:

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/db

# API
API_HOST=0.0.0.0
API_PORT=8000

# Logging
LOG_LEVEL=INFO
DEBUG=false
```

### Settings Class

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",  # Ignore extra fields
    )

    database_url: str
    api_host: str = "0.0.0.0"
    # ...
```

## Development Workflow

### 1. Start Development Environment

```bash
make dev-up  # Starts Docker services
```

### 2. Run Services

```bash
make run-analytics-api       # Start API
make run-analytics-consumer  # Start consumer
```

### 3. Database Migrations

```bash
make db-migrate  # Create migration
make db-upgrade  # Apply migrations
```

## Adding a New Service

### Step 1: Create Entry Point

```bash
mkdir -p cmd/new_service
touch cmd/new_service/__init__.py
touch cmd/new_service/main.py
```

### Step 2: Create Internal Implementation

```bash
mkdir -p internal/new_service
touch internal/new_service/__init__.py
touch internal/new_service/main.py
```

### Step 3: Implement Entry Point

```python
# cmd/new_service/main.py
from core.config import settings
from core.logger import logger
from internal.new_service.main import run_service

if __name__ == "__main__":
    logger.info(f"Starting {settings.service_name}")
    run_service()
```

### Step 4: Implement Service Logic

```python
# internal/new_service/main.py
def run_service():
    # Service implementation
    pass
```

### Step 5: Add Makefile Command

```makefile
run-new-service:
	PYTHONPATH=. uv run cmd/new_service/main.py
```

## Technology Stack

- **Language**: Python 3.10+
- **Package Manager**: `uv`
- **Web Framework**: FastAPI
- **Database**: PostgreSQL
- **ORM**: SQLAlchemy
- **Migrations**: Alembic
- **Logging**: Loguru
- **Configuration**: Pydantic Settings
- **Message Queue**: RabbitMQ (future)
- **Storage**: MinIO (future)

## Best Practices

### 1. Import Organization

```python
# Standard library
import os
import sys

# Third-party
from fastapi import FastAPI
from sqlalchemy import Column

# Local - core
from core.config import settings
from core.logger import logger

# Local - internal
from internal.api.main import app

# Local - services
from services.analytics_service import AnalyticsService
```

### 2. Error Handling

- Use custom exceptions from `core/errors.py`
- Log errors with context using `core/logger.py`
- Return consistent error responses

### 3. Configuration

- All configuration in `core/config.py`
- Use environment variables
- Provide sensible defaults
- Validate settings on startup

### 4. Logging

- Use structured logging
- Include context (service, function, line)
- Different log levels for different environments
- Separate error logs

## Replication Guide

To replicate this structure in a new repository:

1. **Copy Structure**:

   ```bash
   mkdir -p cmd/service_name internal/service_name core services migrations
   ```

2. **Copy Core Files**:

   - `core/config.py` (adapt settings)
   - `core/logger.py` (reuse as-is)
   - `core/models.py` (define your models)

3. **Create Entry Point**:

   - `cmd/service_name/main.py` (follow pattern above)

4. **Create Internal Implementation**:

   - `internal/service_name/main.py` (implement your service)

5. **Setup Dependencies**:

   - Copy `pyproject.toml` structure
   - Run `uv sync`

6. **Setup Database**:

   - Copy `migrations/env.py` pattern
   - Run `alembic init migrations`

7. **Setup Development Environment**:
   - Copy `docker-compose.dev.yml`
   - Copy `Makefile` patterns

This architecture ensures consistency, maintainability, and scalability across all services.
