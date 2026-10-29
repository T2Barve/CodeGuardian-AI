---
phase: 03-deterministic-static-scanners
plan: 01
subsystem: scanners
tags: [bandit, semgrep, gitleaks, eslint, static-analysis]
requires:
  - phase: 02-webhook-ingress-queue
    provides: Review job queue and worker execution context
provides:
  - Sandboxed static scanner adapters
  - Normalized finding schemas
  - Deterministic vulnerability evidence
affects: [Phase 4, Phase 5]
tech-stack:
  added: [bandit, semgrep, gitleaks, eslint]
  patterns: [subprocess isolation, schema normalization, honest error reporting]
key-files:
  created:
    - apps/backend/app/scanners/bandit.py
    - apps/backend/app/scanners/semgrep.py
    - apps/backend/app/scanners/gitleaks.py
    - apps/backend/app/scanners/eslint.py
    - apps/backend/app/scanners/normalizer.py
  modified:
    - apps/backend/app/api/v1/endpoints/scanners.py
key-decisions:
  - "Subprocesses strictly use shell=False to prevent command injection"
  - "Failing scanners return ERROR status instead of deceptive clean results"
patterns-established:
  - "All findings must have extracted source lines and verifiable evidence"
requirements-completed: [SCAN-01, SCAN-02, SCAN-03, SCAN-04, SCAN-05]
duration: 25min
completed: 2026-10-24
---

# Phase 03: Deterministic Static Scanners Summary

**Deterministic static analysis suite (Bandit, Semgrep, Gitleaks, ESLint) verified with 19 unit tests passing.**

## Accomplishments
- Implemented isolated runners for Bandit, Semgrep, Gitleaks, and ESLint.
- Standardized finding fingerprints and severity mappings.
- Verified in `apps/backend/tests/unit/test_scanners.py` (19 tests).
