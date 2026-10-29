# ==============================================================================
# CodeGuardian AI — Backend API Service Multi-Stage Dockerfile
# Production-Hardened Container Definition (CIS Docker Benchmark Compliant)
# ==============================================================================

# Stage 1: Build Dependencies
FROM python:3.12-slim AS builder

LABEL maintainer="CodeGuardian AI Team <devops@codeguardian.ai>"
LABEL stage="builder"

WORKDIR /app

# Install build-time dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies to user directory for easy multi-stage copying
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Production Hardened Runtime
FROM python:3.12-slim AS runner

LABEL maintainer="CodeGuardian AI Team <devops@codeguardian.ai>"
LABEL description="CodeGuardian AI Production Backend API Gateway"
LABEL version="1.0.0"

WORKDIR /app

# Install minimal runtime system utilities and security tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    dumb-init \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged application user and group (UID/GID 1001)
RUN groupadd -g 1001 codeguardian && \
    useradd -u 1001 -g codeguardian -m -d /home/codeguardian -s /bin/bash codeguardian && \
    mkdir -p /app/data/chromadb /app/logs && \
    chown -R codeguardian:codeguardian /app /home/codeguardian

# Copy installed Python packages from builder stage
COPY --from=builder --chown=codeguardian:codeguardian /root/.local /home/codeguardian/.local

# Set environment variables for production execution
ENV PATH=/home/codeguardian/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    UVICORN_WORKERS=4 \
    UVICORN_PORT=8000 \
    UVICORN_HOST=0.0.0.0

# Copy application code with strict non-root ownership
COPY --chown=codeguardian:codeguardian . /app

# Drop all privileges to unprivileged user
USER codeguardian

# Expose API port
EXPOSE 8000

# Container Healthcheck (polls /api/v1/health)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8000/api/v1/health || exit 1

# Process management via dumb-init for proper PID 1 signal handling
ENTRYPOINT ["/usr/bin/dumb-init", "--"]

# Production entrypoint with multi-worker ASGI configuration
CMD ["sh", "-c", "exec uvicorn app.main:app --host ${UVICORN_HOST} --port ${UVICORN_PORT} --workers ${UVICORN_WORKERS} --proxy-headers --forwarded-allow-ips='*'"]
