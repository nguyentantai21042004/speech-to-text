.PHONY: help install dev-install run-api run-queue run-scheduler setup-models setup-model setup-model-tiny setup-model-base setup-model-small setup-model-medium setup-model-large setup-whisper setup-whisper-custom setup-artifacts setup-artifacts-small setup-artifacts-medium docker-build docker-up docker-down docker-logs clean clean-old test test-library test-integration format lint upgrade

# ==============================================================================
# HELPERS
# ==============================================================================
help:
	@echo "Available commands (Managed by uv):"
	@echo ""
	@echo "DEPENDENCIES:"
	@echo "  make install                 - Install dependencies (Sync environment)"
	@echo "  make dev-install             - Install all dependencies including dev tools"
	@echo "  make upgrade                 - Upgrade all packages in lock file"
	@echo ""
	@echo "RUN SERVICES:"
	@echo "  make run-api                 - Run API service locally"
	@echo ""
	@echo "WHISPER ARTIFACTS (Dynamic Model Loading):"
	@echo "  make setup-artifacts         - Download Whisper library artifacts (default: small)"
	@echo "  make setup-artifacts-small   - Download small model artifacts"
	@echo "  make setup-artifacts-medium  - Download medium model artifacts"
	@echo ""
	@echo "TESTING:"
	@echo "  make test                    - Run all tests"
	@echo "  make test-library            - Test Whisper library adapter"
	@echo "  make test-integration        - Test model switching"
	@echo ""
	@echo "DOCKER:"
	@echo "  make docker-build            - Build Docker images"
	@echo "  make docker-up               - Start all services"
	@echo "  make docker-down             - Stop all services"
	@echo "  make docker-logs             - View logs"
	@echo ""
	@echo "CLEANUP:"
	@echo "  make clean                   - Clean up compiled files and caches"
	@echo "  make clean-old               - Remove old/unused files"
	@echo ""
	@echo "CODE QUALITY:"
	@echo "  make format                  - Format code (black)"
	@echo "  make lint                    - Lint code (flake8)"

# ==============================================================================
# DEPENDENCY MANAGEMENT (UV)
# ==============================================================================
# Cài đặt môi trường (mặc định uv sync cài cả dev deps, thêm --no-dev nếu chỉ muốn prod)
install:
	uv sync

# Nếu bạn chia group dev trong pyproject.toml, uv sync mặc định đã cài dev. 
# Target này giữ lại để tương thích thói quen cũ.
dev-install:
	uv sync

# Cập nhật các gói lên phiên bản mới nhất
upgrade:
	uv lock --upgrade

# Thêm thư viện mới (Ví dụ: make add pkg=requests)
add:
	uv add $(pkg)

# ==============================================================================
# RUN SERVICES
# ==============================================================================
# "uv run" tự động load .venv và environment, không cần trỏ đường dẫn python thủ công
# PYTHONPATH=. vẫn giữ để đảm bảo import các module gốc hoạt động đúng
run-api:
	PYTHONPATH=. uv run cmd/api/main.py

run-api-refactored:
	PYTHONPATH=. uv run cmd/api/main.py

# ==============================================================================
# WHISPER SETUP
# ==============================================================================
# Download Whisper models from MinIO (for local development)
# Requires MinIO connection configured in .env
setup-models:
	@echo "Downloading Whisper models from MinIO..."
	PYTHONPATH=. uv run scripts/setup_models.py

# Download specific model (e.g., make setup-model MODEL=medium)
setup-model:
	@echo "Downloading model: $(MODEL)..."
	PYTHONPATH=. uv run scripts/setup_models.py $(MODEL)

# Quick shortcuts for common models
setup-model-tiny:
	@echo "Downloading tiny model..."
	PYTHONPATH=. uv run scripts/setup_models.py tiny

setup-model-base:
	@echo "Downloading base model..."
	PYTHONPATH=. uv run scripts/setup_models.py base

setup-model-small:
	@echo "Downloading small model..."
	PYTHONPATH=. uv run scripts/setup_models.py small

setup-model-medium:
	@echo "Downloading medium model..."
	PYTHONPATH=. uv run scripts/setup_models.py medium

setup-model-large:
	@echo "Downloading large model..."
	PYTHONPATH=. uv run scripts/setup_models.py large

# Build whisper.cpp binary from source (for local development)
# Requires: cmake, make, and whisper.cpp repo cloned
setup-whisper:
	@echo "Building whisper.cpp binary..."
	bash scripts/setup_whisper.sh

# Build whisper.cpp with specific models
setup-whisper-custom:
	@echo "Building whisper.cpp with models: $(MODELS)..."
	bash scripts/setup_whisper.sh --models "$(MODELS)"

# ==============================================================================
# WHISPER LIBRARY ARTIFACTS (Dynamic Model Loading)
# ==============================================================================
# Download Whisper library artifacts from MinIO
setup-artifacts:
	@echo "Downloading Whisper library artifacts (default: small)..."
	PYTHONPATH=. uv run python scripts/download_whisper_artifacts.py small

setup-artifacts-small:
	@echo "Downloading SMALL model artifacts..."
	PYTHONPATH=. uv run python scripts/download_whisper_artifacts.py small

setup-artifacts-medium:
	@echo "Downloading MEDIUM model artifacts..."
	PYTHONPATH=. uv run python scripts/download_whisper_artifacts.py medium

# ==============================================================================
# DOCKER OPERATIONS
# ==============================================================================
docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

docker-restart:
	docker-compose restart

docker-clean:
	docker-compose down -v

# ==============================================================================
# DEV DOCKER (Optimized for fast restart)
# ==============================================================================
dev-build:
	@echo "Building dev image (one-time, caches deps)..."
	docker-compose -f docker-compose.dev.yml build

dev-up:
	@echo "Starting dev container (detached)..."
	docker-compose -f docker-compose.dev.yml up -d

dev-down:
	docker-compose -f docker-compose.dev.yml down

dev-logs:
	docker-compose -f docker-compose.dev.yml logs -f

dev-restart:
	@echo "Restarting dev container (fast)..."
	docker-compose -f docker-compose.dev.yml restart

dev-rebuild:
	@echo "Rebuilding dev image (use when deps change)..."
	docker-compose -f docker-compose.dev.yml build --no-cache
	docker-compose -f docker-compose.dev.yml up -d

# ==============================================================================
# CODE QUALITY & TESTING
# ==============================================================================
clean:
	@echo "Cleaning up compiled files and caches..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	rm -rf dist
	rm -rf build
	rm -rf *.egg-info
	uv cache clean

clean-old:
	@echo "Removing old/unused files and directories..."
	@echo "Removing backup files..."
	find . -name "*.bak" -type f -delete
	find . -name "*~" -type f -delete
	@echo "Removing old __init__.py.bak files..."
	find . -name "__init__.py.bak" -type f -delete
	@echo "Cleanup complete!"

test:
	@echo "Running all tests..."
	PYTHONPATH=. uv run pytest -v

test-library:
	@echo "Testing Whisper Library Adapter..."
	PYTHONPATH=. uv run pytest tests/test_whisper_library.py -v

test-integration:
	@echo "Testing Model Switching Integration..."
	PYTHONPATH=. uv run pytest tests/test_model_switching.py -v

test-small:
	@echo "Testing with SMALL model..."
	WHISPER_MODEL_SIZE=small PYTHONPATH=. uv run pytest tests/test_model_switching.py -v

test-medium:
	@echo "Testing with MEDIUM model..."
	WHISPER_MODEL_SIZE=medium PYTHONPATH=. uv run pytest tests/test_model_switching.py -v

format:
	uv run black core/ services/ cmd/ adapters/ internal/ tests/

lint:
	uv run flake8 core/ services/ cmd/ adapters/ internal/ tests/ --max-line-length=100

# ==============================================================================
# LOGS & SCALING
# ==============================================================================
scale-queue:
	docker-compose up -d --scale queue=3

logs-api:
	docker-compose logs -f api

logs-queue:
	docker-compose logs -f queue

logs-mongodb:
	docker-compose logs -f mongodb

logs-rabbitmq:
	docker-compose logs -f rabbitmq