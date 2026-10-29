# CodeGuardian AI — Product Requirements Document (PRD)

**Project Title:** CodeGuardian AI — Autonomous Multi-Agent Code Review & DevSecOps Platform  
**Academic Program:** B.Tech Final Year Major Project  
**Team Members:** Darshan (Frontend & Visualization), Tanishq (AI & Multi-Agent & RAG), Mayur (Backend & DB & GitHub), Veer (Security & Scanners & DevSecOps)  
**Primary SDG:** SDG 9 — Industry, Innovation and Infrastructure  
**Secondary SDG:** SDG 8 — Decent Work and Economic Growth  
**Version:** 1.0.0 (Phase 0 Baseline)  
**Date:** 2026-09-30  

---

## 1. Problem Statement

Modern software engineering teams face severe constraints when reviewing GitHub Pull Requests (PRs). Manual PR review suffers from:
1. **Human Fatigue & Bottlenecks:** Senior engineers spend hours reviewing boilerplate, missing subtle vulnerabilities or architectural deviations under tight deadlines.
2. **Siloed Static Analysis:** Traditional SAST tools (e.g., Semgrep, Bandit, ESLint) produce disconnected findings, flood developers with false positives, and lack contextual understanding of business logic or change impact.
3. **Absence of Unified Reasoning:** Static analysis does not synthesize code quality, test gap risks, architectural compliance, and security impact into a coherent, risk-prioritized engineering assessment.
4. **Remediation Gap:** Review comments point out flaws without generating safe, syntactically and semantically validated fixes, leaving developers to research and resolve issues manually.
5. **Academic/Enterprise Rigor Gap:** Existing AI coding assistants often act as unconstrained LLM wrappers ("black-box prompt-in, code-out") without deterministic verification, evidence chains, or sandboxed validation.

CodeGuardian AI bridges this gap by orchestrating deterministic static analysis engines with a LangGraph-coordinated multi-agent reasoning architecture, backed by RAG-enforced engineering policies, verifiable risk scoring, and sandboxed auto-remediation with mandatory human approval.

---

## 2. Target Users and Personas

1. **Software Developers (Submitters):**
   - *Goal:* Receive rapid, actionable, context-aware PR reviews with specific code snippets, rationale, and verified one-click patch proposals.
   - *Pain Point:* Cryptic linter warnings, delayed PR approvals, unclear company standard enforcement.
2. **Tech Leads & Senior Reviewers (Review Approvers):**
   - *Goal:* Review aggregated risk scores, verify test coverage gaps, and audit security compliance before merge.
   - *Pain Point:* Review exhaustion, repetitive reviews for style/policy violations, undetected regression risks.
3. **DevSecOps / AppSec Engineers (Security Auditors):**
   - *Goal:* Continuous enforcement of OWASP Top 10, CWE checks, secret leakage prevention, and verifiable audit trails.
   - *Pain Point:* Developers ignoring security scanner output or blindly disabling security rules.
4. **Academic Mentors & Evaluators (B.Tech Examiners):**
   - *Goal:* Assess software architecture, multi-agent systems, deterministic scoring formulas, empirical benchmark evaluations, and adherence to clean engineering practices.

---

## 3. High-Level System Goals & Non-Goals

### System Goals
- Ingest GitHub Pull Request webhooks securely using HMAC SHA-256 signatures.
- Process reviews asynchronously via Redis job queue to prevent API gateway timeouts.
- Execute deterministic security and quality scanners (Semgrep, Bandit, Gitleaks, ESLint) in isolated workspaces.
- Orchestrate specialized LangGraph agents (Supervisor, Security, Quality, Testing, Documentation, Dependency).
- Ground review logic in repository-specific engineering policies via Vector RAG (ChromaDB).
- Deduplicate, correlate, and fingerprint findings across scanners and agents into a unified evidence graph.
- Compute reproducible, deterministic risk scores based on a documented mathematical formula.
- Deliver findings via a high-performance React dashboard and non-intrusive GitHub PR review comments.
- Provide sandboxed, multi-stage validated patch generation (syntax -> unit test -> re-scan -> regression check) with human-in-the-loop merge authorization.

### Non-Goals
- **NOT** a general-purpose chat interface or ChatGPT clone.
- **NOT** an autonomous auto-merge bot that merges code without human sign-off.
- **NOT** an unrestricted code generator operating outside of identified PR findings.
- **NOT** a production deployment/CD orchestrator.
- **NOT** a system that blindly trusts LLM outputs without deterministic schema and tool verification.

---

## 4. Functional Requirements

### FR-01: GitHub Ingestion & Webhook Verification
- The system shall expose a secure webhook endpoint `POST /api/v1/github/webhook`.
- Verify the `X-Hub-Signature-256` HMAC header against a pre-shared secret.
- Enforce idempotency via delivery GUID (`X-GitHub-Delivery`) to reject duplicate events.
- Parse `pull_request` events (opened, synchronize, reopened) and enqueue a background review job in Redis within < 500ms.

### FR-02: Deterministic Static Analysis Pipeline
- Run containerized/subprocess static scanners with timeout limits and isolated working trees:
  - **Bandit:** AST-based Python security scanning.
  - **Semgrep:** Pattern-matching static rules for polyglot vulnerabilities.
  - **Gitleaks:** High-entropy secret and credential detection in diffs.
  - **ESLint:** JavaScript/TypeScript static quality and syntax linting.
- Normalize scanner outputs to a standardized Pydantic `NormalizedScanResult` schema.

### FR-03: Multi-Agent Review Orchestration (LangGraph)
- **Supervisor Agent:** Orchestrates workflow, performs file classification, partitions tasks, and controls conditional branching.
- **Security Agent:** Analyzes vulnerabilities, correlates scanner evidence, evaluates CWE/OWASP vectors, and assesses exploitability.
- **Quality Agent:** Inspects code complexity (cyclomatic/cognitive), maintainability, code smells, duplication, and RAG policy adherence.
- **Testing Agent:** Computes test coverage gaps, maps modified AST functions to existing test suites, and flags untested branches.
- **Documentation Agent:** Identifies missing public API docstrings, invalid parameter docs, and outdated documentation.
- **Dependency Agent:** Inspects package manifest modifications (`package.json`, `requirements.txt`, `Pipfile`), detects untrusted packages, and audits version pinning.

### FR-04: Retrieval-Augmented Generation (RAG) Policy Engine
- Provide an API and UI to ingest engineering guidelines (Markdown, PDF, TXT, DOCX).
- Chunk policies semantically, compute embeddings, and store them in ChromaDB.
- Retrieve top-k relevant policy chunks during agent execution filtered by language, file path, and rule category.
- Enforce strict hallucination guardrails: if no policy matches, explicitly state `"No applicable project policy was retrieved"` and forbid fabricated standard citations.

### FR-05: Finding Correlation & Deterministic Risk Engine
- Generate deterministic SHA-256 fingerprints for each finding: `sha256(repo_id + file_path + line_start + category + rule_id)`.
- Correlate identical issues identified across both static scanners and LLM agents into a unified `Finding` entity while retaining distinct `FindingEvidence` records.
- Calculate risk scores using a deterministic composite formula based on severity, confidence, exploitability, policy violations, and test gap impact.

### FR-06: Controlled Remediation Engine
- For a selected finding, generate a candidate unified diff / git patch using the LLM.
- Execute validation inside an isolated sandbox environment:
  1. Patch application (`git apply --check`).
  2. AST syntax check.
  3. Pre-existing test suite execution.
  4. Targeted scanner re-run (verifying finding elimination without introducing new findings).
  5. Regression test suite pass.
- If and only if all stages pass, allow creation of an isolated Fix Pull Request on GitHub. Never push directly to default branches.

### FR-07: Developer Dashboard & Observability
- Interactive web console built with React, Vite, TypeScript, and Tailwind CSS.
- Real-time review timeline, risk heatmaps, finding explorer with syntax-highlighted code snippets, and remediation status.
- System observability endpoints: `GET /health`, `GET /ready`, Redis queue metrics, and database connection checks.

---

## 5. Non-Functional Requirements

### NFR-01: Performance & Latency
- Webhook response latency: <= 500ms (asynchronous acknowledgement).
- End-to-end review duration: <= 120s for PRs with < 20 changed files.
- UI initial load: <= 1.5s on broadband connections.

### NFR-02: Security & Isolation
- Treat all repository code, diffs, comments, and commit messages as **untrusted data**.
- Enforce prompt injection defense via strict delimiters, system instructions, and schema validation.
- Subprocess execution must run with restricted permissions, execution timeouts (max 60s per scanner), and non-root execution.
- Zero secret leakage in API responses, logs, or LLM prompts.

### NFR-03: Reliability & Fault Tolerance
- A failure in an individual specialist agent must not crash the entire review run. The Supervisor must collect partial findings, log the agent error, and finalize the report.
- Redis job retries with exponential backoff and dead-letter queue (DLQ) support for unrecoverable errors.

### NFR-04: Reproducibility & Auditability
- The risk scoring engine must produce identical scores given identical finding inputs.
- All actions (webhook received, review queued, agent invoked, finding created, remediation tested, PR opened) must be logged in `AuditLog`.

---

## 6. Assumptions and Constraints

- Primary development platform: Windows / Docker environment.
- Supported target languages for initial benchmark: Python and TypeScript/JavaScript.
- LLM Provider: Configurable via modular abstraction layer (OpenAI, Groq, Ollama, Gemini).
- Academic scope: Scaled for demonstration with synthetic benchmarks and real-world GitHub repositories without requiring cloud hyper-scalers.
