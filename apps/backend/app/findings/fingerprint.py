import hashlib
import os
from typing import Optional


# Canonical security and quality issue mappings across tools
RULE_CANONICAL_MAP = {
    # SQL Injection (CWE-89)
    "b608": "cwe-89-sqli",
    "semgrep.python.sqli.format": "cwe-89-sqli",
    # Command Injection (CWE-78)
    "b602": "cwe-78-cmdi",
    "b603": "cwe-78-cmdi",
    "semgrep.python.command-injection": "cwe-78-cmdi",
    # Insecure Deserialization / YAML (CWE-502)
    "b301": "cwe-502-deserialization",
    "b506": "cwe-502-deserialization",
    "semgrep.python.unsafe-yaml-load": "cwe-502-deserialization",
    # Cross-Site Scripting (CWE-79)
    "security/detect-document-write": "cwe-79-xss",
    "security/detect-innerhtml-assignment": "cwe-79-xss",
    "semgrep.js.dom-xss.innerhtml": "cwe-79-xss",
    # Dynamic Code Execution (CWE-95)
    "security/detect-eval-with-expression": "cwe-95-eval",
    "security/detect-function-constructor": "cwe-95-eval",
    # Hardcoded Secrets & Credentials (CWE-798)
    "b105": "cwe-798-hardcoded-secret",
    "aws-access-token": "cwe-798-hardcoded-secret",
    "github-pat": "cwe-798-hardcoded-secret",
    "private-key": "cwe-798-hardcoded-secret",
    "slack-token": "cwe-798-hardcoded-secret",
    "jwt-token": "cwe-798-hardcoded-secret",
    "generic-api-key": "cwe-798-hardcoded-secret",
    "db-connection-secret": "cwe-798-hardcoded-secret",
    # Insecure Storage (CWE-922)
    "security/detect-insecure-storage": "cwe-922-insecure-storage",
    # Permissive CORS (CWE-942)
    "semgrep.generic.cors.wildcard": "cwe-942-cors",
    # Insecure TLS/SSL (CWE-295)
    "semgrep.python.tls.disabled-verification": "cwe-295-tls",
    # Weak Cryptographic Hash (CWE-327)
    "b303": "cwe-327-weak-hash",
    # Quality / Logging
    "quality/no-console-log": "quality-console-log",
    "b101": "quality-assert-used",
}


def normalize_file_path(file_path: str) -> str:
    """Canonicalizes file path by lowercasing, converting backslashes, and trimming prefixes."""
    clean = os.path.normpath(file_path).replace("\\", "/").strip().lower()
    if clean.startswith("./"):
        clean = clean[2:]
    return clean.lstrip("/")


def get_canonical_issue_type(rule_id: str, default: Optional[str] = None) -> str:
    """Resolves a tool-specific rule ID to its canonical vulnerability or flaw classification."""
    rule_key = rule_id.lower().strip()
    return RULE_CANONICAL_MAP.get(rule_key, default or rule_key.replace(".", "-").replace("_", "-"))


def generate_finding_fingerprint(
    file_path: str,
    line_start: Optional[int],
    category: str,
    rule_id: str,
    canonical_class: Optional[str] = None,
) -> str:
    """
    Computes a deterministic, collision-resistant SHA-256 fingerprint for a finding.
    
    Formula:
        SHA-256(canonical_path + ":" + line_bucket + ":" + category + ":" + issue_class)
        
    Guarantees:
      - Two distinct tools detecting the same vulnerability on the same line produce the exact same fingerprint.
      - Repeated reviews of the same unchanged flaw preserve identical fingerprints.
    """
    norm_path = normalize_file_path(file_path)
    norm_line = str(line_start if line_start is not None and line_start > 0 else 0)
    norm_cat = category.strip().upper()
    norm_issue = canonical_class or get_canonical_issue_type(rule_id)

    raw_key = f"{norm_path}:{norm_line}:{norm_cat}:{norm_issue}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
