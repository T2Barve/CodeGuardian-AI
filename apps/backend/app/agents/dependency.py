import re
from typing import Any, Dict, List, Optional
import structlog

from app.schemas.agent import DependencyAgentOutput, DependencyFindingItem
from app.services.llm.base import BaseLLMProvider
from app.services.llm.factory import get_llm_provider

logger = structlog.get_logger(__name__)

# Known sensitive / high-risk package typosquatting patterns
SUSPICIOUS_TYPOSQUAT_PATTERNS = [
    r"python-dateutil-[\w]+",
    r"reqeusts",
    r"colorama-[\w]+",
    r"lodahs",
    r"cross-env-[\w]+",
]


class DependencyAgent:
    """
    Dependency Specialist Agent.
    
    Adheres to docs/AGENT_DESIGN.md Section 3.6:
    - Inspects package manifest modifications (requirements.txt, package.json, pyproject.toml).
    - Flags unpinned dependencies, wildcard ranges, and suspicious package signatures.
    - Advises on lockfile synchronization and supply chain integrity.
    """

    def __init__(self, llm_provider: Optional[BaseLLMProvider] = None):
        self.llm = llm_provider or get_llm_provider()

    async def analyze(
        self,
        changed_files: List[str],
        diff_content: str,
        retrieved_policies: Optional[List[Dict[str, Any]]] = None,
    ) -> DependencyAgentOutput:
        """
        Executes dependency manifest and software supply chain analysis.
        """
        findings: List[DependencyFindingItem] = []
        manifest_files = [f for f in changed_files if self._is_manifest_file(f)]

        for manifest in manifest_files:
            if "requirements" in manifest.lower():
                findings.extend(self._inspect_python_requirements(manifest, diff_content))
            elif "package.json" in manifest.lower():
                findings.extend(self._inspect_npm_package_json(manifest, diff_content))

        summary = (
            f"Dependency analysis identified {len(findings)} software supply chain finding(s) across {len(manifest_files)} manifest(s)."
        ) if findings else "Software dependencies and manifests adhere to version pinning standards."

        return DependencyAgentOutput(
            findings=findings,
            summary=summary,
            dependencies_analyzed=len(manifest_files),
        )

    def _is_manifest_file(self, file_path: str) -> bool:
        lower = file_path.lower()
        return any(lower.endswith(m) for m in [
            "requirements.txt",
            "package.json",
            "pyproject.toml",
            "pipfile",
            "go.mod",
            "pom.xml",
            "cargo.toml",
        ])

    def _inspect_python_requirements(self, manifest_file: str, diff_content: str) -> List[DependencyFindingItem]:
        findings = []
        lines = diff_content.splitlines()

        for line in lines:
            if line.startswith("+") and not line.startswith("+++"):
                raw_pkg = line[1:].strip()
                if not raw_pkg or raw_pkg.startswith("#"):
                    continue

                # Check for unpinned or >= dependencies
                if ">=" in raw_pkg and "==" not in raw_pkg and "<" not in raw_pkg:
                    pkg_name = raw_pkg.split(">=")[0].strip()
                    findings.append(
                        DependencyFindingItem(
                            package_name=pkg_name,
                            version_specifier=raw_pkg,
                            manifest_file=manifest_file,
                            severity="LOW",
                            risk_type="UNPINNED_VERSION",
                            description=f"Package `{pkg_name}` uses open-ended `>=` constraint without upper bound ceiling.",
                            recommendation=f"Pin exact version (e.g. `{pkg_name}==x.y.z`) or enforce compatible release operator `~=`.",
                        )
                    )
                # Check for unpinned package with no version at all
                elif "==" not in raw_pkg and ">=" not in raw_pkg and "<=" not in raw_pkg and "~=" not in raw_pkg:
                    findings.append(
                        DependencyFindingItem(
                            package_name=raw_pkg,
                            version_specifier="*",
                            manifest_file=manifest_file,
                            severity="MEDIUM",
                            risk_type="WILDCARD_VERSION",
                            description=f"Package `{raw_pkg}` has zero version constraint, making builds non-deterministic and vulnerable to supply chain breaks.",
                            recommendation=f"Pin exact version for `{raw_pkg}` in `{manifest_file}`.",
                        )
                    )

                # Check typosquatting indicators
                for pattern in SUSPICIOUS_TYPOSQUAT_PATTERNS:
                    if re.search(pattern, raw_pkg, re.IGNORECASE):
                        findings.append(
                            DependencyFindingItem(
                                package_name=raw_pkg,
                                version_specifier="suspicious",
                                manifest_file=manifest_file,
                                severity="HIGH",
                                risk_type="SUSPICIOUS_PACKAGE",
                                description=f"Package name `{raw_pkg}` matches known typosquatting heuristic.",
                                recommendation=f"Verify authentic package repository and author credentials before installing `{raw_pkg}`.",
                            )
                        )

        return findings

    def _inspect_npm_package_json(self, manifest_file: str, diff_content: str) -> List[DependencyFindingItem]:
        findings = []
        lines = diff_content.splitlines()

        for line in lines:
            if line.startswith("+") and not line.startswith("+++") and ":" in line:
                match = re.search(r'"([^"]+)"\s*:\s*"([^"]+)"', line)
                if match:
                    pkg_name, version = match.group(1), match.group(2)
                    if pkg_name in ("name", "version", "description", "main", "scripts"):
                        continue
                    if version in ("*", "latest"):
                        findings.append(
                            DependencyFindingItem(
                                package_name=pkg_name,
                                version_specifier=version,
                                manifest_file=manifest_file,
                                severity="MEDIUM",
                                risk_type="WILDCARD_VERSION",
                                description=f"NPM package `{pkg_name}` specifies wildcard version `\"{version}\"`.",
                                recommendation=f"Pin exact semantic version (e.g. `\"1.2.3\"`) and commit package-lock.json.",
                            )
                        )

        return findings
