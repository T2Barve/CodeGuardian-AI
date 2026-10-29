# Testing Architecture & Practices

**Analysis Date:** 2026-10-24

## 1. Test Suite Overview

- **Test Framework:** `pytest` 9.0.2 with `pytest-asyncio` (AUTO mode) and `pytest-timeout`
- **Total Automated Tests:** 194 test cases (100% passing)
- **Execution Time:** ~31 seconds for complete end-to-end and unit suite
- **Zero External Dependencies in Tests:** In-memory SQLite async engine (`StaticPool`), mocked external GitHub and LLM API calls.

## 2. Test Directory Layout

```
apps/backend/tests/
├── conftest.py                     # Central fixtures (test_db, db_session, async_client)
├── integration/                    # Multi-component integration tests (4 modules)
│   ├── test_database.py            # Multi-tenant isolation & transaction rollback
│   ├── test_e2e_lifecycle.py       # Full PR review run from webhook to report
│   ├── test_github_webhook.py      # Webhook delivery idempotency & deduplication
│   └── test_worker_lifecycle.py    # Queue processing, retry backoff, and DLQ
└── unit/                           # Isolated unit tests (22 modules)
    ├── test_code_optimization.py   # AST static complexity & optimization rules
    ├── test_dashboard_api.py       # Aggregated stats, SLA metrics, finding counts
    ├── test_devops_configuration.py# Docker compose, env vars, health checks
    ├── test_finding_engine.py      # Deduplication, fingerprinting, severity mapping
    ├── test_fix_pr.py              # Isolated branch creation & draft PR formatting
    ├── test_github_client.py       # GitHub REST client error handling & parsing
    ├── test_github_reporting.py    # Check runs, annotations (max 50), PR comments
    ├── test_health.py              # System health & dependency readiness probes
    ├── test_langgraph_supervisor.py# Supervisor routing & state transitions
    ├── test_multilingual_voice.py  # 6 language translations & WAV audio synthesis
    ├── test_performance_metrics.py # Processing latency, agent time, SLA formulas
    ├── test_policy_rag.py          # ChromaDB vector store indexing & similarity query
    ├── test_remediation_engine.py  # 5-stage validation sandbox & fix generation
    ├── test_report_engine.py       # Sections A-M report formatting & persistence
    ├── test_repository_onboarding.py# URL validation, SSRF defense, repo creation
    ├── test_review_queue.py        # Redis streams & in-memory queue push/pop
    ├── test_risk_engine.py         # Mathematical risk scoring & grade calculation
    ├── test_scanners.py            # Bandit, Semgrep, Gitleaks, ESLint adapters
    ├── test_security_hardening.py  # PromptGuard, secret masking, path traversal
    ├── test_specialist_agents.py   # Security, quality, testing, docs, dependency agents
    └── test_webhook_security.py    # HMAC SHA-256 signature verification tests
```

## 3. How to Run Tests

### Backend Tests
```bash
# Run all tests with concise progress
python -m pytest apps/backend/tests -q

# Run specific unit test with verbose output
python -m pytest apps/backend/tests/unit/test_risk_engine.py -v

# Run integration tests only
python -m pytest apps/backend/tests/integration -v
```

### Frontend Build Verification
```bash
cd apps/frontend
npm run build
```
*Compiles TypeScript with zero errors and produces optimized Vite production bundle in ~4 seconds.*

---
*Testing analysis: 2026-10-24*
