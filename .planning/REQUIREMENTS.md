# Requirements: CodeGuardian AI

**Defined:** 2026-10-24  
**Core Value:** Zero-hallucination, deterministic-first autonomous code review with verifiable evidence, explainable risk scoring, and safe human-in-the-loop automated remediation.

## v1 Requirements

### Authentication & Workspace Isolation
- [x] **AUTH-01**: Role-based access control with `ADMIN`, `REVIEWER`, and `DEVELOPER` permissions
- [x] **AUTH-02**: Organization and repository multi-tenant query boundary isolation preventing IDOR
- [x] **AUTH-03**: Secure GitHub OAuth & API token authentication

### GitHub Integration & Ingress
- [x] **GH-01**: Constant-time HMAC SHA-256 signature verification (`X-Hub-Signature-256`)
- [x] **GH-02**: Webhook delivery deduplication using SHA-256 event ID and commit hash tracking
- [x] **GH-03**: Pull request event ingestion (`opened`, `synchronize`, `reopened`)
- [x] **GH-04**: GitHub Check Runs creation and batched inline code annotations (max 50 per call)

### Deterministic Static Analysis Suite
- [x] **SCAN-01**: Subprocess sandboxed Bandit execution for Python security analysis (`shell=False`)
- [x] **SCAN-02**: Semgrep multi-language semantic rule scanning
- [x] **SCAN-03**: Gitleaks high-entropy credential and API token detection
- [x] **SCAN-04**: ESLint JavaScript/TypeScript code quality and syntax scanning
- [x] **SCAN-05**: Explicit error status propagation when scanner tools fail or are missing

### Multi-Agent System & Policy RAG
- [x] **AGENT-01**: LangGraph StateGraph orchestrating 5 specialist agents with Supervisor routing
- [x] **AGENT-02**: Security Specialist evaluating OWASP Top 10 vulnerabilities
- [x] **AGENT-03**: Quality Specialist evaluating cyclomatic complexity and code maintainability
- [x] **AGENT-04**: Testing Specialist evaluating test adequacy and regression risk
- [x] **AGENT-05**: Documentation Specialist verifying docstring and API contract accuracy
- [x] **AGENT-06**: Dependency Specialist checking supply chain CVEs and licenses
- [x] **RAG-01**: ChromaDB vector store indexing internal security and engineering policies
- [x] **RAG-02**: Grounded policy retrieval preventing ungrounded agent hallucinations

### Risk Engine & Persisted Reports
- [x] **RISK-01**: Mathematical risk calculation formula (0-100 score and A-F letter grade)
- [x] **REPORT-01**: Persisted immutable reports covering comprehensive Sections A through M
- [x] **REPORT-02**: Revision tracking across multiple commit pushes per pull request

### Automated Remediation & Fix PRs
- [x] **FIX-01**: 5-stage validation sandbox (AST syntax, re-scan, unit test, regression guard)
- [x] **FIX-02**: Creation of isolated branch `codeguardian/fix-{finding_id}`
- [x] **FIX-03**: Automated draft PR creation requesting human reviewer sign-off

### Application Security Hardening
- [x] **SEC-01**: PromptGuard neural defense against OWASP LLM01 prompt injection in diffs
- [x] **SEC-02**: SecretMasker regex utility sanitizing credentials before logging or database storage
- [x] **SEC-03**: Path traversal sanitization preventing arbitrary file reads

### Advanced Intelligence Extensions
- [x] **EXT-01**: AST static algorithmic complexity analyzer ($O(N^2) \to O(N)$)
- [x] **EXT-02**: Multilingual technical explanations across 6 languages (English, Hindi, Hinglish, Urdu, Marathi, Gujarati)
- [x] **EXT-03**: Real-time PCM WAV audio streaming endpoint and Web Speech synthesizer

### Cosmic Plasma Nebula Dashboard
- [x] **UI-01**: Responsive React 18 + Vite dashboard with live API data binding
- [x] **UI-02**: Interactive ScoreGauge SVG component and risk breakdown charts
- [x] **UI-03**: Interactive DiffViewer highlighting security findings with line markers
- [x] **UI-04**: Multilingual audio player with voice and language selection controls

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUTH-01..03 | Phase 1: Security & Identity | Complete |
| GH-01..04 | Phase 2: Ingress & Queue | Complete |
| SCAN-01..05 | Phase 3: Deterministic Scanners | Complete |
| AGENT-01..06, RAG-01..02 | Phase 4: LangGraph & RAG | Complete |
| RISK-01, REPORT-01..02 | Phase 5: Risk & Reporting | Complete |
| FIX-01..03 | Phase 6: Remediation Sandbox | Complete |
| SEC-01..03 | Phase 7: Application Hardening | Complete |
| EXT-01..03 | Phase 8: Advanced Extensions | Complete |
| UI-01..04 | Phase 9: Nebula Dashboard | Complete |

---
*Requirements verified: 2026-10-24*
