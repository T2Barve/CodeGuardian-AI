# CodeGuardian AI — System Design Specification

**Document:** System Design, Workflows & State Machines  
**Status:** Approved Architectural Baseline  
**Version:** 1.0.0 (Phase 0)  

---

## 1. System Services and Communication Interfaces

| Service Name | Primary Responsibility | Input Protocol | Output / Storage |
| :--- | :--- | :--- | :--- |
| **API Gateway** | Ingest webhooks, auth, manage CRUD for UI | HTTP REST / JSON | Redis, PostgreSQL |
| **Review Worker** | Dequeue jobs, run orchestrator | Redis Streams / List | PostgreSQL, ChromaDB |
| **Scanner Engine** | Run Semgrep, Bandit, Gitleaks, ESLint | Filepath + diff list | Pydantic `NormalizedScanResult` |
| **LangGraph Supervisor** | Multi-agent coordination and state reduction | `ReviewState` object | Agent task dispatches |
| **RAG Service** | Index policies, semantic vector retrieval | Query text + filters | Top-k `PolicyChunk` |
| **Remediation Engine** | Generate fixes, validate in sandbox | `Finding` + code context | Unified Diff, Fix PR |
| **Web Dashboard** | Developer UI, telemetry, review explorer | HTTP REST / TanStack Query | DOM / User Interface |

---

## 2. End-to-End Review Workflow

```mermaid
sequenceDiagram
    autonumber
    actor Dev as Developer
    participant GH as GitHub API / Webhook
    participant API as FastAPI Gateway
    participant Redis as Redis Queue
    participant Worker as Review Worker
    participant Scanners as Static Scanners
    participant Supervisor as LangGraph Supervisor
    participant Agents as Specialist Agents
    participant RAG as ChromaDB RAG
    participant Risk as Risk Engine
    participant DB as PostgreSQL
    participant UI as React Dashboard

    Dev->>GH: Open Pull Request
    GH->>API: POST /api/v1/github/webhook (HMAC signature)
    API->>API: Verify HMAC & Deduplicate Event
    API->>DB: Create ReviewJob (status: QUEUED)
    API->>Redis: Enqueue job: review.pull_request
    API-->>GH: 202 Accepted (job_id)

    Redis->>Worker: Dequeue review.pull_request
    Worker->>DB: Update ReviewJob (status: RUNNING)
    Worker->>Worker: Clone PR branch into isolated workspace
    
    Worker->>Scanners: Execute Semgrep, Bandit, Gitleaks, ESLint
    Scanners-->>Worker: Raw Tool Outputs
    Worker->>Worker: Normalize into NormalizedScanResult[]

    Worker->>Supervisor: Initialize ReviewState(diff, files, scan_results)
    Supervisor->>RAG: Query relevant policies (languages, categories)
    RAG-->>Supervisor: Retrieved PolicyChunks
    
    par Parallel Agent Execution
        Supervisor->>Agents: SecurityAgent.analyze(evidence, diff)
        Supervisor->>Agents: QualityAgent.analyze(evidence, diff, policies)
        Supervisor->>Agents: TestingAgent.analyze(diff, ast_map)
        Supervisor->>Agents: DocumentationAgent.analyze(diff, docstrings)
        Supervisor->>Agents: DependencyAgent.analyze(manifests)
    end
    Agents-->>Supervisor: Agent Findings & Telemetry

    Supervisor->>Supervisor: Aggregate & Deduplicate Findings
    Supervisor->>Risk: Compute Deterministic Risk Score
    Risk-->>Supervisor: Composite Risk Score (0-100) & Grade
    
    Supervisor->>DB: Persist ReviewRun, Findings, Evidence, AgentRuns
    Supervisor->>DB: Update ReviewJob (status: COMPLETED)

    Worker->>GH: Post Check Run & Concise Review Summary Comment
    Worker->>UI: Review Ready Notification
    Dev->>UI: Inspect Dashboard, Findings & Request Fix
```

---

## 3. State Machines

### 3.1. Review Job State Machine

```mermaid
stateDiagram-v2
    [*] --> QUEUED: Webhook Ingested
    QUEUED --> RUNNING: Worker Dequeued
    RUNNING --> SCANNING: Code Checked Out
    SCANNING --> AGENT_EXECUTION: Static Scans Done
    AGENT_EXECUTION --> AGGREGATING: Agent Inferences Done
    AGGREGATING --> REPORTING: Risk Scored
    REPORTING --> COMPLETED: DB & GitHub Updated
    
    RUNNING --> RETRYING: Recoverable Failure (e.g. rate limit)
    RETRYING --> QUEUED: Backoff Expired
    RETRYING --> FAILED: Max Retries Exceeded
    RUNNING --> FAILED: Unrecoverable Error
    FAILED --> [*]
    COMPLETED --> [*]
```

### 3.2. Remediation Attempt State Machine

```mermaid
stateDiagram-v2
    [*] --> REQUESTED: User Requests Fix
    REQUESTED --> GENERATING: LLM Creates Patch
    GENERATING --> VALIDATING_PATCH: Patch Syntax Valid
    GENERATING --> REJECTED: Malformed Diff Syntax
    
    VALIDATING_PATCH --> RUNNING_TESTS: Patch Applied Cleanly
    VALIDATING_PATCH --> REJECTED: Conflict / Application Failure
    
    RUNNING_TESTS --> RUNNING_SCANNERS: Pre-existing Tests Pass
    RUNNING_TESTS --> REJECTED: Tests Broken by Patch
    
    RUNNING_SCANNERS --> APPROVED: Target Issue Eliminated & No New Issues
    RUNNING_SCANNERS --> REJECTED: Vulnerability Still Present / New Violations
    
    APPROVED --> PR_CREATED: GitHub Fix PR Created
    REJECTED --> [*]
    PR_CREATED --> [*]
```

---

## 4. Failure Handling and Resilience Strategies

1. **Webhook Ingestion Idempotency:**
   - Every GitHub delivery has an `X-GitHub-Delivery` UUID.
   - Redis sets an idempotency key `idempotency:github:{delivery_id}` with a 24-hour TTL to prevent double-processing on network retries.

2. **Scanner Subprocess Timeouts:**
   - Each scanner process (Semgrep, Bandit, etc.) is bounded by an asynchronous timeout (default: 45 seconds).
   - If a scanner times out or crashes, an error evidence entry is recorded, and the review proceeds with remaining scanner results.

3. **Agent Resilience (Partial Review Degradation):**
   - In LangGraph, specialist agents are executed within `try/except` guardrails.
   - If an agent (e.g., Quality Agent) fails due to LLM provider timeout, the error is recorded in `AgentRun` with status `FAILED`, and the Supervisor aggregates findings from all healthy agents.

4. **Queue Poisoning & Dead-Letter Queue (DLQ):**
   - Jobs that exceed maximum retry attempts (default: 3) are automatically routed to `dlq:reviews` with full stack traces for engineer inspection.
