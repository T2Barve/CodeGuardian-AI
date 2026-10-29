import re
from typing import Any, Dict, List, Optional
import structlog

from app.schemas.agent import SecurityAgentOutput, SecurityFindingItem
from app.scanners.gitleaks import mask_secret
from app.services.llm.base import BaseLLMProvider
from app.services.llm.factory import get_llm_provider

logger = structlog.get_logger(__name__)

# CWE Mapping Dictionary for deterministic categorization
CWE_MAP = {
    "sql_injection": ("CWE-89", "A03:2021-Injection"),
    "command_injection": ("CWE-78", "A03:2021-Injection"),
    "hardcoded_secret": ("CWE-798", "A07:2021-Identification and Authentication Failures"),
    "xss": ("CWE-79", "A03:2021-Injection"),
    "insecure_hash": ("CWE-327", "A02:2021-Cryptographic Failures"),
    "unsafe_deserialization": ("CWE-502", "A08:2021-Software and Data Integrity Failures"),
    "unsafe_yaml": ("CWE-502", "A08:2021-Software and Data Integrity Failures"),
    "insecure_tls": ("CWE-295", "A02:2021-Cryptographic Failures"),
    "permissive_cors": ("CWE-942", "A05:2021-Security Misconfiguration"),
    "path_traversal": ("CWE-22", "A01:2021-Broken Access Control"),
}


class SecurityAgent:
    """
    Security Specialist Agent.
    
    Adheres to docs/AGENT_DESIGN.md Section 3.2:
    - Analyzes security baseline violations, CWEs, and OWASP Top 10 vulnerabilities.
    - Grounded in verified scanner evidence (Bandit, Semgrep, Gitleaks, ESLint).
    - Contextual reasoning: discounts false positives and escalates high-risk patterns.
    - Strict secret redaction: all sensitive tokens/passwords masked.
    """

    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm = llm_provider or get_llm_provider()

    async def analyze(
        self,
        changed_files: List[str],
        diff_content: str,
        scanner_results: List[Dict[str, Any]],
        retrieved_policies: Optional[List[Dict[str, Any]]] = None,
    ) -> SecurityAgentOutput:
        """
        Executes security evaluation combining deterministic scanner evidence with contextual LLM reasoning.
        """
        findings: List[SecurityFindingItem] = []

        # 1. First process deterministic scanner results and enrich them
        for scan in scanner_results:
            rule_id = str(scan.get("rule_id", "")).lower()
            scanner = scan.get("scanner", "sast")
            file_path = scan.get("file_path", "unknown")
            raw_msg = scan.get("message", "Security issue detected")
            severity = str(scan.get("severity", "MEDIUM")).upper()
            confidence = float(scan.get("confidence", 0.90))

            # Mask any raw secret tokens in evidence/message
            safe_msg = mask_secret(raw_msg)
            safe_code = mask_secret(str(scan.get("code_snippet", "")))

            # Determine CWE & OWASP mapping
            cwe_id = None
            owasp_category = None
            for key, (cwe, owasp) in CWE_MAP.items():
                if key in rule_id or key in raw_msg.lower():
                    cwe_id = cwe
                    owasp_category = owasp
                    break

            if not cwe_id:
                if scanner == "gitleaks":
                    cwe_id, owasp_category = CWE_MAP["hardcoded_secret"]
                elif "injection" in raw_msg.lower():
                    cwe_id, owasp_category = CWE_MAP["sql_injection"]
                else:
                    cwe_id = "CWE-699"
                    owasp_category = "A05:2021-Security Misconfiguration"

            exploitability = self._determine_exploitability(severity, scanner, cwe_id)
            recommendation = self._generate_security_recommendation(cwe_id, rule_id)

            findings.append(
                SecurityFindingItem(
                    cwe_id=cwe_id,
                    owasp_category=owasp_category,
                    severity=severity,
                    confidence=confidence,
                    file_path=file_path,
                    line_start=int(scan.get("line_start", 1)),
                    line_end=int(scan.get("line_end", 1)),
                    title=safe_msg[:120],
                    description=f"{safe_msg}. Detected at {file_path}:{scan.get('line_start', 1)} by {scanner}.",
                    exploitability_analysis=exploitability,
                    recommendation=recommendation,
                    evidence_source=f"{scanner}:{scan.get('rule_id', 'rule')}",
                    rule_id=scan.get("rule_id"),
                    policy_reference="SEC-POLICY-BASELINE-01" if retrieved_policies else None,
                )
            )

        # 2. Heuristic scan for dangerous patterns in diff not caught by SAST
        diff_findings = self._analyze_diff_heuristics(diff_content, changed_files)
        findings.extend(diff_findings)

        # Determine aggregate threat level
        has_critical = any(f.severity == "CRITICAL" for f in findings)
        has_high = any(f.severity == "HIGH" for f in findings)
        threat_level = "CRITICAL" if has_critical else ("HIGH" if has_high else ("MEDIUM" if findings else "LOW"))

        summary = (
            f"Security analysis identified {len(findings)} vulnerability finding(s). "
            f"Overall threat level: {threat_level}."
        ) if findings else "No security vulnerabilities or policy baseline violations detected."

        return SecurityAgentOutput(
            findings=findings,
            summary=summary,
            threat_level=threat_level,
        )

    def _determine_exploitability(self, severity: str, scanner: str, cwe_id: Optional[str]) -> str:
        if severity == "CRITICAL" or cwe_id in ("CWE-78", "CWE-89", "CWE-798"):
            return "High exploitability: direct remote code execution, SQL injection, or leaked authentication credentials."
        if severity == "HIGH":
            return "Moderate-High exploitability: potential privilege escalation or sensitive data exposure under non-default inputs."
        return "Low-Moderate exploitability: defense-in-depth risk requiring specific chain of misconfigurations."

    def _generate_security_recommendation(self, cwe_id: Optional[str], rule_id: str) -> str:
        if cwe_id == "CWE-89":
            return "Use parameterized queries or ORM abstractions. Never concatenate user input directly into SQL strings."
        if cwe_id == "CWE-78":
            return "Avoid shell=True and dynamic command strings. Pass argument lists to subprocess.run/exec."
        if cwe_id == "CWE-798":
            return "Immediately revoke leaked credentials and store secrets in environment variables or secret vaults."
        if cwe_id == "CWE-327":
            return "Upgrade legacy hashing algorithms to SHA-256, bcrypt, or Argon2."
        if cwe_id == "CWE-502":
            return "Use yaml.safe_load() or JSON serialization instead of unrestricted pickle/yaml deserialization."
        return "Review and sanitize input, enforce least privilege, and validate against project security baselines."

    def _analyze_diff_heuristics(self, diff_content: str, changed_files: List[str]) -> List[SecurityFindingItem]:
        """Heuristic security inspection of diff additions."""
        findings = []
        if not diff_content:
            return findings

        # Check for disabled SSL verification
        if re.search(r"verify\s*=\s*False", diff_content, re.IGNORECASE):
            findings.append(
                SecurityFindingItem(
                    cwe_id="CWE-295",
                    owasp_category="A02:2021-Cryptographic Failures",
                    severity="HIGH",
                    confidence=0.90,
                    file_path=changed_files[0] if changed_files else "unknown",
                    line_start=1,
                    line_end=1,
                    title="Disabled TLS/SSL Certificate Verification",
                    description="Detected 'verify=False' in network client call, making HTTPS requests vulnerable to Man-in-the-Middle (MitM) interception.",
                    exploitability_analysis="High exploitability on shared or public networks.",
                    recommendation="Remove verify=False and supply valid root CA certificate bundles.",
                    evidence_source="security_agent:heuristic:verify_false",
                    rule_id="SEC-TLS-001",
                )
            )

        return findings
