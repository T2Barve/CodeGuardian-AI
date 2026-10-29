# Corporate Engineering Standard: Unit & Integration Testing Coverage

**Policy ID:** TEST-001  
**Category:** TESTING  
**Version:** 1.0.0  
**Effective Date:** 2026-01-01  
**Target Languages:** All  

## 1. Test Coverage Requirements for Pull Requests
Every Pull Request introducing new business logic, domain models, or API endpoints must be accompanied by corresponding automated unit tests.
- Minimum statement test coverage for new code is 80%.
- Critical paths including security-sensitive routines, cryptographic operations, and payment workflows require 100% branch test coverage.

## 2. Test Determinism and Isolation
Tests must be fully isolated and deterministic.
- External network requests, databases, and third-party APIs must be mocked or run against local containerized test doubles.
- Tests must not depend on fixed execution order or persistent state across runs.
