# Technology Stack

**Analysis Date:** 2026-10-24

## Languages

**Primary:**
- Python 3.11 / 3.14 - Backend FastAPI service, multi-agent orchestration, AST static analysis, RAG pipeline, test suites (`apps/backend/`)
- TypeScript 5.4 - Frontend dashboard, typed API clients, state management (`apps/frontend/`)

**Secondary:**
- JavaScript (Node.js 20+) - Frontend build tooling, Vite bundling, ESLint scanner engine
- Shell / PowerShell / Dockerfile - Containerization, local orchestration, CI/CD automation

## Runtime

**Environment:**
- Python 3.11+ async runtime (asyncio, anyio, uvicorn)
- Node.js 20.x (LTS) for Vite development server and production build
- In-memory / browser Web Speech API & Web Audio API (PCM WAV stream synthesis)

**Package Managers:**
- pip / uv for Python dependencies (`apps/backend/pyproject.toml`)
- npm 10.x for frontend dependencies (`apps/frontend/package.json`)
- Lockfile: `apps/frontend/package-lock.json` present

## Frameworks

**Core:**
- FastAPI 0.110+ - Asynchronous REST API, OpenAPI docs, dependency injection, CORS middleware
- LangGraph 0.0.30+ & LangChain Core - Stateful cyclic multi-agent graph with supervisor routing
- React 18.2 - Component-driven UI with hooks, virtual DOM, suspense boundaries
- Tailwind CSS 3.4 - Utility-first styling with Cosmic Plasma Nebula design system

**Testing:**
- pytest 9.0+ & pytest-asyncio - 194 unit and integration tests with in-memory SQLite fixtures
- httpx (AsyncClient + ASGITransport) - High-performance async HTTP testing against FastAPI

**Build & Dev:**
- Vite 5.1 - Frontend bundler with hot module replacement (HMR) and optimized rollup production builds
- TypeScript Compiler (`tsc`) - Strict static type verification
- SQLAlchemy 2.0 (Async) + aiosqlite / asyncpg - ORM and async database connection management

## Key Dependencies

**Critical:**
- `fastapi` & `uvicorn` - High-throughput ASGI server and API routing (`apps/backend/app/main.py`)
- `langgraph` & `langchain-core` - Multi-agent graph orchestrating 5 specialist agents + supervisor (`apps/backend/app/agents/graph.py`)
- `sqlalchemy` & `aiosqlite` / `asyncpg` - Relational persistence layer for 13 domain models (`apps/backend/app/models/`)
- `chromadb` - Vector store embedding internal engineering and security policies (`apps/backend/app/rag/store.py`)
- `redis` (redis-py async) - Dual-mode Redis Streams & Async Queue for distributed review jobs (`apps/backend/app/workers/queue.py`)
- `@tanstack/react-query` - Server-state caching, optimistic updates, and background refetching (`apps/frontend/src/`)
- `lucide-react` & `recharts` - Nebula iconography and real-time SVG charting

**Infrastructure & Tooling:**
- Bandit, Semgrep, Gitleaks, ESLint - Deterministic static analysis tools executed via sandboxed subprocesses
- Docker & Docker Compose - Containerized production stack (`docker-compose.yml`, `docker-compose.prod.yml`)

## Configuration

**Environment:**
- `.env` / `.env.example` / `.env.production.example` - Loaded via Pydantic Settings (`apps/backend/app/config.py`)
- Key variables: `DATABASE_URL`, `REDIS_URL`, `CHROMA_PERSIST_DIR`, `GITHUB_TOKEN`, `GITHUB_WEBHOOK_SECRET`, `LLM_API_KEY`, `JWT_SECRET`

**Build:**
- `apps/frontend/vite.config.ts` - Vite bundling configuration
- `apps/frontend/tsconfig.json` - TypeScript strict mode compiler options
- `apps/backend/pyproject.toml` - Python dependency constraints and pytest settings

## Platform Requirements

**Development:**
- Windows / macOS / Linux with Python 3.11+ and Node.js 20+
- Optional: Local Docker engine for Redis and PostgreSQL services

**Production:**
- Linux container environment (Docker / Kubernetes / AWS ECS / GCP Cloud Run)
- Multi-container architecture: Nginx edge proxy, FastAPI backend, Redis queue, ChromaDB vector store, PostgreSQL database

---
*Stack analysis: 2026-10-24*
*Verified with 194 passing pytest unit/integration tests and clean Vite production bundle.*
