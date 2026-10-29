# CodeGuardian AI — Architectural Decision Records (ADR)

**Document:** Formal Architecture Decision Records  
**Status:** Approved Architectural Baseline  
**Version:** 1.0.0 (Phase 0)  

---

## ADR-001: Monorepo Structure for Full-Stack Systems

- **Date:** 2026-09-30
- **Context:** CodeGuardian AI consists of a FastAPI backend, a React frontend, static analysis configurations, shared policy documents, benchmark datasets, and deployment scripts. We needed to choose between multi-repo vs monorepo.
- **Options Considered:**
  1. Multi-repo (separate repos for frontend, backend, docs, scanners).
  2. Monorepo (unified repo with `apps/`, `scanners/`, `policies/`, `docs/`).
- **Chosen Approach:** Monorepo.
- **Reason:** Simplifies end-to-end integration testing, eliminates repository synchronization overhead for the 4-person B.Tech team, enables single Docker Compose orchestration, and provides a unified submission repository.
- **Consequences:** Requires clean folder isolation and independent dependency management for `apps/backend` and `apps/frontend`.

---

## ADR-002: Asynchronous Job Processing via Redis Queue

- **Date:** 2026-09-30
- **Context:** GitHub webhooks require acknowledgement within seconds, while static analysis and multi-agent reasoning take 15 to 90 seconds.
- **Options Considered:**
  1. Synchronous processing within webhook HTTP handler.
  2. In-memory background tasks (`BackgroundTasks` in FastAPI).
  3. Redis-backed job queue with dedicated worker processes.
  4. Apache Kafka.
- **Chosen Approach:** Redis-backed job queue with dedicated worker processes.
- **Reason:** Synchronous handling causes GitHub webhook timeouts. In-memory tasks lack persistence and crash if the API restarts. Kafka is overengineered for this workload. Redis provides fast, persistent queuing with easy horizontal worker scaling.
- **Consequences:** Introduces Redis as an infrastructure dependency. Requires worker health monitoring and dead-letter queues.

---

## ADR-003: Multi-Agent Orchestration with LangGraph

- **Date:** 2026-09-30
- **Context:** We require structured coordination between Supervisor, Security, Quality, Testing, Documentation, and Dependency agents with parallel execution and shared state reduction.
- **Options Considered:**
  1. Custom Python threading / asyncio scripts.
  2. AutoGen / CrewAI.
  3. LangGraph (StateGraph).
- **Chosen Approach:** LangGraph.
- **Reason:** LangGraph provides an explicit, cyclical graph-based state machine model where transitions are strictly typed and verifiable. Unlike open-ended conversational agent frameworks, LangGraph gives engineering control over state schemas, conditional branches, error fallbacks, and deterministic joins.
- **Consequences:** Team must adhere to pure state reducer functions and typed Pydantic state representations.

---

## ADR-004: Evidence-First Hybrid Review Model

- **Date:** 2026-09-30
- **Context:** LLMs frequently suffer from hallucinations, false positives, and inconsistencies when asked to find code bugs from raw diffs.
- **Options Considered:**
  1. Direct prompt with diff to LLM ("Find bugs in this code").
  2. Static analysis only (Semgrep/Bandit/ESLint).
  3. Evidence-First Hybrid Model: Static tools provide ground-truth evidence; specialized LLM agents interpret and contextualize evidence.
- **Chosen Approach:** Evidence-First Hybrid Model.
- **Reason:** Static analysis provides deterministic, reproducible detection of known patterns (CWEs, secrets, AST metrics). LLMs excel at understanding business logic, contextual impact, and explaining root causes. Combining them eradicates hallucinations while elevating static warnings into actionable engineering reports.
- **Consequences:** Pipeline requires a tool normalization layer before agent invocation.

---

## ADR-005: Deterministic Mathematical Risk Engine

- **Date:** 2026-09-30
- **Context:** Code review platforms must assign risk priorities (e.g. Critical, High, Medium, Low) and overall PR grades (A through F).
- **Options Considered:**
  1. Asking the LLM to output a risk score between 1 and 100.
  2. Hardcoded heuristics based purely on count of errors.
  3. Deterministic composite mathematical formula weighting severity, confidence, exploitability, policy violations, and test gaps.
- **Chosen Approach:** Deterministic composite mathematical formula.
- **Reason:** LLM-generated risk scores are non-reproducible (stochastic) and academically indefensible. A transparent mathematical formula guarantees that identical findings always produce the exact same risk score and grade.
- **Consequences:** The formula parameters and weights must be documented and validated against edge cases in unit tests.

---

## ADR-006: Lightweight Vector Storage via ChromaDB for RAG Policies

- **Date:** 2026-09-30
- **Context:** The system must ground review critiques in organizational coding standards and security baselines.
- **Options Considered:**
  1. ElasticSearch / Lucene keyword search.
  2. Cloud vector databases (Pinecone, Weaviate Cloud).
  3. ChromaDB (Embedded / Local persistent client).
- **Chosen Approach:** ChromaDB.
- **Reason:** ChromaDB is open source, runs locally without external cloud billing, integrates seamlessly with Python, and provides fast cosine distance queries with metadata pre-filtering.
- **Consequences:** Embeddings and vector collections must be persisted to a local or container volume.

---

## ADR-007: Subprocess Security and Sandboxing Rules

- **Date:** 2026-09-30
- **Context:** Running static analysis tools and executing test suites against untrusted PR code creates severe command injection and remote code execution vulnerabilities.
- **Options Considered:**
  1. Running CLI commands with `os.system` or `shell=True`.
  2. Restricted `asyncio.create_subprocess_exec` with explicit arguments and ephemeral directories.
- **Chosen Approach:** Restricted `asyncio.create_subprocess_exec` with explicit arguments, absolute path verification, non-root user execution, and hard execution timeouts.
- **Reason:** Completely prevents shell injection via malicious filepaths or git branch names.
- **Consequences:** All tool parameters must be individually validated and array-formatted.

---

## ADR-008: React + Vite + Tailwind CSS for Developer Portal

- **Date:** 2026-09-30
- **Context:** The user dashboard requires real-time telemetry, risk heatmaps, interactive diff viewing, and one-click remediation workflows.
- **Options Considered:**
  1. Server-rendered templates (Jinja2).
  2. Next.js.
  3. React + Vite + Tailwind CSS + TanStack Query.
- **Chosen Approach:** React + Vite + Tailwind CSS + TanStack Query.
- **Reason:** Provides an ultra-fast, modern developer UI with immediate hot module replacement, client-side caching, and responsive UI components suited for deep code diff visualization and real-time review updates.
- **Consequences:** Requires decoupled build and deployment pipeline alongside the backend API.

---

## ADR-009: Deterministic Static Analysis Adapter Architecture & Native Fallback Engines

- **Date:** 2026-10-03
- **Context:** CodeGuardian AI requires deterministic, tool-based evidence (Bandit, Semgrep, Gitleaks, ESLint) across diverse runtime environments (bare metal development, CI test containers, production Docker clusters). In minimalist or developer environments, external system binaries (e.g. `gitleaks`, `semgrep`, `bandit`, `eslint`) might not be universally present in the system `$PATH`.
- **Options Considered:**
  1. Fail hard whenever any external tool binary is absent.
  2. Pure mock/stub analyzers that fabricate canned findings when binaries are absent.
  3. Dual-execution adapter pattern: invoke official CLI subprocesses via secure `create_subprocess_exec` when binaries exist; seamlessly fallback to native Python AST, regex, and Shannon entropy analysis engines when binaries are not installed.
- **Chosen Approach:** Option 3 (Dual-execution adapter with native Python AST / regex fallback engines).
- **Reason:**
  - Guarantees 100% deterministic analysis and testability in all developer environments without requiring 4 external binary installations.
  - Ensures seamless production execution using official CLI binaries when deployed in complete Docker images.
  - Eliminates fake/mock data in favor of genuine AST analysis and cryptographic entropy calculation.
  - Adheres strictly to Rule 5 (no `shell=True`), Rule 8 (secret masking), and Rule 18 (path traversal defense via `_validate_relative_file_path`).
- **Consequences:** Scanner adapters must maintain both CLI JSON parsers and native pattern/AST rules synchronized with official security taxonomies (CWE and OWASP Top 10).

---

## ADR-010: Deterministic SHA-256 Fingerprinting, Proximity Clustering & Multi-Tool Evidence Merging

- **Date:** 2026-10-03
- **Context:** Multiple SAST scanners (Bandit, Semgrep, Gitleaks, ESLint) and subsequent AI specialist agents frequently detect overlapping issues on the same lines of code (e.g. Bandit reporting B608 and Semgrep reporting `python.sqli` on line 42). Presenting separate, uncoordinated findings degrades user experience, fragments triage workflows, and corrupts risk scores. We need a deterministic, reproducible mechanism to fingerprint, correlate, and merge findings while preserving complete audit evidence.
- **Options Considered:**
  1. No correlation: store all raw tool findings individually in the database and surface them unmerged.
  2. Non-deterministic AI LLM-based clustering during worker processing.
  3. Deterministic SHA-256 fingerprinting based on canonical path, line, category, and canonical issue type with proximity-based clustering (±3 lines) and full child evidence preservation in `finding_evidence`.
- **Chosen Approach:** Option 3 (Deterministic SHA-256 fingerprinting + proximity clustering + evidence graph).
- **Reason:**
  - Fingerprint formula `SHA256(canonical_path:line:category:canonical_issue)` guarantees strict idempotency across multiple review runs and pull request synchronization events.
  - Cross-tool rule taxonomy maps heterogeneous tool rule IDs (e.g., Bandit `B608`, Semgrep `semgrep.python.sqli.format`) to canonical CWE concepts (e.g., `cwe-89-sqli`), allowing seamless cross-tool deduplication.
  - Multi-tool consensus escalates confidence scores (`0.95` for multi-tool agreement) and takes the maximum severity of clustered findings.
  - Preserves 100% of raw evidence: each scanner's output, rule ID, raw message, and code snippet are permanently stored in the `finding_evidence` table linked to the parent `Finding`.
- **Consequences:** Changes in rule taxonomy mapping can alter future fingerprints. Migrations must maintain fingerprint stability across existing reviews.


