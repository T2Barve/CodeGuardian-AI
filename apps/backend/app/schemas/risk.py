from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RiskGrade(str, Enum):
    A = "A"  # 0.00 - 15.00: Clean / Low Risk (Auto-merge candidate)
    B = "B"  # 15.01 - 35.00: Moderate Risk (Minor issues / suggestions)
    C = "C"  # 35.01 - 65.00: High Risk (Significant issues / manual review required)
    D = "D"  # 65.01 - 85.00: Severe Risk (Severe vulnerabilities / quality regressions)
    F = "F"  # 85.01 - 100.00: Critical Blocker (Block merge immediately)


class RiskLevel(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    SEVERE = "SEVERE"
    CRITICAL = "CRITICAL"


class RiskActionRecommendation(str, Enum):
    APPROVE = "APPROVE"
    APPROVE_WITH_SUGGESTIONS = "APPROVE_WITH_SUGGESTIONS"
    REQUEST_CHANGES = "REQUEST_CHANGES"
    BLOCK = "BLOCK"


class RepositoryTier(str, Enum):
    TIER_1 = "TIER_1"  # Mission-critical / Payment / Auth / Core Infrastructure
    TIER_2 = "TIER_2"  # Standard Production Services & APIs
    TIER_3 = "TIER_3"  # Internal Tools / Prototypes / Documentation


class CategoryRiskBreakdown(BaseModel):
    security: float = Field(0.0, ge=0.0, le=100.0, description="Security sub-score (0-100)")
    quality: float = Field(0.0, ge=0.0, le=100.0, description="Code quality & maintainability sub-score (0-100)")
    testing: float = Field(0.0, ge=0.0, le=100.0, description="Test gap & coverage sub-score (0-100)")
    documentation: float = Field(0.0, ge=0.0, le=100.0, description="Documentation sub-score (0-100)")
    dependency: float = Field(0.0, ge=0.0, le=100.0, description="Dependency & CVE sub-score (0-100)")


class RepositoryRiskProfile(BaseModel):
    tier: RepositoryTier = Field(RepositoryTier.TIER_2, description="Criticality tier")
    criticality_multiplier: float = Field(1.0, ge=0.5, le=2.0, description="Risk multiplier based on tier")
    is_production: bool = Field(True, description="Whether target branch is production-facing")
    custom_weights: Dict[str, float] = Field(default_factory=dict, description="Optional custom category weights")

    @classmethod
    def from_tier(cls, tier: RepositoryTier | str, is_production: bool = True) -> "RepositoryRiskProfile":
        tier_enum = RepositoryTier(tier) if isinstance(tier, str) else tier
        multipliers = {
            RepositoryTier.TIER_1: 1.25,
            RepositoryTier.TIER_2: 1.0,
            RepositoryTier.TIER_3: 0.8,
        }
        return cls(
            tier=tier_enum,
            criticality_multiplier=multipliers[tier_enum],
            is_production=is_production,
        )


class RiskAssessment(BaseModel):
    overall_score: float = Field(..., ge=0.0, le=100.0, description="Deterministic risk score (0-100)")
    grade: RiskGrade = Field(..., description="Overall risk letter grade (A-F)")
    level: RiskLevel = Field(..., description="Human-readable risk classification")
    action: RiskActionRecommendation = Field(..., description="Automated PR governance recommendation")
    is_mergeable: bool = Field(..., description="True if risk is within allowable merge thresholds")
    breakdown: CategoryRiskBreakdown = Field(..., description="Multi-dimensional category scores")
    findings_count_by_severity: Dict[str, int] = Field(default_factory=dict)
    findings_count_by_category: Dict[str, int] = Field(default_factory=dict)
    factors: List[str] = Field(default_factory=list, description="Key driving factors behind the assessment")
    assessed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FindingRiskInput(BaseModel):
    severity: str = Field(..., description="CRITICAL, HIGH, MEDIUM, LOW, INFO")
    category: str = Field("SECURITY", description="SECURITY, QUALITY, TESTING, DOCUMENTATION, DEPENDENCY")
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    rule_id: Optional[str] = None
    file_path: Optional[str] = None


class RiskCalculationRequest(BaseModel):
    findings: List[FindingRiskInput] = Field(default_factory=list)
    repo_tier: Optional[RepositoryTier] = Field(RepositoryTier.TIER_2)
    lines_changed: Optional[int] = Field(None, ge=0)
    files_changed: Optional[int] = Field(None, ge=0)
