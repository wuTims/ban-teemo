# =============================================================================
# Ban Teemo Backend - Production Dockerfile
# =============================================================================
#
# Multi-stage build for optimized image size
# Target: Render.com free tier (512MB RAM limit)
#
# Build Options:
#   1. With local data files (deployment branch):
#      docker build -f deploy/docker/Dockerfile -t ban-teemo-api .
#
#   2. Download data from GitHub release:
#      docker build -f deploy/docker/Dockerfile \
#        --build-arg DATA_URL=https://github.com/user/repo/releases/download/v1.0/ban-teemo-data.tar.gz \
#        -t ban-teemo-api .
#
# Run: docker run -p 8000:8000 -e PORT=8000 ban-teemo-api

# -----------------------------------------------------------------------------
# Build Arguments
# -----------------------------------------------------------------------------
ARG DATA_URL=""

# -----------------------------------------------------------------------------
# Stage 1: Build environment with uv
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first (better layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies
RUN uv sync --frozen --no-dev --no-install-project

# -----------------------------------------------------------------------------
# Stage 2: Data preparation (handles download or copy)
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS data

ARG DATA_URL

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /data

# Download from URL if provided
RUN if [ -n "$DATA_URL" ]; then \
        echo "Downloading data from: $DATA_URL" && \
        curl -fsSL "$DATA_URL" -o /tmp/data.tar.gz && \
        tar -xzf /tmp/data.tar.gz -C /data && \
        rm /tmp/data.tar.gz; \
    fi

# Copy from build context (used when DATA_URL is empty)
# Using COPY . and then moving only what we need
COPY . /tmp/context/

RUN if [ -z "$DATA_URL" ]; then \
        echo "Copying data from build context" && \
        cp -r /tmp/context/outputs /data/ 2>/dev/null || true && \
        cp -r /tmp/context/knowledge /data/ 2>/dev/null || true; \
    fi && \
    rm -rf /tmp/context

# Verify required files exist
RUN ls -la /data/ && \
    test -d /data/outputs/full_2024_2025_v2/csv || \
    (echo "ERROR: outputs/full_2024_2025_v2/csv not found" && exit 1) && \
    test -d /data/knowledge || \
    (echo "ERROR: knowledge directory not found" && exit 1)

# -----------------------------------------------------------------------------
# Stage 3: Production runtime
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

# Security: Run as non-root user
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Environment configuration
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/backend/src"
ENV PYTHONUNBUFFERED=1

# Copy application code
COPY backend/src/ban_teemo ./backend/src/ban_teemo

# Copy data files from data stage
COPY --from=data /data/outputs ./outputs
COPY --from=data /data/knowledge ./knowledge

# Set ownership
RUN chown -R appuser:appuser /app

USER appuser

# Port configuration (Render sets PORT automatically)
EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-10000}/health')" || exit 1

# Start server
CMD ["sh", "-c", "uvicorn ban_teemo.main:app --host 0.0.0.0 --port ${PORT:-10000}"]
