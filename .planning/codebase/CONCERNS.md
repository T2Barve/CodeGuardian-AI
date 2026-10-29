# Technical Concerns & Operational Considerations

**Analysis Date:** 2026-10-24

## 1. Database & Persistence Considerations

- **SQLite vs PostgreSQL Concurrency:**
  - *Current State:* Development and unit testing utilize SQLite (`aiosqlite` with `StaticPool`).
  - *Consideration:* SQLite locks the whole database file during write transactions. For production multi-worker deployment, PostgreSQL must be used (configured via `DATABASE_URL=postgresql+asyncpg://...`) to enable row-level concurrency and robust connection pooling.
  - *Mitigation:* The SQLAlchemy 2.0 async models and migrations are dialect-agnostic and verified with asyncpg in `docker-compose.prod.yml`.

## 2. Distributed Queue & Worker Scaling

- **Queue Mode Selection:**
  - *Current State:* Dual-mode queue defaults to in-memory `asyncio.Queue` when Redis is unavailable, and auto-switches to Redis Streams when `REDIS_URL` is set.
  - *Consideration:* In-memory queue state is lost if the backend container restarts during an active review.
  - *Recommendation:* Always configure Redis in production clusters for durable persistence and horizontal worker autoscale.

## 3. Large Pull Request Token Optimization

- **Diff Truncation & Chunking:**
  - *Current State:* Large diffs (> 5,000 lines or > 50 files) could exceed LLM context windows or induce high latency.
  - *Mitigation:* `app/github/client.py` filters lockfiles (`package-lock.json`, `poetry.lock`), generated assets, and binaries before forwarding diffs to LangGraph specialist agents.

## 4. Remediation Sandbox Security

- **Safe Execution Environment:**
  - *Current State:* Remediation sandbox tests fixes via AST syntax checking and unit tests.
  - *Consideration:* Running untrusted code in local subprocesses during remediation validation presents execution risk if PR contains malicious test scripts.
  - *Mitigation:* The sandbox operates in a restricted temporary directory with strict subprocess timeouts, no network access, and non-root execution privileges in Docker.

## 5. Frontend Bundle Optimization

- **Chunk Size Notice:**
  - *Current State:* Vite production build generates a 752 kB main bundle chunk (including Recharts and Lucide icons).
  - *Recommendation:* Introduce route-level code splitting using `React.lazy()` for auxiliary views (Policy Knowledge Base, Voice Explanation, Remediation Sandbox) to reduce the initial load bundle below 300 kB.

---
*Concerns analysis: 2026-10-24*
