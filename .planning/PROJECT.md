# CodeGuardian AI — Autonomous Multi-Agent Code Review & DevSecOps Platform

## What This Is

CodeGuardian AI is an enterprise-grade autonomous DevSecOps and code review platform designed for high-velocity software engineering teams. It intercepts pull requests via secure GitHub webhooks, runs deterministic static analysis tools (Bandit, Semgrep, Gitleaks, ESLint), orchestrates a LangGraph multi-agent committee (Security, Quality, Testing, Docs, Dependency specialists), enforces internal policies via ChromaDB RAG, calculates mathematical risk scores, and generates sandboxed remediation pull requests on isolated branches.

## Core Value

Zero-hallucination, deterministic-first autonomous code review with verifiable evidence, explainable risk scoring, and safe human-in-the-loop automated remediation.

## Requirements

### Validated

- [x] **CORE-01**: Multi-tenant workspace isolation & Role-Based Access Control (`ADMIN`, `REVIEWER`, `DEVELOPER`) — Phase 1
- [x] **CORE-02**: Webhook HMAC SHA-256 constant-time verification & event idempotency replay defense — Phase 1
- [x] **CORE-03**: Dual-mode Redis Streams & In-Memory async review queue with exponential backoff & DLQ — Phase 2
- [x] **CORE-04**: Deterministic static scanner suite (Bandit, Semgrep, Gitleaks, ESLint) with subprocess sandboxing — Phase 2
- [x] **CORE-05**: LangGraph 5-specialist agent committee with supervisor routing and structured output — Phase 3
- [x] **CORE-06**: ChromaDB vector store policy knowledge base with anti-hallucination grounding — Phase 3
- [x] **CORE-07**: Deterministic mathematical risk scoring engine (0-100 score and A-F letter grade) — Phase 4
- [x] **CORE-08**: Comprehensive Sections A through M pull request audit reports — Phase 4
- [x] **CORE-09**: 5-stage sandboxed automated remediation engine — Phase 5
- [x] **CORE-10**: Isolated branch creation (`codeguardian/fix-...`) and automated draft pull request generator — Phase 5
- [x] **CORE-11**: Security hardening: PromptGuard (OWASP LLM01), secret masking, path traversal defense — Phase 6
- [x] **CORE-12**: SLA tracking, latency performance monitoring, and academic evaluation metrics — Phase 6
- [x] **CORE-13**: Cosmic Plasma Nebula Dark React 18 dashboard with live charts, diff viewer, and finding explorer — Phase 7
- [x] **EXT-01**: AST static complexity and NLP code optimization engine ($O(N^2) \to O(N)$) — Phase 8
- [x] **EXT-02**: Multilingual technical explanations across 6 languages (English, Hindi, Hinglish, Urdu, Marathi, Gujarati) — Phase 8
- [x] **EXT-03**: Real-time PCM WAV audio synthesis streaming endpoint and Web Speech player — Phase 8

### Active

- [x] **GSD-AUDIT**: Full project audit and GSD milestone verification confirming 100% test passing and production deployment readiness.

### Out of Scope

- **Direct commits to default branch (`main` / `master`):** Never permitted; all automated fixes strictly create isolated branches and draft PRs for human approval.
- **Unverified code execution:** External arbitrary code is never executed without AST syntax validation and sandboxed subprocess containment.

## Context

- **Test Suite:** 194 automated test cases passing in 31 seconds.
- **Frontend Stack:** React 18, TypeScript 5.4, Vite 5.1, Tailwind CSS 3.4.
- **Backend Stack:** Python 3.11/3.14, FastAPI, LangGraph, SQLAlchemy 2.0 Async, ChromaDB, Redis.
- **Deployment:** Docker & Docker Compose (`docker-compose.yml`, `docker-compose.prod.yml`).

## Constraints

- **Security Constraint:** Webhooks must reject forged signatures with 401 Unauthorized within constant time.
- **Reliability Constraint:** Scanner or LLM failures must produce explicit error statuses rather than false clean scores.
- **Persistence Constraint:** All review runs, agent decisions, and findings must be permanently recorded with immutable timestamps.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Deterministic scanners run prior to LLM agents | Ground truth facts prevent AI hallucinations and save token costs | Passed |
| LangGraph StateGraph with Supervisor | Modular specialist routing prevents context pollution | Passed |
| Draft PRs on isolated `codeguardian/fix-*` branches | Guarantees human-in-the-loop review and prevents unintended code modification | Passed |
| In-Memory Async DB & Client fixture in tests | Ensures zero test cross-contamination with on-disk development database | Passed |

---
*Last updated: 2026-10-24 after GSD Codebase Mapping & Test Suite Hardening*
