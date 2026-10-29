# CodeGuardian AI — Engineering Rules & Operational Constraints

**Document:** Engineering Standards, Safety Invariants & Architectural Rules  
**Status:** Mandatory Active Constraint  
**Version:** 1.0.0 (Phase 0)  

---

## 1. Fundamental Architectural Invariants

### Rule 1: Evidence-Driven Architecture
- **TOOLS PROVIDE EVIDENCE.**
- **AGENTS INTERPRET EVIDENCE.**
- **SUPERVISOR ORCHESTRATES.**
- **AGGREGATOR CORRELATES.**
- **RISK ENGINE PRIORITIZES.**
- **HUMAN REVIEWS.**
- *Violation:* Directly sending raw PR diffs to an LLM without static scanner evidence or AST analysis is strictly forbidden.

### Rule 2: Trust Model Boundary
- **Trusted Assets:** System instructions, internal security policies, validated scanner results, application configs, database state.
- **Untrusted Assets:** All repository source files, diff content, PR descriptions, issue text, commit messages, author metadata, and raw AI-generated code patches.
- *Requirement:* All untrusted code must be processed within delimiters, sanitized before rendering, and validated in an isolated sandbox.

### Rule 3: Deterministic Risk Engine
- Risk scores ($0.0 - 100.0$) and grades ($A - F$) must be derived exclusively via the deterministic mathematical formula defined in `ARCHITECTURE.md` and `SYSTEM_DESIGN.md`.
- Agents provide qualitative commentary and exploitability assessments, but the numerical score is strictly computed by Python code.

### Rule 4: LLM Provider Abstraction
- Agents, services, and endpoints must **never** import provider-specific SDKs (`import openai`, `import google.generativeai`) directly.
- All AI calls must pass through `LLMService` implementing the unified `BaseLLMProvider` interface (`generate()`, `generate_structured()`, `embed()`).

### Rule 5: Zero Subprocess Shell Execution
- All system tool invocations (Semgrep, Bandit, Gitleaks, ESLint, Git) must use `asyncio.create_subprocess_exec` with explicit argument arrays.
- `shell=True` or `os.system` is completely prohibited across the entire project.

---

## 2. Anti-Fabrication & Academic Honesty Principles

### Rule 6: No Fake Metrics
- Metrics like "95% accuracy", "80% faster review", "99% detection" must **never** be hardcoded or fabricated in reports, documentation, or the UI.
- All metrics reported in `docs/EVALUATION.md` must be empirically calculated from actual execution runs against the benchmark dataset.

### Rule 7: No Cosmetic "Mock" Agents
- Every agent displayed on the UI or documented in the architecture (Supervisor, Security, Quality, Testing, Documentation, Dependency) must execute real backend code with LangGraph nodes and typed Pydantic models.

### Rule 8: No Unchecked Auto-Fixes
- An automated code fix will never be submitted as a Pull Request unless it has passed the complete 5-stage validation pipeline (syntax check, unit test execution, targeted scanner verification, regression check, and human approval).
- The platform will **never** merge code directly into default branches.

---

## 3. Code & API Guidelines

- **Python Backend:**
  - Python 3.12+ / 3.14.
  - Strict type annotations (`typing`, Pydantic v2).
  - Asynchronous I/O (`async` / `await`) for all database queries and external HTTP requests.
  - Formatted with `ruff` and type-checked with `mypy`.
- **TypeScript Frontend:**
  - Strict mode enabled (`tsconfig.json`).
  - No `any` types; all API responses must have corresponding TypeScript interfaces matching Pydantic schemas.
  - Tailwind CSS for responsive, modern, developer-grade UI styling.
