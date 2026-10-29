# CodeGuardian AI — Production DevOps & Deployment Architecture

**Academic Document:** B.Tech Major Project Technical Specification  
**Milestone:** Phase 18 — Production DevOps & Cloud Infrastructure  
**Author:** CodeGuardian AI Engineering Team (Veer & Backend Team)  
**Status:** Approved Production Standard  
**Revision:** 1.0.0  

---

## 1. Executive Architecture Summary

CodeGuardian AI is engineered with an enterprise-grade, defense-in-depth containerized topology designed for high availability, deterministic execution, and zero-trust network segregation. The infrastructure is partitioned into isolated network tiers ensuring that data storage systems (PostgreSQL, Redis) are never exposed to untrusted external traffic.

### Multi-Tier Defense-in-Depth Topology

```mermaid
graph TD
    Client["Client Browser / Webhooks"] -->|HTTPS :443 / :80| Nginx["Nginx Web Server & Reverse Proxy<br/>(apps/frontend/nginx.conf)"]
    
    subgraph DMZ ["Public DMZ Tier (frontend-tier)"]
        Nginx -->|Static Assets| SPA["React 18 SPA (dist/)"]
        Nginx -->|Proxy /api/| Backend["FastAPI Gateway (4 ASGI Workers)<br/>UID 1001 (codeguardian)"]
    end
    
    subgraph SecureNetwork ["Isolated Internal Tier (backend-tier, internal=true)"]
        Backend -->|asyncpg:5432| Postgres[("PostgreSQL 16 Database<br/>Alembic Migrations / WAL")]
        Backend -->|aioredis:6379 (auth)| Redis[("Redis 7 Broker & Cache<br/>AOF Persistence")]
        Backend -->|Vector Search| Chroma[("ChromaDB Vector Store<br/>Persisted Volume")]
        
        Worker1["Review Worker Replica 1<br/>UID 1001 (codeguardian)"] -->|Dequeue| Redis
        Worker1 -->|Read / Write| Postgres
        Worker1 -->|Policy RAG| Chroma
        
        Worker2["Review Worker Replica 2<br/>UID 1001 (codeguardian)"] -->|Dequeue| Redis
        Worker2 -->|Read / Write| Postgres
        Worker2 -->|Policy RAG| Chroma
    end
    
    style DMZ fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#fff
    style SecureNetwork fill:#0f172a,stroke:#10b981,stroke-width:2px,color:#fff
```

---

## 2. Containerization Architecture & Security Hardening

Every component is packaged using multi-stage Docker builds to achieve minimal attack surfaces, deterministic dependency resolution, and strict adherence to the **CIS Docker Benchmark**.

### 2.1 Multi-Stage Build Mechanics

| Container Image | Build Stage | Runtime Stage | Non-Root User | Base OS | Exposed Ports | Healthcheck Target |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`codeguardian-backend`** | `python:3.12-slim` | `python:3.12-slim` | `codeguardian` (UID 1001) | Debian Slim | 8000 | `/api/v1/health` (HTTP 200) |
| **`codeguardian-worker`** | `python:3.12-slim` | `python:3.12-slim` | `codeguardian` (UID 1001) | Debian Slim | None | `/app/services/worker/healthcheck.py` |
| **`codeguardian-frontend`** | `node:20-alpine` | `nginx:1.27-alpine` | `nginx` (Standard) | Alpine Linux | 5173 / 80 | `/nginx-health` (HTTP 200) |

### 2.2 Security Standards Implemented

1. **Unprivileged Execution (Non-Root):**
   - The backend and worker containers drop all root capabilities upon start, executing exclusively under UID/GID `1001:1001` (`codeguardian`).
   - No `sudo` or setuid/setgid binaries exist in the production runtime images.
2. **PID 1 Signal Forwarding (`dumb-init`):**
   - In containerized environments, Python scripts running as PID 1 often fail to handle POSIX signals like `SIGTERM` correctly, leading to forceful kills (`SIGKILL`) after timeout.
   - `dumb-init` is installed as the primary container `ENTRYPOINT`, properly reaping zombie processes and forwarding termination signals to Uvicorn and the asynchronous `ReviewWorker` daemon for zero data loss graceful shutdown.
3. **Strict Layer Caching & No Cache Bloat:**
   - Package manager files (`requirements.txt`, `package.json`) are copied and installed in isolated builder stages with `--no-cache-dir`.
   - Temporary compilers (`build-essential`) are completely absent from the final runtime image.

---

## 3. Production Orchestration Topology (`docker-compose.prod.yml`)

The production deployment manifest defines strict resource constraints, service liveness probes, and network boundaries:

```yaml
# Architectural Resource Allocation Matrix
services:
  postgres:
    deploy:
      resources:
        limits: { cpus: '2.0', memory: 2048M }
        reservations: { cpus: '0.5', memory: 512M }
  redis:
    deploy:
      resources:
        limits: { cpus: '1.0', memory: 1024M }
        reservations: { cpus: '0.25', memory: 256M }
  backend:
    deploy:
      resources:
        limits: { cpus: '2.0', memory: 2048M }
        reservations: { cpus: '0.5', memory: 512M }
  worker:
    deploy:
      replicas: 2
      resources:
        limits: { cpus: '2.0', memory: 2048M }
        reservations: { cpus: '0.5', memory: 512M }
  frontend:
    deploy:
      resources:
        limits: { cpus: '1.0', memory: 512M }
        reservations: { cpus: '0.2', memory: 128M }
```

### Network Tier Separation

- **`frontend-tier` (Public / External Facing):** Bridges `frontend` and `backend`. Only port 80/443 is published to the host.
- **`backend-tier` (`internal: true`):** Contains `backend`, `worker`, `postgres`, and `redis`. Direct packet routing to/from the host network is blocked at the Docker bridge level. External attackers cannot port-scan or probe PostgreSQL or Redis.

---

## 4. Reverse Proxy & Nginx Hardening (`nginx.conf`)

The edge gateway utilizes Nginx configured with security headers and SPA fallback routing:

- **Security Headers:**
  - `X-Frame-Options: DENY` (Mitigates clickjacking)
  - `X-Content-Type-Options: nosniff` (Mitigates MIME-sniffing)
  - `Content-Security-Policy: default-src 'self'; ...`
  - `Referrer-Policy: strict-origin-when-cross-origin`
- **Dynamic Compression:** Gzip enabled with level 6 for JSON, JS, CSS, and SVG, reducing asset payload transfer by >70%.
- **Reverse Proxying with Timeout Guarantees:** 120-second upstream read timeouts to accommodate complex multi-agent analysis and LLM remediation streams without dropped connections.

---

## 5. Automated CI/CD Pipeline (GitHub Actions)

The repository workflow (`.github/workflows/ci.yml`) executes on every push and pull request to `main` and `develop`:

1. **`backend-ci`:** Linting with Ruff, asynchronous test suite execution with Pytest across 170+ unit and integration tests.
2. **`frontend-ci`:** Strict TypeScript static typing (`tsc --noEmit`) and production bundling with Vite.
3. **`docker-validation`:** Syntactic verification of both development and production compose topologies.
4. **`docker-build-test`:** Container compilation testing with Docker Buildx to prevent container registry breakage.

---

## 6. Operational Runbooks & Disaster Recovery

### 6.1 Database Backup & Recovery Procedure

```bash
# Automated Scheduled Backup (pg_dump with compression)
docker exec -t codeguardian-prod-postgres pg_dump -U codeguardian -F c codeguardian_db > /backups/db_$(date +%Y%m%d_%H%M%S).dump

# Point-In-Time Restoration Procedure
docker exec -i codeguardian-prod-postgres pg_restore -U codeguardian -d codeguardian_db --clean --if-exists < /backups/db_target.dump
```

### 6.2 Zero-Downtime Rolling Deployment Runbook

```bash
# 1. Pull latest verified container images
docker compose -f docker-compose.prod.yml pull

# 2. Run database migrations before worker or backend restarts
docker compose -f docker-compose.prod.yml run --rm backend alembic upgrade head

# 3. Perform rolling update with zero downtime
docker compose -f docker-compose.prod.yml up -d --no-deps --build backend
docker compose -f docker-compose.prod.yml up -d --no-deps --build worker
docker compose -f docker-compose.prod.yml up -d --no-deps --build frontend

# 4. Verify cluster health status
docker compose -f docker-compose.prod.yml ps
```

### 6.3 Worker Horizontal Scaling

```bash
# Scale background review workers dynamically during high PR volume
docker compose -f docker-compose.prod.yml up -d --scale worker=4
```
