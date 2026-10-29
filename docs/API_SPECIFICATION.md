# CodeGuardian AI — API Specification

**Base URL:** `/api/v1`  
**Protocol:** HTTPS  
**Format:** JSON (`application/json`)  
**Version:** 1.0.0 (Phase 0)  

---

## 1. Authentication & Security Headers

All protected endpoints require a Bearer token in the `Authorization` header:
```http
Authorization: Bearer <jwt_token>
```
Webhook endpoints do not use JWT; instead, they require the GitHub HMAC signature header:
```http
X-Hub-Signature-256: sha256=<hmac_hex_digest>
X-GitHub-Event: pull_request
X-GitHub-Delivery: <uuid>
```

---

## 2. Standard Error Response Schema

All errors follow RFC 7807 problem details format:
```json
{
  "type": "https://errors.codeguardian.ai/v1/resource-not-found",
  "title": "Resource Not Found",
  "status": 404,
  "detail": "Review with ID '9a4f2162-...' does not exist.",
  "instance": "/api/v1/reviews/9a4f2162-...",
  "timestamp": "2026-09-30T17:24:00Z"
}
```

---

## 3. Endpoints by Group

### 3.1. Health & Observability (`/health`, `/ready`)

#### `GET /api/v1/health`
- **Description:** Liveness probe verifying the API gateway process is responding.
- **Auth:** None
- **Response 200:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2026-09-30T17:24:00Z"
}
```

#### `GET /api/v1/ready`
- **Description:** Readiness probe validating connectivity to PostgreSQL and Redis.
- **Auth:** None
- **Response 200:**
```json
{
  "status": "ready",
  "database": "connected",
  "redis": "connected",
  "active_workers": 2
}
```

---

### 3.2. GitHub Integration (`/github`)

#### `POST /api/v1/github/webhook`
- **Description:** Ingests GitHub Webhook events (e.g. `pull_request`). Validates HMAC SHA-256 and enqueues review job.
- **Auth:** HMAC `X-Hub-Signature-256`
- **Headers Required:**
  - `X-GitHub-Event: pull_request`
  - `X-GitHub-Delivery: <uuid>`
  - `X-Hub-Signature-256: sha256=...`
- **Response 202 Accepted:**
```json
{
  "status": "enqueued",
  "job_id": "b1b51e04-d50c-4e89-9a2c-f604b90e6ea1",
  "delivery_id": "7f8c0542-...",
  "event": "pull_request",
  "action": "opened"
}
```
- **Errors:** 400 Bad Request (Invalid event), 401 Unauthorized (Invalid HMAC signature), 409 Conflict (Duplicate delivery ID).

---

### 3.3. Repositories (`/repositories`)

#### `GET /api/v1/repositories`
- **Description:** List registered repositories with pagination and health status.
- **Auth:** Bearer Token
- **Query Params:** `page` (default: 1), `limit` (default: 20), `search` (string)
- **Response 200:**
```json
{
  "items": [
    {
      "id": "c5304b2b-...",
      "github_repo_id": 98765432,
      "name": "ecommerce-backend",
      "owner": "acme-corp",
      "url": "https://github.com/acme-corp/ecommerce-backend",
      "default_branch": "main",
      "language": "python",
      "is_active": true,
      "total_reviews": 42,
      "last_risk_score": 14.5
    }
  ],
  "total": 1,
  "page": 1,
  "pages": 1
}
```

---

### 3.4. Pull Requests (`/pull-requests`)

#### `GET /api/v1/repositories/{repo_id}/pull-requests`
- **Description:** List pull requests for a given repository.
- **Auth:** Bearer Token
- **Response 200:**
```json
{
  "items": [
    {
      "id": "e6741b80-...",
      "number": 142,
      "title": "feat: add user authentication endpoint",
      "author": "dev-alice",
      "source_branch": "feat/auth",
      "target_branch": "main",
      "commit_sha": "a1b2c3d4e5f6...",
      "status": "OPEN",
      "latest_review_status": "COMPLETED",
      "latest_risk_score": 78.50,
      "latest_risk_grade": "D"
    }
  ]
}
```

---

### 3.5. Reviews & Findings (`/reviews`, `/findings`)

#### `GET /api/v1/reviews/{review_id}`
- **Description:** Retrieve comprehensive review run details, risk score, and summary.
- **Auth:** Bearer Token
- **Response 200:**
```json
{
  "id": "9a4f2162-...",
  "review_job_id": "b1b51e04-...",
  "status": "SUCCESS",
  "risk_score": 68.20,
  "risk_grade": "C",
  "duration_ms": 14250,
  "summary": "Identified 1 CRITICAL SQL injection vulnerability and 2 high-complexity functions without unit tests.",
  "findings_summary": {
    "CRITICAL": 1,
    "HIGH": 2,
    "MEDIUM": 4,
    "LOW": 1,
    "INFO": 0
  },
  "created_at": "2026-09-30T17:25:00Z"
}
```

#### `GET /api/v1/reviews/{review_id}/findings`
- **Description:** Retrieve normalized, deduplicated findings for a specific review run.
- **Auth:** Bearer Token
- **Query Params:** `category`, `severity`, `status`
- **Response 200:**
```json
{
  "items": [
    {
      "id": "713f0ac2-...",
      "fingerprint": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
      "category": "SECURITY",
      "severity": "CRITICAL",
      "confidence": 0.98,
      "status": "OPEN",
      "file_path": "services/auth/views.py",
      "line_start": 42,
      "line_end": 45,
      "title": "Raw SQL Query Concatenation (SQLi)",
      "description": "Untrusted input directly formatted into raw database query.",
      "impact": "Remote attacker could bypass authentication or dump database.",
      "recommendation": "Use parameterized queries via SQLAlchemy text(:param).",
      "evidence_count": 2,
      "policy_reference": "SEC-POL-04: Secure Database Access Standards"
    }
  ]
}
```

#### `GET /api/v1/findings/{finding_id}`
- **Description:** Detailed finding view including full evidence chain from scanners & agents.
- **Auth:** Bearer Token
- **Response 200:**
```json
{
  "id": "713f0ac2-...",
  "title": "Raw SQL Query Concatenation (SQLi)",
  "evidence": [
    {
      "source": "SCANNER",
      "tool": "bandit",
      "rule_id": "B608",
      "raw_message": "Possible SQL injection vector through string-based query construction.",
      "code_snippet": "query = f\"SELECT * FROM users WHERE username = '{username}'\""
    },
    {
      "source": "AGENT",
      "tool": "security_agent",
      "rule_id": "CWE-89",
      "raw_message": "Exploitable SQL injection verified in login route without ORM sanitization.",
      "metadata": { "exploitability": "HIGH", "cvss_v3_score": 9.8 }
    }
  ]
}
```

---

### 3.6. Agent Telemetry (`/agents`)

#### `GET /api/v1/reviews/{review_id}/agents`
- **Description:** Inspect LangGraph agent execution status, duration, and token usage.
- **Auth:** Bearer Token
- **Response 200:**
```json
{
  "items": [
    {
      "agent_name": "supervisor",
      "status": "COMPLETED",
      "duration_ms": 1200,
      "total_tokens": 1450,
      "estimated_cost": 0.0029
    },
    {
      "agent_name": "security",
      "status": "COMPLETED",
      "duration_ms": 3400,
      "total_tokens": 2890,
      "estimated_cost": 0.0058
    }
  ]
}
```

---

### 3.7. Remediation Engine (`/remediation`)

#### `POST /api/v1/findings/{finding_id}/remediate`
- **Description:** Trigger sandboxed patch generation for a specific finding.
- **Auth:** Bearer Token
- **Response 202 Accepted:**
```json
{
  "remediation_id": "893d5bf1-...",
  "status": "VALIDATING",
  "message": "Fix candidate generated. Running sandboxed validation pipeline..."
}
```

#### `GET /api/v1/remediation/{remediation_id}`
- **Description:** Retrieve patch content, validation results, and Fix PR status.
- **Auth:** Bearer Token
- **Response 200:**
```json
{
  "id": "893d5bf1-...",
  "finding_id": "713f0ac2-...",
  "status": "VALIDATED",
  "patch": "--- a/services/auth/views.py\n+++ b/services/auth/views.py\n@@ -42,3 +42,3 @@\n-query = f\"SELECT * FROM users WHERE username = '{username}'\"\n+query = select(User).where(User.username == username)",
  "validation_result": {
    "syntax_check": "PASSED",
    "unit_tests": "PASSED (14/14 passed)",
    "scanner_check": "PASSED (B608 eliminated, 0 new findings)",
    "regression_tests": "PASSED"
  },
  "can_create_pr": true
}
```

#### `POST /api/v1/remediation/{remediation_id}/create-pr`
- **Description:** Create an official GitHub Fix Pull Request following human confirmation.
- **Auth:** Bearer Token
- **Response 201 Created:**
```json
{
  "fix_pr_id": "12903ea2-...",
  "github_pr_url": "https://github.com/acme-corp/ecommerce-backend/pull/143",
  "status": "OPEN"
}
```

---

### 3.8. Policies & RAG (`/policies`, `/rag`)

#### `POST /api/v1/policies`
- **Description:** Ingest an engineering standard or security policy file (MD, PDF, TXT).
- **Auth:** Bearer Token (ADMIN or REVIEWER)
- **Form Data:** `file` (Multipart file), `name` (string), `category` (string)
- **Response 201 Created:**
```json
{
  "id": "31f49a0e-...",
  "name": "SQL Injection & Database Standards",
  "category": "SECURITY_BASELINE",
  "chunks_created": 6,
  "status": "INDEXED"
}
```

#### `POST /api/v1/rag/search`
- **Description:** Query policy chunks via semantic vector similarity.
- **Auth:** Bearer Token
- **Body:**
```json
{
  "query": "parameterized queries sql injection",
  "category": "SECURITY_BASELINE",
  "top_k": 3
}
```
- **Response 200:**
```json
{
  "results": [
    {
      "chunk_id": "chunk_sec_01",
      "policy_name": "SQL Injection & Database Standards",
      "content": "All queries touching relational stores must use ORM binding or text(:param) syntax...",
      "score": 0.89
    }
  ]
}
```

---

### 3.9. Dashboard Analytics (`/dashboard`)

#### `GET /api/v1/dashboard/summary`
- **Description:** Aggregated operational metrics for developer dashboard overview.
- **Auth:** Bearer Token
- **Response 200:**
```json
{
  "total_repositories": 12,
  "total_reviews": 154,
  "active_jobs": 2,
  "findings_by_severity": {
    "CRITICAL": 3,
    "HIGH": 14,
    "MEDIUM": 38,
    "LOW": 62
  },
  "average_review_duration_ms": 16400,
  "risk_distribution": {
    "A": 45,
    "B": 60,
    "C": 32,
    "D": 12,
    "F": 5
  }
}
```
