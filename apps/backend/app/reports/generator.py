from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from app.schemas.report import (
    ReportAgentSummary,
    ReportFindingItem,
    ReviewReport,
    ReviewReportSummary,
)
from app.schemas.risk import CategoryRiskBreakdown, RiskGrade, RiskLevel


class ReportGenerator:
    """
    Synthesizes and renders developer-friendly, auditable, and executive-ready
    Pull Request review reports in GitHub Markdown and JSON schemas.
    """

    @classmethod
    def assemble_report(
        cls,
        summary: ReviewReportSummary,
        category_breakdown: CategoryRiskBreakdown,
        risk_driving_factors: List[str],
        findings: List[ReportFindingItem],
        agent_summaries: Optional[List[ReportAgentSummary]] = None,
    ) -> ReviewReport:
        report = ReviewReport(
            summary=summary,
            category_breakdown=category_breakdown,
            risk_driving_factors=risk_driving_factors,
            findings=findings,
            agent_summaries=agent_summaries or [],
            generated_at=datetime.now(timezone.utc),
        )
        report.markdown_content = cls.render_markdown(report)
        return report

    @classmethod
    def render_markdown(cls, report: ReviewReport) -> str:
        s = report.summary
        cb = report.category_breakdown

        # Severity badges mapping
        grade_badges = {
            RiskGrade.A: "🟢 **GRADE A** (Minimal Risk — Approved)",
            RiskGrade.B: "🔵 **GRADE B** (Low Risk — Minor Findings)",
            RiskGrade.C: "🟡 **GRADE C** (Moderate Risk — Attention Recommended)",
            RiskGrade.D: "🟠 **GRADE D** (Elevated Risk — Action Required)",
            RiskGrade.F: "🔴 **GRADE F** (Critical Risk — Merge BLOCKED)",
        }

        grade_text = grade_badges.get(s.risk_grade, f"**GRADE {s.risk_grade.value}**")
        merge_status_badge = "✅ **MERGEABLE**" if s.is_mergeable else "🚫 **BLOCKED (Requires Remediation)**"

        lines: List[str] = [
            f"# 🛡️ CodeGuardian AI — Pull Request Review Report",
            f"",
            f"**Repository:** `{s.repo_name}` | **PR:** `#{s.pr_number}` — *{s.pr_title}*",
            f"**Author:** @{s.author} | **Commit:** `{s.commit_sha[:8]}` | **Duration:** `{s.duration_ms}ms`",
            f"",
            f"---",
            f"",
            f"## 📊 Executive Summary",
            f"",
            f"| Overall Risk Score | Risk Grade | Gate Status | Recommended Action |",
            f"| :---: | :---: | :---: | :---: |",
            f"| **`{s.risk_score:.1f} / 100`** | {grade_text} | {merge_status_badge} | **`{s.recommended_action}`** |",
            f"",
            f"### 🔍 Findings Distribution",
            f"| Total | 🔴 Critical | 🟠 High | 🟡 Medium | 🔵 Low | ⚪ Info |",
            f"| :---: | :---: | :---: | :---: | :---: | :---: |",
            f"| **{s.total_findings}** | **{s.critical_count}** | **{s.high_count}** | **{s.medium_count}** | **{s.low_count}** | **{s.info_count}** |",
            f"",
            f"---",
            f"",
            f"## 🎯 Category Risk Radar",
            f"",
            f"| Category | Dimension Risk Score (0-100) | Findings Count |",
            f"| :--- | :---: | :---: |",
            f"| 🛡️ **Security** | `{cb.security:.1f}` | {sum(1 for f in report.findings if f.category == 'SECURITY')} |",
            f"| 💎 **Code Quality** | `{cb.quality:.1f}` | {sum(1 for f in report.findings if f.category == 'QUALITY')} |",
            f"| 🧪 **Test Coverage** | `{cb.testing:.1f}` | {sum(1 for f in report.findings if f.category == 'TESTING')} |",
            f"| 📚 **Documentation** | `{cb.documentation:.1f}` | {sum(1 for f in report.findings if f.category == 'DOCUMENTATION')} |",
            f"| 📦 **Dependencies** | `{cb.dependency:.1f}` | {sum(1 for f in report.findings if f.category == 'DEPENDENCY')} |",
            f"",
        ]

        if report.risk_driving_factors:
            lines.append("### ⚠️ Key Risk Driving Factors")
            for factor in report.risk_driving_factors:
                lines.append(f"- {factor}")
            lines.append("")

        lines.extend([
            f"---",
            f"",
            f"## 🛠️ Correlated Findings & Policy Citations ({len(report.findings)})",
            f"",
        ])

        if not report.findings:
            lines.append("🎉 **No security vulnerabilities, quality defects, or policy violations detected in this Pull Request.**")
            lines.append("")
        else:
            # Sort findings by severity order
            severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}
            sorted_findings = sorted(
                report.findings,
                key=lambda f: severity_order.get(f.severity.upper(), 5),
            )

            for idx, finding in enumerate(sorted_findings, 1):
                sev = finding.severity.upper()
                sev_icon = "🔴" if sev == "CRITICAL" else "🟠" if sev == "HIGH" else "🟡" if sev == "MEDIUM" else "🔵"

                tools_str = ", ".join(finding.tools_involved) if finding.tools_involved else "Multi-Agent"

                lines.extend([
                    f"### {sev_icon} [{sev}] {finding.title}",
                    f"**Location:** `{finding.file_path}:{finding.line_start}-{finding.line_end}` | **Category:** `{finding.category}` | **Confidence:** `{finding.confidence * 100:.0f}%` | **Tools:** `{tools_str}`",
                    f"",
                    f"**Description:** {finding.description}",
                    f"",
                ])

                if finding.impact:
                    lines.append(f"**Impact:** {finding.impact}")
                    lines.append("")

                if finding.code_snippet:
                    lines.extend([
                        f"<details><summary><b>View Affected Code Snippet</b></summary>",
                        f"",
                        f"```",
                        f"{finding.code_snippet}",
                        f"```",
                        f"</details>",
                        f"",
                    ])

                if finding.recommendation:
                    lines.append(f"💡 **Recommendation:** {finding.recommendation}")
                    lines.append("")

                if finding.policy_reference:
                    lines.append(f"📜 **Policy Citation:** `{finding.policy_reference}`")
                    lines.append("")

                lines.append("---")
                lines.append("")

        # Agent execution telemetry footnote
        if report.agent_summaries:
            lines.extend([
                f"## 🤖 Multi-Agent Execution Telemetry",
                f"",
                f"| Agent | Status | Duration | Token Usage | Findings |",
                f"| :--- | :---: | :---: | :---: | :---: |",
            ])
            for ag in report.agent_summaries:
                lines.append(
                    f"| `{ag.agent_name}` | `{ag.status}` | `{ag.duration_ms}ms` | `{ag.token_usage}` | `{ag.findings_count}` |"
                )
            lines.append("")

        lines.extend([
            f"---",
            f"<sub>*Report autonomously generated by CodeGuardian AI Multi-Agent Review Platform.*</sub>",
        ])

        return "\n".join(lines)
