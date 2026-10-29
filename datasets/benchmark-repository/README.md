# Synthetic Benchmark Repository

This directory contains intentionally flawed code used for controlled academic evaluation of CodeGuardian AI:

- Python vulnerabilities: SQL injection (CWE-89), command injection (CWE-78), hardcoded secrets (CWE-798), deprecated MD5 crypto (CWE-327).
- JavaScript/TypeScript vulnerabilities: XSS (CWE-79), unsafe eval (CWE-95).
- Quality flaws: High cyclomatic complexity (> 25), code duplication (> 40 lines), poor naming.
- Testing gaps: Critical business modules missing test coverage.
- Documentation gaps: Public endpoints missing parameter specifications.
