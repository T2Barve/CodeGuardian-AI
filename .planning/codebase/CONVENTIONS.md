# Coding Conventions & Patterns

**Analysis Date:** 2026-10-24

## 1. Backend (Python & FastAPI)

### Code Style & Formatting
- **PEP 8 Alignment:** 4-space indentation, snake_case function and variable names, PascalCase class names.
- **Type Annotations:** Mandatory type hints on all public functions, methods, and FastAPI path operations.
- **Schemas:** Pydantic `BaseModel` models for every request payload and response contract (`app/schemas/`).

### Async Programming
- **Asynchronous Everywhere:** Every route handler and database interaction uses `async def` and `await`.
- **SQLAlchemy 2.0 Syntax:** Pure 2.0 select syntax (`select(Model).where(...)`) executed via `await db.execute(...)`.
- **Greenlet Safety:** Async SQLite operations managed cleanly through `aiosqlite` and `async_sessionmaker`.

### Error Handling & Security Conventions
- **Explicit Subprocesses:** All static tool executions use `subprocess.run(args, shell=False, capture_output=True, timeout=...)`. Never pass raw strings to shell.
- **Constant-Time Verification:** Webhook secrets and sensitive tokens compared strictly using `hmac.compare_digest()`.
- **OWASP LLM Defense:** Inbound prompts and git diffs passed through `PromptGuard` to neutralize instruction override injection attacks before reaching LLM state graphs.
- **Secret Masking:** API keys, GitHub tokens, and private credentials automatically masked via `SecretMasker` before logging or persisting.

## 2. Frontend (TypeScript & React)

### Component & State Architecture
- **Functional Components:** React 18 functional components with explicit TypeScript interfaces.
- **Server State:** TanStack React Query (`useQuery`, `useMutation`) for caching, optimistic updates, and automatic invalidation.
- **Router:** React Router DOM v6 with declarative nested layout (`Sidebar`, `Header`, `<Outlet />`).

### UI & Styling Guidelines
- **Cosmic Plasma Nebula Theme:** Dark navy/black backgrounds (`#0a0d14`, `#101726`), glowing cyan/purple borders, glassmorphism cards (`backdrop-blur-md`).
- **Zero Raw Layout Bugs:** All data screens implement full three-state handling:
  1. *Loading State:* Animated skeleton loaders matching target layout.
  2. *Error State:* Human-readable failure banner with retry action.
  3. *Empty State:* Clear iconography and onboarding action when no data exists.

## 3. Database Conventions

- **Immutable Audit Trails:** Historical review runs, agent decisions, and remediation attempts are write-only/append-only.
- **Tenant Scoping:** All repository and review lookups verify ownership or tenant isolation at query boundary.
- **Deterministic Keys:** Unique constraints on external identifiers (`github_repo_id`, `commit_sha`).

---
*Conventions analysis: 2026-10-24*
