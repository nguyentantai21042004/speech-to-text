# syntax=docker/dockerfile:1

# ==============================================================================
# STAGE 1: BUILDER
# ==============================================================================
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc g++ make && \
    rm -rf /var/lib/apt/lists/*

# Install dependencies (cached layer)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --frozen --no-install-project --no-dev

# Copy source and install project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ==============================================================================
# STAGE 2: RUNTIME
# ==============================================================================
FROM python:3.12-slim-bookworm AS runtime

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ffmpeg \
        wget \
        curl \
        libgomp1 \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

LABEL org.opencontainers.image.title="Speech-to-Text API" \
      org.opencontainers.image.description="Fast Speech-to-Text API with Whisper.cpp" \
      org.opencontainers.image.source="https://github.com/nguyentantai21042004/speech-to-text" \
      org.opencontainers.image.licenses="MIT"

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    WHISPER_MODEL_SIZE=base \
    WHISPER_LANGUAGE=vi \
    WHISPER_N_THREADS=0 \
    WHISPER_CHUNK_ENABLED=true \
    WHISPER_CHUNK_DURATION=30 \
    WHISPER_CHUNK_OVERLAP=1 \
    TRANSCRIBE_TIMEOUT_SECONDS=90

WORKDIR /app

# Create non-root user
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Copy from builder
COPY --from=builder /app/.venv /app/.venv
COPY cmd /app/cmd
COPY core /app/core
COPY internal /app/internal
COPY services /app/services
COPY infrastructure /app/infrastructure
COPY interfaces /app/interfaces
COPY models/__init__.py /app/models/__init__.py
COPY models/schemas.py /app/models/schemas.py
COPY scripts /app/scripts

# Setup entrypoint
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /app/scripts/download_whisper_artifacts.py

# Create directories
RUN mkdir -p /app/logs /app/models && \
    chown -R appuser:appgroup /app

USER appuser

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 -c "import http.client,os,sys;c=http.client.HTTPConnection('127.0.0.1',int(os.getenv('PORT',8000)));c.request('GET','/health');sys.exit(0 if c.getresponse().status==200 else 1)"

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["python3", "-m", "uvicorn", "cmd.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
