# CodeGuardian AI — Phase Roadmap & Implementation Plan

**Document:** Phased Engineering Milestones, Acceptance Criteria & Progression Gates  
**Status:** Approved Architectural Baseline  
**Version:** 1.0.0 (Phase 0)  

---

## Master Phase Progression Table

| Phase | Phase Name | Primary Focus | Dependencies | Acceptance Gate |
| :--- | :--- | :--- | :--- | :--- |
| **0** | **Discovery & Blueprint** | Workspace audit, complete system design, technical docs | None | Complete 38-section discovery & Phase-0 documentation approved |
| **1** | **Foundation** | Monorepo structure, FastAPI skeleton, Docker Compose, CI | Phase 0 | `docker compose up` starts dev environment; `/health` returns 200 |
| **2** | **Database** | SQLAlchemy async models, Alembic migrations, CRUD repos | Phase 1 | `alembic upgrade head` succeeds; DB CRUD unit tests pass |
| **3** | **GitHub Integration** | Webhook endpoint, HMAC verification, PR metadata parsing | Phase 2 | HMAC test passes; valid webhook creates `ReviewJob` record |
| **4** | **Queue & Worker** | Redis streams/lists, background review worker, retries | Phase 3 | Review job enqueued via webhook is processed asynchronously by worker |
| **5** | **Scanner Engine** | Semgrep, Bandit, Gitleaks, ESLint adapters & normalization | Phase 4 | Target repo scan returns typed `NormalizedScanResult[]` |
| **6** | **Finding Engine** | Deterministic SHA-256 fingerprinting, deduplication | Phase 5 | Repeated findings grouped cleanly with preserved evidence chain |
| **7** | **Risk Engine** | Deterministic formula scoring (0-100) & risk grading | Phase 6 | Identical input produces identical score and grade |
| **8** | **LangGraph Supervisor**| Shared `ReviewState`, state machine, dynamic dispatch | Phase 6 | Supervisor routes PR to specialist agents with fallback recovery |
| **9** | **Specialist Agents** | Security, Quality, Testing, Doc, Dependency agents | Phase 8 | Each agent returns validated Pydantic models backed by evidence |
| **10** | **Policy RAG** | ChromaDB, chunking, semantic retrieval, anti-hallucination| Phase 9 | Accurate policy chunks retrieved; "No policy found" returned on mismatch |
| **11** | **Report Engine** | Markdown & JSON review summary synthesis | Phase 7, 10 | Structured review report generated with findings & policy citations |
| **12** | **Frontend Dashboard** | React, Vite, Tailwind, TanStack Query, Recharts | Phase 11 | Dashboard displays real review data, findings, risk trends |
| **13** | **GitHub Reporting** | Post Check Runs and concise PR summary comments | Phase 11 | GitHub PR receives formatted check status and summary review |
| **14** | **Remediation Engine** | LLM patch generator, sandboxed multi-stage validation | Phase 9 | Patch passes syntax check, test pass, scanner verification |
| **15** | **Fix PR Integration** | Automated creation of Fix PR for human approval | Phase 14 | Validated patch creates dedicated Fix PR on GitHub |
| **16** | **Security Hardening** | Prompt injection tests, path traversal, secret redaction | Phase 15 | Passes OWASP/CWE test battery against the platform itself |
| **17** | **Performance & Metrics**| Latency, throughput, token cost tracking, DLQ metrics | Phase 16 | Review latency <= 120s; measured metrics in `EVALUATION.md` |
| **18** | **Production DevOps** | Multi-stage Dockerfiles, production compose, CI pipeline | Phase 17 | All CI steps pass; images build cleanly with zero vulnerabilities |
| **19** | **Final System Test** | End-to-end demonstration scenario validation | Phase 18 | Full E2E loop runs successfully from PR opening to Fix PR merge |

---

## Progression Rule
After every phase is completed, the agent must **STOP** and wait for explicit human user approval before proceeding to the next phase.
