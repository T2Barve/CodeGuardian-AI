# External Integrations

**Analysis Date:** 2026-10-24

## 1. GitHub API & Webhooks

**Purpose:** Complete pull-request lifecycle automation, commit inspection, inline code review annotations, and automated fix branches.

**Endpoints & Components:**
- **Webhook Ingress:** `/api/v1/github/webhook`
  - Protocol: HTTPS POST
  - Security: HMAC SHA-256 constant-time signature verification (`X-Hub-Signature-256`) via [`app/github/webhook.py`](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/apps/backend/app/github/webhook.py).
  - Deduplication: SHA-256 event ID and commit hash tracking preventing duplicate review execution.
  - Events Handled: `pull_request.opened`, `pull_request.synchronize`, `pull_request.reopened`.
- **API Client:** [`app/github/client.py`](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/apps/backend/app/github/client.py)
  - Base URL: `https://api.github.com`
  - Authentication: Bearer token (`GITHUB_TOKEN` / GitHub App installation token).
  - Operations: Fetch pull request metadata, head/base commit SHAs, patch diffs, repo details.
- **Reporting & Annotations:** [`app/github/reporter.py`](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/apps/backend/app/github/reporter.py)
  - GitHub Check Runs: Post status `in_progress`, `completed` with conclusion `success` or `failure`.
  - Inline Annotations: Batched in groups of 50 (GitHub API limit), containing exact file paths, line numbers, severity, and recommendations.
- **Automated Fix PRs:** [`app/remediation/fix_pr.py`](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/apps/backend/app/remediation/fix_pr.py)
  - Human-in-the-loop protection: Never commits to main; creates isolated branch `codeguardian/fix-{finding_id}` and posts a draft PR.

## 2. Deterministic Static Scanners

**Purpose:** High-precision deterministic security and code quality analysis executed prior to LLM agent passes.

**Tools & Protocols:**
- **Bandit:** Python AST vulnerability scanning (`app/scanners/bandit.py`).
- **Semgrep:** Rule-based semantic vulnerability scanning across Python, TS, JS (`app/scanners/semgrep.py`).
- **Gitleaks:** High-entropy regex and secret detection (`app/scanners/gitleaks.py`).
- **ESLint:** JavaScript/TypeScript static analysis (`app/scanners/eslint.py`).
- **Execution Mechanism:** Subprocess execution with explicit arguments (`shell=False`), timeout limits (60s default), isolated temp directories, and normalized findings schemas.
- **Error Handling:** Explicit failure reporting—missing scanner binaries or runtime errors yield visible `ERROR` states rather than false clean scores.

## 3. Message Queue & Asynchronous Workers

**Purpose:** Decoupled background task execution for heavy review pipelines.

**Components:**
- **Redis Streams:** Distributed message broker for production multi-worker environments (`REDIS_URL`).
- **In-Memory Async Queue:** Zero-dependency fallback for local development and self-contained testing.
- **Lifecycle Engine:** [`app/workers/review_worker.py`](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/apps/backend/app/workers/review_worker.py) with exponential backoff retry (3 attempts) and Dead Letter Queue (DLQ) persistence.

## 4. Policy RAG & Vector Knowledge Base

**Purpose:** Organization policy enforcement and anti-hallucination knowledge grounding.

**Components:**
- **ChromaDB:** Persistent embedding database (`app/rag/store.py`).
- **Retrieval Engine:** [`app/rag/engine.py`](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/apps/backend/app/rag/engine.py) querying policy documents for security standards, coding guidelines, and SLA compliance.
- **Grounding Guard:** Specialist agents strictly cite retrieved policy chunks or flag gaps when ungrounded.

## 5. AI Language Models (Multi-Agent System)

**Purpose:** Deep semantic code review, dependency vulnerability analysis, test coverage evaluation, documentation checking, and automated remediation generation.

**Components:**
- **LangGraph Multi-Agent Engine:** [`app/agents/graph.py`](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/apps/backend/app/agents/graph.py) orchestrating:
  - Security Specialist Agent
  - Quality Specialist Agent
  - Testing Specialist Agent
  - Documentation Specialist Agent
  - Dependency Specialist Agent
  - Supervisor Orchestrator
- **LLM Providers:** OpenAI (GPT-4o), Anthropic (Claude 3.5 Sonnet), or Google Gemini via standard unified LangChain chat interface.
- **Graceful Fallback:** If LLM keys are absent, the system operates in Deterministic Mode with full scanner and AST rule coverage.

## 6. Persistence & Relational Database

**Purpose:** Multi-tenant relational storage for organizations, repositories, pull requests, review jobs, runs, findings, and immutable audit logs.

**Components:**
- **PostgreSQL / SQLite:** Managed via SQLAlchemy 2.0 AsyncSession.
- **Connection Pooling:** Async engine with connection pooling (`pool_size=10`, `max_overflow=20` in production; `StaticPool` in testing).

## 7. Speech Synthesis & Audio Streaming

**Purpose:** Multilingual voice explanation for developer accessibility and fast audio debugging.

**Components:**
- **WAV Streamer:** [`app/voice/service.py`](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/apps/backend/app/voice/service.py) providing real-time PCM WAV audio streaming via `/api/v1/optimization/audio`.
- **Frontend Player:** Web Speech API integration in React with play/pause, voice selection, and language switching (English, Hindi, Hinglish, Urdu, Marathi, Gujarati).

---
*Integrations analysis: 2026-10-24*
