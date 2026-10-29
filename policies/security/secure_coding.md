# Corporate Security Policy: Secure Coding Baseline

**Policy ID:** SEC-001  
**Category:** SECURITY  
**Version:** 1.0.0  
**Effective Date:** 2026-01-01  
**Target Languages:** Python, JavaScript, TypeScript, Go  

## 1. Input Validation and Sanitization
All untrusted user input originating from HTTP requests, headers, query parameters, webhooks, or file uploads must be strictly validated against an allowlist schema prior to execution.
Never pass unsanitized input directly into system shells or execution environments.

## 2. Command Injection and Subprocess Security
Dynamic execution of operating system commands using `shell=True`, `eval()`, `exec()`, or string concatenation is strictly prohibited across all services.
- Always use `subprocess.run` or `asyncio.create_subprocess_exec` with an explicit list of arguments.
- Execute all subprocesses under a dedicated non-root service account.
- Enforce strict execution timeouts on all background processes to prevent resource exhaustion.

## 3. Secret and Credential Management
Hardcoding secrets, API keys, private keys, authentication tokens, or database credentials directly in source code or version control is a Critical security violation.
- All secrets must be loaded dynamically from environment variables or external vault secret managers.
- Any logged message or error trace must sanitize and mask sensitive tokens before emission.
- Automated secret scanning (e.g. Gitleaks) must run on every commit.

## 4. Cryptographic Standards
Deprecated cryptographic algorithms such as MD5, SHA-1, DES, and RC4 must never be used for password hashing, digital signatures, or confidential data encryption.
- Use Argon2id or bcrypt with appropriate work factors for credential hashing.
- Use SHA-256 or SHA-512 for cryptographic integrity digests.
- Enforce TLS 1.3 for all in-transit communications with strict certificate verification (`verify=True`).
