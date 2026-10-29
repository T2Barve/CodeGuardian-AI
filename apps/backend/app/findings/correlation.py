from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from app.findings.fingerprint import (
    generate_finding_fingerprint,
    get_canonical_issue_type,
    normalize_file_path,
)
from app.schemas.scanner import NormalizedScanResult, ScannerSeverity

# Numeric severity ranking for deterministic escalation
SEVERITY_ORDER = {
    "CRITICAL": 5,
    "HIGH": 4,
    "MEDIUM": 3,
    "LOW": 2,
    "INFO": 1,
}

# Remediation guides and impact statements by canonical issue type
ISSUE_TAXONOMY_DETAILS = {
    "cwe-89-sqli": {
        "title": "SQL Injection Vulnerability",
        "description": "Untrusted user or request input is directly formatted or concatenated into raw database SQL commands.",
        "impact": "Remote attackers could bypass authentication, read or modify sensitive tables, or execute administrative operations on the database.",
        "recommendation": "Use parameterized queries, prepared statements, or ORM object models (e.g. SQLAlchemy, Prisma) rather than dynamic string formatting.",
        "policy_reference": "SEC-POL-04: Secure Database Access Standards",
    },
    "cwe-78-cmdi": {
        "title": "Remote OS Command Injection",
        "description": "Operating system command is constructed dynamically using unsanitized string inputs or shell=True.",
        "impact": "Arbitrary command execution on the host server with the privileges of the running application process.",
        "recommendation": "Avoid invoking system shells. Use structured APIs with arguments passed as an explicit array of strings (e.g. subprocess.run(['cmd', arg], shell=False)).",
        "policy_reference": "SEC-POL-01: Principle of Least Privilege and Subprocess Sandboxing",
    },
    "cwe-798-hardcoded-secret": {
        "title": "Exposed Hardcoded Secret / Credential",
        "description": "Plaintext API token, private key, or password credential detected in source code.",
        "impact": "Credential compromise allowing unauthorized third-party access to external cloud providers, databases, or API resources.",
        "recommendation": "Immediately rotate the exposed secret and store credentials exclusively in environment variables or a secure secret manager (e.g. HashiCorp Vault, AWS Secrets Manager).",
        "policy_reference": "SEC-POL-02: Zero Plaintext Credentials Policy",
    },
    "cwe-79-xss": {
        "title": "Cross-Site Scripting (XSS)",
        "description": "Dynamic or unsanitized data is rendered directly into the DOM or client document.",
        "impact": "Attacker can execute malicious scripts in victim browsers, hijack user sessions, or exfiltrate sensitive tokens.",
        "recommendation": "Use textContent or framework-safe templating (e.g. React JSX) instead of innerHTML or document.write.",
        "policy_reference": "SEC-POL-05: Web Application Security Standards",
    },
    "cwe-95-eval": {
        "title": "Arbitrary Code Execution via eval() / Function()",
        "description": "Dynamic string compilation allows untrusted input to be evaluated as executable code.",
        "impact": "Complete client-side or server-side compromise through arbitrary execution of injected code.",
        "recommendation": "Replace eval() or Function() constructor with safe JSON parsing or explicit state machines.",
        "policy_reference": "SEC-POL-05: Web Application Security Standards",
    },
    "cwe-502-deserialization": {
        "title": "Insecure Deserialization of Untrusted Data",
        "description": "Deserialization of untrusted payloads using unsafe loaders (e.g. pickle, yaml.load without SafeLoader).",
        "impact": "Arbitrary remote code execution via object instantiation during payload unpacking.",
        "recommendation": "Use safe serializers like json.loads() or yaml.safe_load(Loader=yaml.SafeLoader). Never unpickle data from untrusted sources.",
        "policy_reference": "SEC-POL-03: Safe Serialization Baseline",
    },
    "cwe-942-cors": {
        "title": "Permissive Wildcard Cross-Origin Resource Sharing (CORS)",
        "description": "Access-Control-Allow-Origin header is configured with a wildcard '*', allowing any origin domain to interact with API endpoints.",
        "impact": "Exposes authenticated endpoints to cross-origin data theft and CSRF-like exploitation.",
        "recommendation": "Restrict allowed origins to trusted explicit domain names; avoid wildcard origin with credentials.",
        "policy_reference": "SEC-POL-06: API Security Guidelines",
    },
    "cwe-295-tls": {
        "title": "Disabled SSL/TLS Certificate Verification",
        "description": "Certificate verification disabled (verify=False), allowing network traffic interception.",
        "impact": "Vulnerable to Man-in-the-Middle (MitM) attacks where an attacker can eavesdrop or tamper with network payloads.",
        "recommendation": "Enable TLS verification (verify=True) and provide custom trusted CA certificates if internal PKI is used.",
        "policy_reference": "SEC-POL-07: Transport Layer Security Baseline",
    },
    "cwe-327-weak-hash": {
        "title": "Use of Broken Cryptographic Hash Algorithm",
        "description": "Obsolete cryptographic hash algorithm (e.g. MD5, SHA1) vulnerable to collision attacks.",
        "impact": "Collision vulnerabilities allowing forging of digital signatures, integrity checks, or password digests.",
        "recommendation": "Upgrade to cryptographically secure modern hash functions such as SHA-256, SHA-3, or Argon2/bcrypt for passwords.",
        "policy_reference": "SEC-POL-08: Cryptographic Standards",
    },
    "cwe-922-insecure-storage": {
        "title": "Insecure Storage of Sensitive Authentication Tokens",
        "description": "Sensitive credentials or tokens stored in client-accessible localStorage or sessionStorage.",
        "impact": "Vulnerable to token theft via any Cross-Site Scripting (XSS) vulnerability on the domain.",
        "recommendation": "Store session identifiers in HttpOnly, Secure, SameSite cookies rather than web storage.",
        "policy_reference": "SEC-POL-05: Web Application Security Standards",
    },
}


@dataclass
class FindingEvidenceItem:
    """Verbatim tool evidence substantiating a finding."""
    source: str
    tool: str
    rule_id: Optional[str]
    raw_message: str
    code_snippet: Optional[str]
    metadata_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CorrelatedFinding:
    """Synthesized, deduplicated finding correlating evidence across tools."""
    fingerprint: str
    category: str
    severity: str
    confidence: float
    file_path: str
    line_start: Optional[int]
    line_end: Optional[int]
    title: str
    description: str
    impact: Optional[str]
    recommendation: Optional[str]
    policy_reference: Optional[str]
    status: str = "OPEN"
    evidence_items: List[FindingEvidenceItem] = field(default_factory=list)
    tools_involved: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes CorrelatedFinding dataclass into a JSON-compatible dictionary."""
        from dataclasses import asdict
        return asdict(self)


def combine_confidence(confidences: List[float], distinct_tools_count: int) -> float:
    """
    Computes combined confidence score based on tool consensus.
    Boosts confidence by +0.05 for each additional distinct tool confirming the issue.
    """
    if not confidences:
        return 0.8
    base_conf = max(confidences)
    consensus_bonus = max(0, distinct_tools_count - 1) * 0.05
    return round(min(1.0, base_conf + consensus_bonus), 2)


def resolve_highest_severity(severities: List[str]) -> str:
    """Resolves highest severity among a collection of findings."""
    highest_rank = 0
    selected_severity = "MEDIUM"
    for sev in severities:
        sev_upper = sev.upper()
        rank = SEVERITY_ORDER.get(sev_upper, 1)
        if rank > highest_rank:
            highest_rank = rank
            selected_severity = sev_upper
    return selected_severity


def correlate_findings(
    raw_results: List[NormalizedScanResult],
    line_tolerance: int = 2,
) -> List[CorrelatedFinding]:
    """
    Groups raw scanner findings by (normalized_file, canonical_issue, line_proximity).
    Merges duplicate evidence, calculates consensus confidence, escalates severity,
    and produces deterministic SHA-256 fingerprints.
    """
    if not raw_results:
        return []

    # 1. Bucket by (normalized_file_path, canonical_issue_type)
    buckets: Dict[Tuple[str, str], List[NormalizedScanResult]] = {}
    for res in raw_results:
        norm_path = normalize_file_path(res.file_path)
        canonical_issue = get_canonical_issue_type(res.rule_id)
        bucket_key = (norm_path, canonical_issue)
        buckets.setdefault(bucket_key, []).append(res)

    correlated_list: List[CorrelatedFinding] = []

    # 2. Within each bucket, group by line proximity
    for (norm_path, canonical_issue), items in buckets.items():
        # Sort items by line_start
        sorted_items = sorted(items, key=lambda x: (x.line_start or 0))

        clusters: List[List[NormalizedScanResult]] = []
        for item in sorted_items:
            placed = False
            item_line = item.line_start or 0
            for cluster in clusters:
                cluster_lines = [c.line_start or 0 for c in cluster]
                avg_line = sum(cluster_lines) / len(cluster_lines)
                if abs(item_line - avg_line) <= line_tolerance:
                    cluster.append(item)
                    placed = True
                    break
            if not placed:
                clusters.append([item])

        # 3. For each cluster, synthesize a CorrelatedFinding
        for cluster in clusters:
            primary_item = cluster[0]
            cluster_severities = [c.severity.value if hasattr(c.severity, "value") else str(c.severity) for c in cluster]
            cluster_confidences = [c.confidence for c in cluster]
            tools = list({c.scanner for c in cluster})

            final_severity = resolve_highest_severity(cluster_severities)
            final_confidence = combine_confidence(cluster_confidences, len(tools))

            # Determine best line range
            all_starts = [c.line_start for c in cluster if c.line_start is not None]
            all_ends = [
                (c.line_end if c.line_end is not None else c.line_start)
                for c in cluster
                if (c.line_start is not None or c.line_end is not None)
            ]
            final_line_start = min(all_starts) if all_starts else None
            final_line_end = max(all_ends) if all_ends else final_line_start

            # Extract taxonomy guidelines if known
            taxonomy = ISSUE_TAXONOMY_DETAILS.get(canonical_issue, {})
            title = taxonomy.get("title") or primary_item.title
            description = taxonomy.get("description") or primary_item.message
            impact = taxonomy.get("impact") or "May compromise application integrity or security."
            recommendation = taxonomy.get("recommendation") or "Review and sanitize untrusted input."
            policy_ref = taxonomy.get("policy_reference")

            # Collect evidence items
            evidence_items: List[FindingEvidenceItem] = []
            for c in cluster:
                evidence_items.append(
                    FindingEvidenceItem(
                        source="SCANNER",
                        tool=c.scanner,
                        rule_id=c.rule_id,
                        raw_message=c.message,
                        code_snippet=c.code_snippet,
                        metadata_payload=c.metadata,
                    )
                )

            # Generate deterministic SHA-256 fingerprint
            category_val = (
                primary_item.category.value
                if hasattr(primary_item.category, "value")
                else str(primary_item.category)
            )
            fingerprint = generate_finding_fingerprint(
                file_path=norm_path,
                line_start=final_line_start,
                category=category_val,
                rule_id=primary_item.rule_id,
                canonical_class=canonical_issue,
            )

            correlated = CorrelatedFinding(
                fingerprint=fingerprint,
                category=category_val,
                severity=final_severity,
                confidence=final_confidence,
                file_path=norm_path,
                line_start=final_line_start,
                line_end=final_line_end,
                title=title,
                description=description,
                impact=impact,
                recommendation=recommendation,
                policy_reference=policy_ref,
                status="OPEN",
                evidence_items=evidence_items,
                tools_involved=tools,
            )
            correlated_list.append(correlated)

    # 4. Sort correlated findings deterministically: Critical first, then High, etc.
    correlated_list.sort(
        key=lambda x: (
            -SEVERITY_ORDER.get(x.severity, 1),
            -x.confidence,
            x.file_path,
            x.line_start or 0,
        )
    )

    return correlated_list
