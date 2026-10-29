from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.session import get_db
from app.models.finding import FindingEvidence
from app.scanners.runner import ScannerEngine

router = APIRouter(prefix="/scanners", tags=["Scanner Center"])


class ScannerToolInfo(BaseModel):
    name: str
    display_name: str
    category: str
    is_enabled: bool
    is_operational: bool
    description: str
    version_command: str
    supported_coverage: List[str]
    total_detections: int = 0
    last_status: str = "IDLE"


class ScannerCenterResponse(BaseModel):
    total_tools: int
    operational_tools: int
    tools: List[ScannerToolInfo]


@router.get(
    "",
    response_model=ScannerCenterResponse,
    summary="List static analysis scanners with verified operational status",
)
async def list_scanner_tools(
    db: AsyncSession = Depends(get_db),
) -> ScannerCenterResponse:
    engine = ScannerEngine()
    available = set(engine.get_available_scanners())

    # Check evidence counts in DB per tool
    evidence_stmt = select(FindingEvidence.tool, func.count(FindingEvidence.id)).group_by(FindingEvidence.tool)
    res = await db.execute(evidence_stmt)
    tool_counts = {row[0].lower(): row[1] for row in res.all()}

    tool_definitions = [
        {
            "name": "bandit",
            "display_name": "Bandit AST Security Scanner",
            "category": "Python SAST",
            "is_enabled": settings.ENABLE_BANDIT,
            "description": "Deterministic AST visitor analyzing Python code for SQL injection, command execution, hardcoded keys, and unsafe deserialization.",
            "version_command": "bandit --version",
            "supported_coverage": ["CWE-89 (SQLi)", "CWE-78 (OS Command)", "CWE-798 (Secrets)", "CWE-502 (Pickle)"],
        },
        {
            "name": "semgrep",
            "display_name": "Semgrep Multi-Language SAST",
            "category": "Polyglot SAST",
            "is_enabled": settings.ENABLE_SEMGREP,
            "description": "Fast, syntax-aware static analysis scanning Python, JavaScript, TypeScript, and Go for OWASP Top 10 vulnerabilities.",
            "version_command": "semgrep --version",
            "supported_coverage": ["OWASP A01 (Broken Access)", "OWASP A03 (Injection)", "Insecure CORS", "Insecure TLS"],
        },
        {
            "name": "gitleaks",
            "display_name": "Gitleaks Entropy & Secret Scanner",
            "category": "Secret Detection",
            "is_enabled": settings.ENABLE_GITLEAKS,
            "description": "High-speed git secret scanner utilizing regex rules and Shannon entropy calculations to identify credentials, AWS keys, and JWT tokens.",
            "version_command": "gitleaks version",
            "supported_coverage": ["AWS Access Keys", "GitHub PATs", "Stripe API Keys", "Database URIs", "High Entropy Strings"],
        },
        {
            "name": "eslint",
            "display_name": "ESLint Security & Code Quality",
            "category": "JS/TS SAST",
            "is_enabled": settings.ENABLE_ESLINT,
            "description": "JavaScript and TypeScript linter inspecting AST patterns for dangerous eval(), innerHTML/document.write, prototype pollution, and code smells.",
            "version_command": "npx eslint --version",
            "supported_coverage": ["CWE-95 (Eval Injection)", "CWE-79 (DOM XSS)", "Prototype Pollution", "LocalStorage Secrets"],
        },
    ]

    tools: List[ScannerToolInfo] = []
    operational_count = 0

    for td in tool_definitions:
        name = td["name"]
        is_operational = name in available and td["is_enabled"]
        if is_operational:
            operational_count += 1

        detections = tool_counts.get(name, 0)
        tools.append(
            ScannerToolInfo(
                name=name,
                display_name=td["display_name"],
                category=td["category"],
                is_enabled=td["is_enabled"],
                is_operational=is_operational,
                description=td["description"],
                version_command=td["version_command"],
                supported_coverage=td["supported_coverage"],
                total_detections=detections,
                last_status="ACTIVE" if is_operational else "UNAVAILABLE",
            )
        )

    return ScannerCenterResponse(
        total_tools=len(tools),
        operational_tools=operational_count,
        tools=tools,
    )
