# Roadmap: CodeGuardian AI

## Overview

CodeGuardian AI is built across nine structured phases spanning identity, webhook ingress, deterministic static scanners, multi-agent LangGraph intelligence, policy RAG, deterministic risk calculation, 5-stage sandboxed remediation, security hardening, and a high-performance React dashboard.

## Phases

- [x] **Phase 1: Security & Identity Foundation** - Role-based access control, tenant query isolation, JWT sessions
- [x] **Phase 2: Webhook Ingress & Distributed Queue** - Constant-time HMAC-SHA256 verification, Redis Streams, In-memory queue
- [x] **Phase 3: Deterministic Static Scanners** - Subprocess sandboxed Bandit, Semgrep, Gitleaks, ESLint adapters
- [x] **Phase 4: Multi-Agent Committee & Policy RAG** - LangGraph 5 specialist agents + supervisor, ChromaDB vector store
- [x] **Phase 5: Mathematical Risk Engine & Reports** - Formula-driven risk scoring (0-100, A-F), Sections A-M reports
- [x] **Phase 6: Sandboxed Remediation & Fix PRs** - 5-stage validation sandbox, isolated git branch and draft PR generator
- [x] **Phase 7: Application Hardening & Defense** - PromptGuard (OWASP LLM01), secret masking, path traversal checks
- [x] **Phase 8: Advanced Intelligence Extensions** - AST algorithmic complexity optimization, multilingual explanations, audio WAV streaming
- [x] **Phase 9: Cosmic Plasma Nebula Dashboard** - Responsive React 18, Vite, Tailwind CSS, live charts, SVG gauges

## Phase Details

### Phase 1: Security & Identity Foundation
**Goal**: Enforce strict workspace boundaries and role-based permissions.
**Requirements**: AUTH-01, AUTH-02, AUTH-03
**Success Criteria**:
  1. Unauthorized API queries return 401 Unauthorized.
  2. Queries for cross-tenant resources return 404/403.
  3. API tokens and passwords stored hashed.
**Plans**: 1 plan

Plans:
- [x] 01-01: Establish multi-tenant isolation, role-based authorization, and user identity persistence.

### Phase 2: Webhook Ingress & Distributed Queue
**Goal**: Reliable, non-blocking ingestion of pull request events from GitHub.
**Requirements**: GH-01, GH-02, GH-03, GH-04
**Success Criteria**:
  1. Forged HMAC signatures rejected in constant time.
  2. Duplicate webhook deliveries ignored via SHA-256 fingerprint deduplication.
  3. Review jobs queued for background worker consumption with exponential backoff and DLQ.
**Plans**: 1 plan

Plans:
- [x] 02-01: Establish high-throughput GitHub webhook ingestion with cryptographic signature validation and async background task queuing.

### Phase 3: Deterministic Static Scanners
**Goal**: Run reliable static analysis tools before AI evaluation.
**Requirements**: SCAN-01, SCAN-02, SCAN-03, SCAN-04, SCAN-05
**Success Criteria**:
  1. Bandit, Semgrep, Gitleaks, ESLint executed in sandboxed subprocesses (`shell=False`).
  2. Missing scanner binaries report explicit errors rather than false clean scores.
  3. Findings normalized into standard schema with file, line, and evidence snippets.
**Plans**: 1 plan

Plans:
- [x] 03-01: Implement static analysis adapters for Bandit, Semgrep, Gitleaks, and ESLint with schema normalization and subprocess isolation.

### Phase 4: Multi-Agent Committee & Policy RAG
**Goal**: Comprehensive contextual review using specialist AI agents grounded in company policies.
**Requirements**: AGENT-01..06, RAG-01..02
**Success Criteria**:
  1. LangGraph StateGraph orchestrates Security, Quality, Testing, Docs, and Dependency specialists.
  2. ChromaDB provides semantic retrieval of organizational engineering policies.
  3. Missing LLM API keys fall back gracefully to deterministic static analysis.
**Plans**: 1 plan

Plans:
- [x] 04-01: Build the LangGraph multi-agent review graph with 5 specialist agents and ChromaDB RAG policy grounding.

### Phase 5: Mathematical Risk Engine & Reports
**Goal**: Deterministic risk quantification and human-readable audit reports.
**Requirements**: RISK-01, REPORT-01, REPORT-02
**Success Criteria**:
  1. Risk score calculated using verified mathematical formula bounded between 0 and 100.
  2. Sections A through M reports persisted in database.
  3. Commit revisions tracked historically across each pull request.
**Plans**: 1 plan

Plans:
- [x] 05-01: Implement mathematical risk calculation and structured Section A-M pull request audit report generation.

### Phase 6: Sandboxed Remediation & Fix PRs
**Goal**: Automated code patch generation with strict safety guardrails.
**Requirements**: FIX-01, FIX-02, FIX-03
**Success Criteria**:
  1. Patches validated through 5-stage sandbox (AST syntax, re-scan, unit test, regression guard).
  2. Fix branch created with prefix `codeguardian/fix-...` and draft PR opened for human approval.
  3. Zero commits made directly to protected default branch.
**Plans**: 1 plan

Plans:
- [x] 06-01: Implement safe, automated code patch generation with 5-stage sandbox validation and draft PR creation.

### Phase 7: Application Hardening & Defense
**Goal**: Protect the application from adversarial input and sensitive leaks.
**Requirements**: SEC-01, SEC-02, SEC-03
**Success Criteria**:
  1. PromptGuard rejects prompt injection attempts embedded inside code diffs.
  2. SecretMasker redacts high-entropy keys from logs and database fields.
  3. Path traversal attempts (`../`) are safely rejected.
**Plans**: 1 plan

Plans:
- [x] 07-01: Harden the entire application stack against adversarial inputs, prompt injection, and credential leakage.

### Phase 8: Advanced Intelligence Extensions
**Goal**: Cutting-edge code optimization and multilingual accessibility.
**Requirements**: EXT-01, EXT-02, EXT-03
**Success Criteria**:
  1. AST optimizer detects $O(N^2)$ nested loops and generates $O(N)$ replacements.
  2. Technical explanations translated across 6 languages (English, Hindi, Hinglish, Urdu, Marathi, Gujarati).
  3. Real-time PCM WAV audio synthesis streams at `/api/v1/optimization/audio`.
**Plans**: 1 plan

Plans:
- [x] 08-01: Implement AST-driven algorithmic code optimization, multilingual technical localization, and AI voice explanation synthesis.

### Phase 9: Cosmic Plasma Nebula Dashboard
**Goal**: Visually stunning and responsive user interface for monitoring DevSecOps health.
**Requirements**: UI-01, UI-02, UI-03, UI-04
**Success Criteria**:
  1. React 18 + Vite frontend compiles with zero TypeScript errors.
  2. Clean Cosmic Plasma Nebula dark mode with glassmorphic cards and SVG risk gauges.
  3. All dashboard counters and review reports consume live backend API endpoints.
**Plans**: 1 plan

Plans:
- [x] 09-01: Build a visually stunning, responsive React 18 frontend dashboard bound to real backend APIs.

---
*Roadmap verified: 2026-10-24*
