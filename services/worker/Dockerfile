# ==============================================================================
# CodeGuardian AI — Review Worker Service Multi-Stage Dockerfile
# Production-Hardened Background Worker (CIS Docker Benchmark Compliant)
# ==============================================================================

# Stage 1: Build Dependencies
FROM python:3.12-slim AS builder

LABEL maintainer="CodeGuardian AI Team <devops@codeguardian.ai>"
LABEL stage="builder"

WORKDIR /app

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY apps/backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Production Hardened Runtime
FROM python:3.12-slim AS runner

LABEL maintainer="CodeGuardian AI Team <devops@codeguardian.ai>"
LABEL description="CodeGuardian AI Background Review Worker Daemon"
LABEL version="1.0.0"

WORKDIR /app

# Install runtime system utilities and security tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    dumb-init \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged application user and group (UID/GID 1001)
RUN groupadd -g 1001 codeguardian && \
    useradd -u 1001 -g codeguardian -m -d /home/codeguardian -s /bin/bash codeguardian && \
    mkdir -p /app/data/chromadb /app/logs /tmp/codeguardian && \
    chown -R codeguardian:codeguardian /app /home/codeguardian /tmp/codeguardian

# Copy installed Python packages from builder stage
COPY --from=builder --chown=codeguardian:codeguardian /root/.local /home/codeguardian/.local

# Set environment variables for production execution
ENV PATH=/home/codeguardian/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Copy application source code with non-root ownership
COPY --chown=codeguardian:codeguardian apps/backend/app /app/app
COPY --chown=codeguardian:codeguardian services/worker /app/services/worker

# Drop all privileges to unprivileged user
USER codeguardian

# Container Healthcheck (polls Redis connectivity and worker heartbeat)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python /app/services/worker/healthcheck.py || exit 1

# Process management via dumb-init for proper signal handling (SIGTERM graceful shutdown)
ENTRYPOINT ["/usr/bin/dumb-init", "--"]

CMD ["python", "services/worker/worker.py"]
