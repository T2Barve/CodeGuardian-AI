import math
from typing import Any, Dict, Iterable, List, Optional, Union
from app.schemas.risk import (
    CategoryRiskBreakdown,
    FindingRiskInput,
    RepositoryRiskProfile,
    RepositoryTier,
    RiskActionRecommendation,
    RiskAssessment,
    RiskGrade,
    RiskLevel,
)

# Base Severity Weights
SEVERITY_WEIGHTS: Dict[str, float] = {
    "CRITICAL": 25.0,
    "HIGH": 15.0,
    "MEDIUM": 8.0,
    "LOW": 3.0,
    "INFO": 0.5,
}

# Category / Exploitability Factors
CATEGORY_FACTORS: Dict[str, float] = {
    "SECURITY": 1.2,
    "DEPENDENCY": 1.1,
    "TESTING": 1.0,
    "QUALITY": 0.9,
    "DOCUMENTATION": 0.5,
}


def _extract_finding_attributes(item: Any) -> Dict[str, Any]:
    """Uniformly extracts severity, category, confidence, and rule from diverse object types."""
    if isinstance(item, dict):
        severity = str(item.get("severity", "LOW")).upper()
        category = str(item.get("category", "SECURITY")).upper()
        confidence = float(item.get("confidence", 1.0))
        rule_id = item.get("rule_id") or item.get("title")
        file_path = item.get("file_path")
    else:
        # Pydantic model, SQLAlchemy Finding, or CorrelatedFinding
        severity = getattr(item, "severity", "LOW")
        if hasattr(severity, "value"):
            severity = severity.value
        severity = str(severity).upper()

        category = getattr(item, "category", "SECURITY")
        if hasattr(category, "value"):
            category = category.value
        category = str(category).upper()

        confidence = getattr(item, "confidence", 1.0)
        if confidence is None:
            confidence = 1.0
        confidence = float(confidence)

        rule_id = getattr(item, "rule_id", None) or getattr(item, "title", None)
        file_path = getattr(item, "file_path", None)

    # Sanitize confidence
    confidence = max(0.0, min(1.0, confidence))

    return {
        "severity": severity,
        "category": category,
        "confidence": confidence,
        "rule_id": rule_id,
        "file_path": file_path,
    }


class RiskEngine:
    """
    Deterministic Mathematical Risk Scoring Engine.
    
    Guarantees strict reproducibility:
    - Identical findings + identical profile -> identical score and grade.
    - Zero stochastic / LLM inputs to numerical scoring.
    - Transparent category breakdown, severity counts, and explainable driving factors.
    """

    @classmethod
    def calculate_risk(
        cls,
        findings: Iterable[Any],
        repo_profile: Optional[RepositoryRiskProfile] = None,
        lines_changed: Optional[int] = None,
        files_changed: Optional[int] = None,
    ) -> RiskAssessment:
        if repo_profile is None:
            repo_profile = RepositoryRiskProfile.from_tier(RepositoryTier.TIER_2)

        finding_list = list(findings)
        severity_counts = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0, "INFO": 0}
        category_counts = {
            "SECURITY": 0,
            "QUALITY": 0,
            "TESTING": 0,
            "DOCUMENTATION": 0,
            "DEPENDENCY": 0,
        }
        category_raw_impacts: Dict[str, float] = {
            "SECURITY": 0.0,
            "QUALITY": 0.0,
            "TESTING": 0.0,
            "DOCUMENTATION": 0.0,
            "DEPENDENCY": 0.0,
        }

        total_base_impact = 0.0
        factors: List[str] = []

        # Process each finding deterministically
        for item in finding_list:
            attrs = _extract_finding_attributes(item)
            sev = attrs["severity"]
            cat = attrs["category"]
            conf = attrs["confidence"]

            if sev not in severity_counts:
                sev = "LOW"
            if cat not in category_counts:
                cat = "SECURITY"

            severity_counts[sev] += 1
            category_counts[cat] += 1

            base_w = SEVERITY_WEIGHTS.get(sev, 3.0)
            cat_factor = CATEGORY_FACTORS.get(cat, 1.0)
            impact = base_w * conf * cat_factor

            total_base_impact += impact
            category_raw_impacts[cat] += impact

        # If zero findings, return perfect clean score
        if len(finding_list) == 0:
            return RiskAssessment(
                overall_score=0.0,
                grade=RiskGrade.A,
                level=RiskLevel.LOW,
                action=RiskActionRecommendation.APPROVE,
                is_mergeable=True,
                breakdown=CategoryRiskBreakdown(
                    security=0.0,
                    quality=0.0,
                    testing=0.0,
                    documentation=0.0,
                    dependency=0.0,
                ),
                findings_count_by_severity=severity_counts,
                findings_count_by_category=category_counts,
                factors=["Zero findings detected; pull request is clean and adheres to all security baselines."],
            )

        # 1. Apply Repository Criticality Multiplier
        multiplier = repo_profile.criticality_multiplier
        if not repo_profile.is_production:
            multiplier *= 0.9

        weighted_score = total_base_impact * multiplier

        if repo_profile.tier == RepositoryTier.TIER_1:
            factors.append("Repository is Tier 1 (Mission-Critical): risk score escalated by 1.25x.")
        elif repo_profile.tier == RepositoryTier.TIER_3:
            factors.append("Repository is Tier 3 (Internal/Prototype): risk score scaled by 0.8x.")

        # 2. PR Churn Penalty
        churn_penalty = 0.0
        if lines_changed is not None and lines_changed > 1000:
            churn_penalty += 5.0
            factors.append(f"High-churn PR ({lines_changed} lines changed) adds +5.0 risk penalty.")
        elif lines_changed is not None and lines_changed > 500:
            churn_penalty += 3.0
            factors.append(f"Moderate-churn PR ({lines_changed} lines changed) adds +3.0 risk penalty.")
        elif lines_changed is not None and lines_changed > 200:
            churn_penalty += 1.5

        if files_changed is not None and files_changed > 25:
            churn_penalty += 2.0
            factors.append(f"Broad PR footprint ({files_changed} files changed) adds +2.0 risk penalty.")

        weighted_score += churn_penalty

        # 3. Critical Severity Floor Overrides (Rule of Non-Negotiable Blockers)
        critical_count = severity_counts["CRITICAL"]
        high_count = severity_counts["HIGH"]

        if critical_count >= 2:
            weighted_score = max(86.0, weighted_score)
            factors.insert(0, f"Critical Blocker: {critical_count} CRITICAL findings detected (Grade F mandatory).")
        elif critical_count == 1:
            weighted_score = max(70.0, weighted_score)
            factors.insert(0, f"Severe Risk: 1 CRITICAL finding detected (Grade D minimum).")
        elif high_count >= 3:
            weighted_score = max(50.0, weighted_score)
            factors.insert(0, f"High Risk: {high_count} HIGH severity findings detected.")
        elif high_count > 0:
            factors.insert(0, f"Identified {high_count} HIGH severity finding(s).")

        # 4. Final Clamping & Rounding
        final_score = round(max(0.0, min(100.0, weighted_score)), 2)

        # 5. Category Breakdown Calculation
        category_breakdown = cls._calculate_category_breakdown(
            category_raw_impacts, severity_counts, category_counts, multiplier
        )

        # 6. Risk Grade & Governance Action Determination
        grade, level, action, is_mergeable = cls._determine_grade_and_action(final_score, critical_count)

        return RiskAssessment(
            overall_score=final_score,
            grade=grade,
            level=level,
            action=action,
            is_mergeable=is_mergeable,
            breakdown=category_breakdown,
            findings_count_by_severity=severity_counts,
            findings_count_by_category=category_counts,
            factors=factors,
        )

    @classmethod
    def _calculate_category_breakdown(
        cls,
        category_impacts: Dict[str, float],
        severity_counts: Dict[str, int],
        category_counts: Dict[str, int],
        multiplier: float,
    ) -> CategoryRiskBreakdown:
        breakdown_scores: Dict[str, float] = {}

        for cat, raw in category_impacts.items():
            if category_counts.get(cat, 0) == 0:
                breakdown_scores[cat.lower()] = 0.0
                continue

            scaled = raw * multiplier
            # Subscore asymptotic ceiling: asymptotic mapping so category score reflects standard 0-100 radar
            if cat == "SECURITY" and severity_counts["CRITICAL"] >= 2:
                subscore = max(86.0, min(100.0, scaled * 1.4))
            elif cat == "SECURITY" and severity_counts["CRITICAL"] == 1:
                subscore = max(70.0, min(100.0, scaled * 1.2))
            else:
                subscore = min(100.0, scaled)

            breakdown_scores[cat.lower()] = round(max(0.0, subscore), 2)

        return CategoryRiskBreakdown(
            security=breakdown_scores.get("security", 0.0),
            quality=breakdown_scores.get("quality", 0.0),
            testing=breakdown_scores.get("testing", 0.0),
            documentation=breakdown_scores.get("documentation", 0.0),
            dependency=breakdown_scores.get("dependency", 0.0),
        )

    @classmethod
    def _determine_grade_and_action(
        cls, score: float, critical_count: int
    ) -> tuple[RiskGrade, RiskLevel, RiskActionRecommendation, bool]:
        """
        Determines the grade, human level, PR governance action, and mergeability.
        """
        if score > 85.0 or critical_count >= 2:
            return (
                RiskGrade.F,
                RiskLevel.CRITICAL,
                RiskActionRecommendation.BLOCK,
                False,
            )
        elif score > 65.0:
            return (
                RiskGrade.D,
                RiskLevel.SEVERE,
                RiskActionRecommendation.REQUEST_CHANGES,
                False,
            )
        elif score > 35.0:
            return (
                RiskGrade.C,
                RiskLevel.HIGH,
                RiskActionRecommendation.REQUEST_CHANGES,
                False,
            )
        elif score > 15.0:
            return (
                RiskGrade.B,
                RiskLevel.MODERATE,
                RiskActionRecommendation.APPROVE_WITH_SUGGESTIONS,
                True,
            )
        else:
            return (
                RiskGrade.A,
                RiskLevel.LOW,
                RiskActionRecommendation.APPROVE,
                True,
            )
