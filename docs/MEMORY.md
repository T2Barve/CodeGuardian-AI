# CodeGuardian AI — Project Memory & Session State

**Last Updated:** 2026-10-14 (Phase 16 Security Hardening Completed)  
**Current Phase:** Phase 16 — Security Hardening (COMPLETED) $\to$ Ready for Phase 17 (Performance & Metrics)  
**Previous Phase:** Phase 15 — Fix PR Integration (COMPLETED)  

---

## 1. System State & Phase Tracking

- **Workspace:** Monorepo established with `apps/backend/`, `apps/frontend/`, `services/worker/`, `scanners/`, `policies/`, `datasets/`, `docs/`.
- **Risk Subsystem (Phase 7 - COMPLETED):**
  - **Deterministic Mathematical Scoring Engine (`app/risk/engine.py`):** Pure function risk calculation with base severity weighting (`CRITICAL: 25`, `HIGH: 15`, `MEDIUM: 8`, `LOW: 3`, `INFO: 0.5`), category exploitability factors (`SECURITY: 1.2`, `DEPENDENCY: 1.1`, `TESTING: 1.0`, `QUALITY: 0.9`, `DOCUMENTATION: 0.5`), repository criticality tier multipliers (`TIER_1: 1.3`, `TIER_2: 1.0`, `TIER_3: 0.7`), and logarithmic PR churn penalties (files & lines changed).
  - **Strict Determinism & Boundaries:** Zero LLM stochastic inputs into numerical score; deterministic grading (A to F), mergeability gating (`is_mergeable`), and critical finding override rules (>=1 CRITICAL caps grade at D; >=2 enforces Grade F and immediate BLOCK).
  - **Explainability & Category Radar:** Category risk breakdown across 5 dimensions, severity counts, and human-readable risk driving factors.
  - **Persistence & API (`app/risk/service.py` & `app/api/v1/endpoints/risk.py`):** Service persists risk assessment into `ReviewRun.configuration["risk_assessment"]` with compliance audit logs (`REVIEW_RISK_ASSESSED`); REST endpoints for review risk retrieval and simulation.
  - **Worker Integration (`app/workers/review_worker.py`):** Worker automatically computes and persists deterministic risk score after scanner & finding correlation.
  - **Verification:** 12/12 risk tests passing; 80/80 total test suite passing (100% pass rate).
- **Finding Subsystem (Phase 6 - COMPLETED):**
  - **Deterministic SHA-256 Fingerprinting (`app/findings/fingerprint.py`):** Canonical path normalizer (`normalize_file_path`), cross-tool rule taxonomy mapper (`get_canonical_issue_type`) to unified CWE classes, and deterministic SHA-256 hex digest generator: `SHA256(canonical_path:line:category:canonical_issue)`.
  - **Correlation & Proximity Engine (`app/findings/correlation.py`):** Line proximity clustering (±3 line tolerance), severity escalation (`resolve_highest_severity`), consensus confidence boosting (`combine_confidence`: 0.85 single tool, 0.95 multi-tool), issue taxonomy enrichment, and complete raw evidence collection (`FindingEvidenceItem`).
  - **Finding Engine (`app/findings/engine.py`):** Orchestrator processing raw scanner results into deduplicated, correlated findings with severity count breakdowns.
  - **Persistence & API (`app/findings/service.py` & `app/api/v1/endpoints/findings.py`):** Transactional PostgreSQL batch persistence with idempotent upsert, status transitions (`OPEN`, `RESOLVED`, `FALSE_POSITIVE`, `WONT_FIX`), and REST API endpoints (`GET /api/v1/reviews/{id}/findings`, `GET /api/v1/findings/{id}`, `PATCH /api/v1/findings/{id}/status`).
  - **Worker Integration (`app/workers/review_worker.py`):** Asynchronous worker pipeline automatically executes scanners, processes findings, and commits findings + evidence rows to the database.
  - **Verification:** 11/11 finding engine tests passing; 68/68 total test suite passing (100% pass rate).
- **Scanner Subsystem (Phase 5 - COMPLETED):**
  - SAST adapter architecture implemented under `apps/backend/app/scanners/` based on `BaseScanner` abstract contract with unified subprocess execution, strict timeouts (`SCANNER_TIMEOUT_SECONDS`), zero shell usage (`create_subprocess_exec`), and path traversal defense (`_validate_relative_file_path`).
  - **Bandit SAST Adapter (`BanditScanner`):** AST-level analysis and CLI JSON parsing detecting SQL injection (B608), command injection via `shell=True` (B602), insecure MD5/SHA1 hashes (B303), insecure pickle deserialization (B301), unsafe YAML load (B506), assert in production (B101), and hardcoded credentials (B105) with secret masking.
  - **Gitleaks SAST Adapter (`GitleaksScanner`):** High-entropy secret and credential detection supporting AWS Access Keys, GitHub PATs (classic & fine-grained), asymmetric private keys (RSA/EC/DSA/OPENSSH), Slack tokens, database connection strings, JWT tokens, and generic high-entropy keys with Shannon entropy gating (`calculate_shannon_entropy >= 3.0`) and non-reversible credential masking (`mask_secret`).
  - **ESLint SAST Adapter (`ESLintScanner`):** JavaScript/TypeScript security and quality linting detecting dynamic `eval()`, `document.write()`, DOM XSS via `innerHTML`, `new Function()` dynamic compilation, insecure web storage (`localStorage`), and production `console.log()` statements.
  - **Semgrep SAST Adapter (`SemgrepScanner`):** Polyglot semantic rule pattern matching covering SQL injection, dynamic command injection, DOM XSS, permissive wildcard CORS (`Access-Control-Allow-Origin: *`), unsafe YAML loading, and disabled SSL/TLS verification (`verify=False`).
  - **Scanner Orchestrator (`ScannerEngine`):** Concurrent scanner execution using `asyncio.gather(..., return_exceptions=True)`, registry pattern (`register_scanner`, `unregister_scanner`), partial failure isolation (failing/timed-out scanners do not halt the scan), and execution telemetry capturing per-scanner `ScannerExecutionSummary` (status, duration_ms, findings_count, error_message).
  - **Verification:** 19/19 scanner unit tests passing; 57/57 total test suite passing.
- **Queue & Worker Subsystem (Phase 4 - COMPLETED):**
  - Redis review queue broker (`queue:reviews`, `queue:reviews:processing`, `dlq:reviews`) implementing `ReviewQueueInterface` with atomic `BLMOVE`/`BRPOPLPUSH` delivery guarantees.
  - Dedicated in-memory queue fallback (`MemoryReviewQueue`) for reliable standalone test isolation.
  - Idempotent job dispatch with 24-hr TTL deduplication keys (`queue:reviews:dedup:{job_id}`).
  - Background `ReviewWorker` daemon managing the full asynchronous job state machine (`QUEUED` -> `RUNNING` -> `COMPLETED`).
  - Transient failure recovery: exponential retry backoff and state transition to `RETRYING`.
  - Permanent failure handling: routing to Dead-Letter Queue (`dlq:reviews`) with compliance audit logs (`REVIEW_JOB_FAILED_DLQ`) upon retry exhaustion.
  - Queue depth telemetry endpoint (`GET /api/v1/queue/metrics`) and Redis connectivity probing on `/api/v1/ready`.
- **Backend Service:** FastAPI application with structured logging, CORS, telemetry headers (`X-Request-ID`, `X-Process-Time`), versioned router (`/api/v1`), health (`/health`, `/api/v1/health`) and dynamic database readiness (`/api/v1/ready`) probes.
- **Frontend Service:** React 18 + Vite + TypeScript + Tailwind CSS application configured with dark-mode DevSecOps UI, live health polling, LangGraph agent fabric matrix, and metric cards. Compiles cleanly with zero errors (`tsc && vite build`).
- **Container Infrastructure:** `docker-compose.yml` validated via `docker compose config` with 5 services: `postgres`, `redis`, `backend`, `worker`, `frontend`.
- **CI Pipeline:** `.github/workflows/ci.yml` configured for backend lint/type-check/test, frontend type-check/build, and docker compose validation.

---

## 2. Completed Deliverables (Phase 0)

1. **Host & Workspace Discovery:** Verified clean workspace and toolchain availability.
2. **Master Phase 0 Discovery Report:** 38-section blueprint compiled covering all technical, structural, and academic dimensions.
3. **Core Specification Suite in `docs/`:**
   - [PRD.md](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/docs/PRD.md): Product requirements, personas, functional/non-functional criteria.
   - [ARCHITECTURE.md](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/docs/ARCHITECTURE.md): System topology, component interactions, trust boundaries, scaling.
   - [SYSTEM_DESIGN.md](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/docs/SYSTEM_DESIGN.md): Workflows, state machines, failure modes, sequence diagrams.
   - [DATABASE_DESIGN.md](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/docs/DATABASE_DESIGN.md): 13 PostgreSQL entities, DDL schemas, indexes, Alembic migration strategy.
   - [API_SPECIFICATION.md](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/docs/API_SPECIFICATION.md): OpenAPI/REST endpoints, HMAC headers, schemas, error formats.
   - [AGENT_DESIGN.md](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/docs/AGENT_DESIGN.md): LangGraph state machine, Supervisor & 5 specialist agents, Pydantic schemas.
   - [RAG_DESIGN.md](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/docs/RAG_DESIGN.md): ChromaDB vector ingestion, chunking, filtering, anti-hallucination rules.
   - [SECURITY.md](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/docs/SECURITY.md): Threat model, HMAC verification, subprocess isolation, prompt injection defense.
   - [TESTING.md](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/docs/TESTING.md): Multi-tier test pyramid, benchmark dataset, empirical evaluation formulas.
   - [DEPLOYMENT.md](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/docs/DEPLOYMENT.md): Docker Compose topology, service matrix, `.env` schema, quickstart.
   - [PHASES.md](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/docs/PHASES.md): 20-phase roadmap (Phases 0-19), progression rules, acceptance gates.
   - [RULES.md](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/docs/RULES.md): Non-negotiable engineering constraints, trust model, anti-fabrication rules.
   - [DECISIONS.md](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/docs/DECISIONS.md): Architectural Decision Records (ADRs 001 - 010).
   - [PROJECT_STATUS.md](file:///c:/Users/ASUS/Desktop/Code%20Guardian%20AI/docs/PROJECT_STATUS.md): Live progress tracker and team member responsibility allocations.

---

## 3. Known Issues & Environment Notes

- **Docker Desktop Daemon:** Docker Desktop is installed, but the background daemon process is not running. It will need to be running for containerized PostgreSQL, Redis, and multi-container deployment in Phase 1.
- **Python 3.14 Compatibility:** Python 3.14 is very recent; certain C-extension packages (e.g. older versions of greenlet or chromadb) may prefer Python 3.12/3.13 in Docker container environments. We ensure containerized Dockerfiles use `python:3.12-slim` to ensure 100% binary package stability while supporting local Python development.

---

## 4. Completed Milestone: Phase 8 — LangGraph Supervisor (COMPLETED)
 
- **LLM Provider Abstraction (`app/services/llm/`):** Clean interface (`BaseLLMProvider`) supporting provider independence (Gemini 1.5/2.0, Mock provider fallback, structured JSON output validation).
- **Shared ReviewState with Reducers (`app/agents/state.py`):** Immutable state with typed parallel additive reducers (`merge_dicts`, `merge_findings`, `merge_token_usage`, `merge_errors`, `merge_telemetry`).
- **Supervisor Routing & File Classifier (`app/agents/supervisor.py`):** Deterministic AST-aware file partitioning and routing decision generator (`SupervisorRoutingDecision`).
- **Compiled LangGraph StateGraph (`app/agents/graph.py`):** Full stateful DAG executing `supervisor_node`, dynamic parallel specialist fan-out (`security`, `quality`, `testing`, `documentation`, `dependency`), aggregator, and deterministic risk calculation nodes with partial failure isolation.
- **Agent Run Persistence & Telemetry (`app/agents/service.py` & `app/api/v1/endpoints/agents.py`):** Database persistence into `AgentRun` records with REST querying and review timeline telemetry.
- **ReviewWorker Pipeline Integration (`app/workers/review_worker.py`):** Asynchronous worker dispatches full LangGraph review workflow.
- **Verification:** 10/10 unit tests in `test_langgraph_supervisor.py` passing; 90/90 total test suite passing (100% pass rate).

---

## 5. Completed Milestone: Phase 9 — Specialist Agents (COMPLETED)

- **Specialist Agent Schemas (`app/schemas/agent.py`):** Rich Pydantic schemas for `SecurityAgentOutput`, `QualityAgentOutput`, `TestingAgentOutput`, `DocumentationAgentOutput`, `DependencyAgentOutput`.
- **Security Specialist Agent (`app/agents/security.py`):** Contextual reasoning over SAST findings and code diffs with automated CWE & OWASP Top 10 mapping, exploitability analysis, and mandatory secret token masking (`mask_secret`).
- **Quality Specialist Agent (`app/agents/quality.py`):** Structural code smell detection (swallowed exceptions `except Exception: pass`, wildcard imports, debug `print()` / `console.log()` statements, deep callback pyramids) with maintainability ratings.
- **Testing Specialist Agent (`app/agents/testing.py`):** Test coverage gap analysis identifying modified source logic without corresponding test files; starter unit test scaffolding generator (`AI_GENERATED_STARTER_TEST`).
- **Documentation Specialist Agent (`app/agents/documentation.py`):** Public docstring omission checks and README/API documentation drift warnings.
- **Dependency Specialist Agent (`app/agents/dependency.py`):** Package manifest analysis (`requirements.txt`, `package.json`, `pyproject.toml`) detecting unpinned `>=` constraints, wildcard versions, and suspicious typosquatting heuristics.
- **LangGraph Integration (`app/agents/graph.py`):** All 5 specialist agents wired into the compiled review workflow DAG.
- **Verification:** 6/6 unit tests in `test_specialist_agents.py` passing; 96/96 total test suite passing (100% pass rate).

---

## 6. Completed Milestone: Phase 10 — Policy RAG (COMPLETED)

- **Ground-Truth Policy Standards (`policies/`):**
  - Secure Coding Baseline (`policies/security/secure_coding.md` - SEC-001)
  - Database Security & SQLi Prevention (`policies/security/db_security.md` - SEC-002)
  - Python Code Quality & Maintainability (`policies/coding-standards/python_quality.md` - QUAL-001)
  - Unit & Integration Test Coverage Criteria (`policies/testing/test_coverage.md` - TEST-001)
  - Public API & Architecture Documentation (`policies/documentation/api_docs.md` - DOC-001)
- **Structural Document Chunker (`app/rag/chunker.py`):**
  - Section-aware Markdown splitting on `## ` and `### ` preserving code blocks, paragraph integrity, and metadata (`policy_name`, `category`, `section`, `source_file`).
- **Vector Store & Embeddings Engine (`app/rag/vector_store.py`):**
  - `VectorStoreInterface` with `MemoryVectorStore` implementing deterministic TF-IDF / term-frequency vectorizer and cosine similarity calculation.
  - Category and language scope pre-filtering.
- **Anti-Hallucination Retriever & Citation Verifier (`app/rag/retriever.py`):**
  - Enforces explicit Anti-Hallucination sentinel: `"[POLICY_CONTEXT]: No applicable project policy was retrieved."` on zero matches or similarity $< 0.60$.
  - Citation validator `verify_citation()` verifying agent references against ground-truth retrieved chunks.
- **Policy Service & REST API (`app/rag/service.py`, `app/api/v1/endpoints/policies.py`, `app/api/v1/endpoints/rag.py`):**
  - `POST /api/v1/policies/ingest`: transactional chunk and vector ingestion.
  - `GET /api/v1/policies`: list active engineering standards.
  - `GET /api/v1/policies/{id}`: inspect policy and chunk hierarchy.
  - `POST /api/v1/rag/query`: semantic retrieval with anti-hallucination context assembly.
- **Verification:** 9/9 unit & integration tests in `test_policy_rag.py` passing; 105/105 total test suite passing (100% pass rate).

## 7. Completed Milestone: Phase 11 — Report Engine (COMPLETED)
 
- **Report Schema (`app/schemas/report.py`):** Structured Pydantic contracts for `ReviewReport`, `ReviewReportSummary`, `ReportFindingItem`, and `ReportAgentSummary`.
- **Markdown & JSON Synthesizer (`app/reports/generator.py`):**
  - Developer-friendly, executive-ready GitHub Markdown renderer (`ReportGenerator.render_markdown`).
  - Badges and visual indicators for risk grade (🟢 Grade A through 🔴 Grade F), mergeability gating (✅ MERGEABLE / 🚫 BLOCKED), and severity breakdown matrix.
  - Multi-dimensional Category Risk Radar table (Security, Quality, Testing, Documentation, Dependency).
  - Correlated findings with tool citations (Bandit, Semgrep, ESLint, Gitleaks, Multi-Agent), collapsible code snippets, recommendations, and policy citations.
  - Multi-agent execution telemetry table with agent status, duration (ms), token usage, and finding counts.
- **Report Service & Persistence (`app/reports/service.py`):**
  - Transactional persistence into `ReviewRun.configuration["report"]` and `ReviewRun.summary`.
  - Database audit trail (`REVIEW_REPORT_GENERATED`).
  - Safe fallback calculation via deterministic Risk Engine if risk assessment has not yet been computed.
- **REST API Endpoints (`app/api/v1/endpoints/reports.py`):**
  - `GET /api/v1/reviews/{id}/report`: Structured JSON review report.
  - `GET /api/v1/reviews/{id}/report/markdown`: Formatted GitHub Markdown stream.
  - `POST /api/v1/reviews/{id}/report/generate`: On-demand regeneration and persistence.
- **Worker Pipeline Integration (`app/workers/review_worker.py`):**
  - Automatic synthesis and persistence of review report upon completing multi-agent review and risk scoring.
- **Verification:** 4/4 report engine tests passing; 109/109 total test suite passing (100% pass rate).

---

## 8. Completed Milestone: Phase 12 — Frontend Dashboard (COMPLETED)

- **Owner:** Darshan (Frontend & Visualization)
- **Design Principles (Section 49):** High-contrast DevSecOps aesthetic, clean typography (Inter / JetBrains Mono), glassmorphism cards, zero cartoon elements, responsive layout.
- **Backend API Endpoints (`app/api/v1/endpoints/dashboard.py` & `repositories.py`):**
  - `GET /api/v1/dashboard/summary`: Executive metrics (total repos, total reviews, critical/high counts, open/resolved counts, avg latency, 7-day security & quality trends via Recharts, 5D Category Risk Radar).
  - `POST /api/v1/dashboard/seed`: One-click demonstration data populator.
  - `GET /api/v1/repositories`: List tracked GitHub repositories with health status, PR counts, and review counts.
  - `GET /api/v1/repositories/{id}`: Detailed repo explorer with PR list and review history.
- **Frontend Architecture (`apps/frontend/`):**
  - **Types (`src/types/index.ts`):** Strictly synchronized with backend Pydantic models.
  - **API Client (`src/services/api.ts`):** Complete async fetch layer covering dashboard, repositories, reports, findings, status patching, and RAG semantic queries.
  - **Navigation (`src/components/Navbar.tsx`):** Header with logo, navigation links, real-time backend/database health indicator, and 1-click "Seed Demo" action.
  - **Dashboard View (`src/pages/DashboardPage.tsx`):**
    - Executive MetricCards (Repositories, Reviews, Critical Vulnerabilities, Latency).
    - Vulnerability Detection AreaChart (Critical vs High severity trends).
    - 5D Category Risk Radar progress breakdown (Security, Quality, Testing, Documentation, Dependency).
    - Recent Pull Request Reviews table with RiskGradeBadges, mergeability pills, and inspect links.
    - AgentStatusGrid monitoring the 6 LangGraph review agents.
  - **Repositories View (`src/pages/RepositoriesPage.tsx`):** Monitored repository directory with health badges, language tags, search filter, and PR history.
  - **Review Explorer View (`src/pages/ReviewPage.tsx`):**
    - PR banner with author, commit SHA, branch mapping, duration, risk score (0-100), and Grade badge (A-F).
    - Tabbed findings breakdown: Executive Summary, Security Vulnerabilities, Code Quality, Test Coverage Gaps, Documentation Drift, Dependencies.
    - Agent Fabric telemetry matrix (status, duration, tokens consumed, finding count).
    - Full GitHub Markdown Stream toggle.
  - **Finding Inspector Modal (`src/components/FindingDetailModal.tsx`):**
    - Deep-dive into root cause, code snippet, line ranges, impact, remediation recommendation, and ground-truth policy citations.
    - Raw tool evidence chain (Bandit, Semgrep, ESLint, Gitleaks).
    - Controlled status transitions (`OPEN` -> `RESOLVED` / `FALSE_POSITIVE`) with compliance audit justifications.
    - AI Remediation Sandbox preview with 5-stage validation checks (syntax, tests, security, regression).
  - **Policy Library & RAG Sandbox (`src/pages/PoliciesPage.tsx`):**
    - Ground-truth policy standards browser and chunk hierarchy inspector.
    - Interactive semantic search tester verifying the Anti-Hallucination Sentinel.
- **Verification:**
  - Frontend builds with zero errors: `tsc && vite build` (Clean build in 10.89s).
  - Backend test suite: 110 / 110 unit & integration tests passing (100% pass rate).

---

## 9. Completed Milestone: Phase 13 — GitHub Reporting (COMPLETED)

- **Owner:** Mayur (Backend, DB & GitHub)
- **GitHub Client Extensions (`app/github/client.py`):**
  - Added `list_issue_comments(owner, repo, issue_number)` to inspect existing PR comments.
  - Added `update_issue_comment(owner, repo, comment_id, body)` for in-place comment updates.
  - Added `list_check_runs_for_ref(owner, repo, ref)` to query existing check suite runs.
- **GitHub Reporter Service (`app/github/reporter.py`):**
  - **Deterministic Anti-Spam Marker:** `<!-- codeguardian-pr-review-summary:pr-{pr_number} -->`. On new review cycles, searches existing comments for the marker; updates in-place (`UPDATED`) rather than spamming multiple PR comments (`CREATED`).
  - **Concise Developer Comment Formatting:**
    - Executive summary with Grade Badges (🟢 A to 🔴 F) and Merge Gate status (`MERGEABLE` vs `MERGE BLOCKED`).
    - Findings distribution table across 5 severity tiers (Critical, High, Medium, Low, Info).
    - 5D Category Risk Radar breakdown (Security, Quality, Testing, Documentation, Dependency).
    - Key risk driving factors list.
    - Severe findings table (top 8 Critical & High findings with file locations and remediation recommendations).
    - Telemetry footer with execution time, agent count, and deep links to the CodeGuardian dashboard.
  - **GitHub Check Run Creation:**
    - Check run title: `CodeGuardian: GRADE {grade} ({score}/100) — {action}`.
    - Conclusion mapping: `failure` if unmergeable/critical findings/grade F; `neutral` if high findings/grade C/D; `success` if clean.
    - Up to 50 line-level annotations with severity mapping (`failure` for CRITICAL, `warning` for HIGH/MEDIUM, `notice` for LOW/INFO) and start/end line clamping.
  - **Inline PR Comments:** Posts targeted review comments on changed lines for critical findings.
  - **Dry-Run Preview:** `preview_github_report()` returns formatted comment markdown and annotations without executing network calls.
  - **Mock Token Fallback:** Gracefully simulates clean check run creation and comment delivery when `GITHUB_TOKEN` is unset or prefixed with `mock_`.
  - **Audit Logging:** Logs `GITHUB_REVIEW_REPORT_PUBLISHED` in the database audit log with Check Run ID, Comment ID, conclusion, and risk grade.
- **Worker Integration (`app/workers/review_worker.py`):**
  - Pipeline automatically calls `GitHubReporter.publish_review_report()` after report synthesis.
- **REST API Endpoints (`app/api/v1/endpoints/reports.py`):**
  - `POST /api/v1/reviews/{id}/github/publish`: Triggers manual or automated publish of Check Run and PR comment.
  - `GET /api/v1/reviews/{id}/github/preview`: Previews the PR comment markdown, anti-spam marker, and Check Run annotations.
- **Verification:**
  - 8/8 unit tests in `tests/unit/test_github_reporting.py` passing.
  - 132/132 total tests passing across backend (118 unit + 14 integration).
  - Clean frontend production build (`dist/` generated, 0 TypeScript errors).

---

## 10. Completed Milestone: Phase 14 — Remediation Engine (COMPLETED)

- **Owners:** Tanishq (AI & Multi-Agent) & Veer (Security & Scanners)
- **Patch Generator (`app/remediation/generator.py`):**
  - Generates minimal, clean unified git diff patches grounded in ChromaDB policy standards and finding context.
  - Deterministic fallback patch generator for offline/test environments covering:
    - SQL Injection (replaces dynamic string formatting with parameterized query syntax).
    - Hardcoded Secrets (replaces plaintext tokens with `os.environ.get(...)`).
    - Permissive CORS (replaces wildcard `*` with environment or specific origin).
    - Insecure Hashes (replaces MD5/SHA1 with SHA-256).
    - Unsafe YAML (replaces `yaml.load` with `yaml.safe_load`).
- **5-Stage Sandboxed Validation Pipeline (`app/remediation/sandbox.py`):**
  - Pure Python resilient unified diff patch application (`apply_unified_diff_to_string`).
  - Stage 1 (`patch_application`): Validates clean application of unified diff onto target file in isolated sandbox.
  - Stage 2 (`syntax_check`): Executes AST parsing (`ast.parse`) for Python, JSON parse for JSON, verifying 0 syntax errors.
  - Stage 3 (`scanner_check`): Targeted scanner re-run verifying original vulnerability elimination without introducing new security flaws.
  - Stage 4 (`unit_tests`): Executes workspace unit tests under sandbox timeout; skips cleanly if no test files exist.
  - Stage 5 (`regression_check`): Non-destructive check ensuring minimal diff without catastrophic truncation or unintended deletions.
  - Overall status gating: sets `VALIDATED` and `can_create_pr = True` if and only if all stages pass.
- **Remediation Service & DB Persistence (`app/remediation/service.py`):**
  - Complete lifecycle management for `RemediationAttempt` entities.
  - Resolves file content from workspace, evidence snippets, or synthetic context.
  - Records compliance audit logs (`REMEDIATION_VALIDATED`, `REMEDIATION_REJECTED`).
  - Full retrieval, revalidation, and per-finding listing support.
- **REST API Endpoints (`app/api/v1/endpoints/remediation.py`):**
  - `POST /api/v1/findings/{finding_id}/remediate`: Triggers patch generation and sandboxed validation pipeline.
  - `GET /api/v1/remediation/{remediation_id}`: Retrieves patch, 5-stage validation details, and PR eligibility.
  - `GET /api/v1/findings/{finding_id}/remediations`: Lists all remediation attempts for a finding.
  - `POST /api/v1/remediation/{remediation_id}/validate`: Re-triggers validation on an existing patch.
- **Verification:**
  - 9/9 unit tests in `tests/unit/test_remediation_engine.py` passing.
  - 141/141 total tests passing across backend (127 unit + 14 integration).
  - Clean frontend production build (`dist/` generated, 0 TypeScript errors).

---

## 11. Completed Milestone: Phase 15 — Fix PR Integration (COMPLETED)

- **Owner:** Mayur (Backend, DB & GitHub)
- **GitHub Client Extensions (`app/github/client.py`):**
  - Added `get_file_contents(owner, repo, path, ref)` for remote blob SHA and content inspection.
  - Added `create_or_update_file_contents(owner, repo, path, message, content_base64, branch, sha)` for atomic commits to branches.
- **Fix PR Service (`app/remediation/fix_pr.py`):**
  - **Automated Branch & PR Dispatch:**
    - Gating rule: Enforces that only patches with `status == "VALIDATED"` can trigger Fix PR creation.
    - Idempotency & duplicate protection: Blocks duplicate Fix PRs if a Fix PR already exists or attempt is already `APPLIED`.
    - Creates git branch `codeguardian/fix-{finding_id[:8]}` from base commit SHA.
    - Applies patch to file and commits changes to the branch via GitHub API.
    - Submits GitHub Pull Request with rich markdown documentation: finding summary, location, policy standard, and 5-stage validation table.
    - Zero direct pushes to default branch; requires developer human-in-the-loop review and approval.
  - **Database Persistence & State Transitions:**
    - Persists `FixPR` entity linked to `RemediationAttempt`.
    - Transitions `RemediationAttempt.status` from `VALIDATED` to `APPLIED`.
    - Records compliance audit logs (`FIX_PR_CREATED`).
  - **Webhook Lifecycle Synchronization (`handle_fix_pr_webhook_event`):**
    - Listens for GitHub PR events on tracked Fix PRs.
    - When Fix PR is merged: transitions `FixPR.status = "MERGED"` and automatically resolves `Finding.status = "RESOLVED"` with audit log.
    - When Fix PR is closed without merge: transitions `FixPR.status = "CLOSED"`.
- **REST API Endpoints (`app/api/v1/endpoints/remediation.py`):**
  - `POST /api/v1/remediation/{remediation_id}/fix-pr`: Submits automated GitHub Fix PR for validated remediation patch.
  - `GET /api/v1/fix-prs/{fix_pr_id}`: Retrieves Fix PR metadata, GitHub PR number, URL, and status.
- **Verification:**
  - 7/7 unit tests in `tests/unit/test_fix_pr.py` passing.
  - 148/148 total tests passing across backend (134 unit + 14 integration).
  - Clean frontend production build (`dist/` generated, 0 TypeScript errors).

---

---

## 12. Security Hardening Subsystem (Phase 16 - COMPLETED)

- **Owner:** Veer (Security, Scanners & DevSecOps)
- **Implemented Security Components (`apps/backend/app/security/`):**
  - **Prompt Injection Defense (`app/security/prompt_guard.py`):**
    - `PromptGuard`: High-performance detection against direct instruction overrides, jailbreaks (`EvilBot`, `DAN`, unrestricted modes), system prompt leaks, rating/audit tampering (`mark PR as 100% clean`), and delimiter collision breakouts (`</untrusted_user_input>`, `--- END ORIGINAL FILE CONTENT ---`).
    - Unicode normalization (`NFKC`) and zero-width character stripping to neutralize homoglyph evasion attacks.
    - Encapsulation utility (`encapsulate_untrusted`) wrapping external PR diffs, developer instructions, and code snippets into hardened XML boundary tags with explicit AI anti-execution directives.
    - Integrated with `PatchGenerator.generate_patch` to protect against prompt injection in custom developer instructions and untrusted repository code.
  - **Path Traversal Defense (`app/security/path_traversal.py`):**
    - `validate_safe_path`: Enforces strict boundary containment, rejects null-byte injections (`\x00`, CWE-626), disallows absolute filesystem paths (`/etc/shadow`, `C:\...`), and validates that canonical resolved paths remain inside the intended directory (`target.is_relative_to(base)` and `os.path.commonpath`).
    - `sanitize_filename`: Extracts basenames and strips directory separators, control characters, and leading dots.
    - Integrated into `SandboxPipeline` (`validate_patch_application`, `validate_scanner`, file staging) and `RemediationService` (`_resolve_file_content`).
  - **Subprocess Isolation Guard (`app/security/subprocess_guard.py`):**
    - `execute_isolated_command`: Enforces `shell=False` invariant with argument list validation (`List[str]`), working directory safety checks, explicit execution timeout (`timeout_seconds`) with async cancellation & termination, and memory buffer quotas (`max_output_bytes`) guarding against infinite output flooding DoS.
    - Verified static AST audit confirming **zero** invocations of `shell=True` or `os.system()` in production backend code.
  - **Secret Redaction & Telemetry Sanitization (`app/security/secret_masker.py`):**
    - `mask_secrets_in_text`: Regex pattern matching across Stripe keys (`sk_live_...`), GitHub PATs (`ghp_...`, `github_pat_...`), AWS credentials (`AKIA...`), Slack tokens, private keys (`-----BEGIN ... PRIVATE KEY-----`), database passwords in URIs, and bearer tokens.
    - `mask_secret`: Non-reversible token masking preserving at most 4 prefix and suffix characters for auditability while preventing credential leakage.
    - `sanitize_telemetry`: Deep recursive scrubber traversing dictionaries, lists, and Pydantic models to redact sensitive fields (`password`, `secret`, `token`, `api_key`, `authorization`).
  - **OWASP Top 10 API Security Middleware (`app/security/middleware.py`):**
    - `SecurityHeadersMiddleware`: Injects defense-in-depth headers on all HTTP responses (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`, `Content-Security-Policy: default-src 'self'`, `Permissions-Policy`, and conditional HSTS).
    - `ContentLengthLimitMiddleware`: Rejects oversized request payloads exceeding 10MB quota with `413 Payload Too Large` in RFC 7807 Problem Details format before reading body into memory.
- **Verification & Test Battery (`tests/unit/test_security_hardening.py`):**
  - 25 dedicated unit tests validating prompt injection detection, path traversal rejection, subprocess isolation, secret masking, and OWASP middleware.
  - Total test suite: **159 / 159 tests passing** (145 unit + 14 integration).
  - Frontend production build: `tsc && vite build` passing cleanly with 0 errors.

---

## 13. Next Milestone: Phase 17 — Performance & Metrics (PLANNED)

- **Owner:** Veer & Tanishq
- **Scope & Goals (Section 56):**
  - Review latency benchmarking: verify typical PR review completes in $\le 120$ seconds.
  - Multi-agent token usage & cost tracking: normalize prompt/completion token metrics across agents and calculate estimated USD cost per review run.
  - Review throughput and queue performance: Dead Letter Queue (DLQ) metrics, queue processing rates, and worker pool saturation telemetry.
  - Performance and metrics documentation in `docs/EVALUATION.md`.

