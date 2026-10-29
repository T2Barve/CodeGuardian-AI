---
phase: 06-sandboxed-remediation-fix-prs
plan: 01
subsystem: remediation
tags: [remediation, sandbox, fix-pr, ast, human-in-the-loop]
requires:
  - phase: 05-risk-engine-reports
    provides: Persisted finding details and file evidence
provides:
  - 5-stage validation sandbox
  - Automated code patch generator
  - Isolated branch and draft PR engine
affects: [Phase 9]
tech-stack:
  added: [git, ast]
  patterns: [human-in-the-loop, multi-stage validation sandbox]
key-files:
  created:
    - apps/backend/app/remediation/sandbox.py
    - apps/backend/app/remediation/generator.py
    - apps/backend/app/remediation/fix_pr.py
  modified:
    - apps/backend/app/api/v1/endpoints/fix_prs.py
key-decisions:
  - "Zero direct commits to default branch: all fixes strictly open draft PRs"
  - "Patches failing AST syntax or unit tests are discarded immediately"
patterns-established:
  - "Branches strictly follow codeguardian/fix-{finding_id} pattern"
requirements-completed: [FIX-01, FIX-02, FIX-03]
duration: 25min
completed: 2026-10-24
---

# Phase 06: Sandboxed Remediation & Fix PRs Summary

**5-stage sandboxed remediation generator and human-in-the-loop draft PR engine verified across 16 unit tests.**

## Accomplishments
- Implemented 5-stage validation sandbox (AST syntax, re-scan, unit test, regression guard).
- Implemented isolated branch creation and draft PR opener.
- Verified in `apps/backend/tests/unit/test_remediation_engine.py` (9 tests) and `apps/backend/tests/unit/test_fix_pr.py` (7 tests).
