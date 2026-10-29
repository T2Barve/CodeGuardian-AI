from typing import Dict, List, Optional, Sequence
from sqlalchemy.ext.asyncio import AsyncSession

from app.findings.correlation import CorrelatedFinding
from app.models.finding import Finding, FindingEvidence
from app.repositories.audit_repository import AuditRepository
from app.repositories.finding_repository import FindingEvidenceRepository, FindingRepository
from app.utils.logging import get_logger

logger = get_logger("codeguardian.findings.service")


class FindingService:
    """
    Database persistence and query service for Findings and FindingEvidence.
    Ensures idempotent persistence, relational linkage, and audit logging.
    """

    @staticmethod
    async def persist_findings(
        session: AsyncSession,
        review_run_id: str,
        correlated_findings: List[CorrelatedFinding],
    ) -> List[Finding]:
        """
        Persists correlated findings and their respective evidence items into PostgreSQL.
        Maintains idempotency via the review_run_id and fingerprint.
        """
        finding_repo = FindingRepository(session)
        evidence_repo = FindingEvidenceRepository(session)
        audit_repo = AuditRepository(session)

        persisted_findings: List[Finding] = []

        for cf in correlated_findings:
            if isinstance(cf, dict):
                fp = cf.get("fingerprint")
                cat = cf.get("category", "SECURITY")
                sev = cf.get("severity", "LOW")
                conf = float(cf.get("confidence", 1.0))
                stat = cf.get("status", "OPEN")
                fp_path = cf.get("file_path", "unknown")
                l_start = cf.get("line_start")
                l_end = cf.get("line_end")
                title = cf.get("title", "Finding")
                desc = cf.get("description", "")
                imp = cf.get("impact")
                rec = cf.get("recommendation")
                pol_ref = cf.get("policy_reference")
                evidence_list = cf.get("evidence_items", [])
            else:
                fp = cf.fingerprint
                cat = cf.category
                sev = cf.severity
                conf = cf.confidence
                stat = cf.status
                fp_path = cf.file_path
                l_start = cf.line_start
                l_end = cf.line_end
                title = cf.title
                desc = cf.description
                imp = cf.impact
                rec = cf.recommendation
                pol_ref = cf.policy_reference
                evidence_list = cf.evidence_items

            # 1. Check if finding already exists in this run (idempotent guard)
            existing_finding = await finding_repo.get_by_fingerprint(
                review_run_id=review_run_id,
                fingerprint=fp,
            )

            if existing_finding:
                target_finding = existing_finding
                logger.info(
                    "Finding fingerprint already exists in review run; updating evidence",
                    extra={"finding_id": target_finding.id, "fingerprint": fp},
                )
            else:
                # 2. Create new Finding entity
                target_finding = await finding_repo.create(
                    review_run_id=review_run_id,
                    fingerprint=fp,
                    category=cat,
                    severity=sev,
                    confidence=conf,
                    status=stat,
                    file_path=fp_path,
                    line_start=l_start,
                    line_end=l_end,
                    title=title,
                    description=desc,
                    impact=imp,
                    recommendation=rec,
                    policy_reference=pol_ref,
                )

            # 3. Create associated FindingEvidence items
            for ev in evidence_list:
                if isinstance(ev, dict):
                    ev_source = ev.get("source", "tool")
                    ev_tool = ev.get("tool", "sast")
                    ev_rule = ev.get("rule_id")
                    ev_msg = ev.get("raw_message", "")
                    ev_snippet = ev.get("code_snippet")
                    ev_meta = ev.get("metadata_payload", {})
                else:
                    ev_source = ev.source
                    ev_tool = ev.tool
                    ev_rule = ev.rule_id
                    ev_msg = ev.raw_message
                    ev_snippet = ev.code_snippet
                    ev_meta = ev.metadata_payload

                await evidence_repo.create(
                    finding_id=target_finding.id,
                    source=ev_source,
                    tool=ev_tool,
                    rule_id=ev_rule,
                    raw_message=ev_msg,
                    code_snippet=ev_snippet,
                    metadata_payload=ev_meta,
                )

            persisted_findings.append(target_finding)

        # 4. Record compliance audit log
        await audit_repo.record(
            actor="codeguardian-engine",
            action="FINDINGS_SYNTHESIZED",
            resource_type="review_run",
            resource_id=review_run_id,
            metadata_payload={
                "findings_count": len(persisted_findings),
                "review_run_id": review_run_id,
            },
        )

        await session.commit()
        logger.info(
            f"Successfully persisted {len(persisted_findings)} findings with evidence for review {review_run_id}",
            extra={"review_run_id": review_run_id, "findings_count": len(persisted_findings)},
        )
        return persisted_findings

    @staticmethod
    async def list_findings_by_review(
        session: AsyncSession,
        review_run_id: str,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Sequence[Finding]:
        """Queries findings for a specific review run with optional filtering."""
        repo = FindingRepository(session)
        return await repo.list_by_review_run(
            review_run_id=review_run_id,
            category=category,
            severity=severity,
            status=status,
        )

    @staticmethod
    async def get_finding_by_id(
        session: AsyncSession,
        finding_id: str,
    ) -> Optional[Finding]:
        """Retrieves a single finding along with its complete evidence chain."""
        repo = FindingRepository(session)
        return await repo.get_with_evidence(finding_id)

    @staticmethod
    async def update_finding_status(
        session: AsyncSession,
        finding_id: str,
        new_status: str,
        actor: str = "reviewer",
        reason: Optional[str] = None,
    ) -> Optional[Finding]:
        """Updates finding lifecycle status (e.g. FALSE_POSITIVE, RESOLVED) with audit trail."""
        finding_repo = FindingRepository(session)
        audit_repo = AuditRepository(session)

        finding = await finding_repo.get(finding_id)
        if not finding:
            return None

        old_status = finding.status
        updated = await finding_repo.update(finding_id, status=new_status)

        await audit_repo.record(
            actor=actor,
            action="FINDING_STATUS_UPDATED",
            resource_type="finding",
            resource_id=finding_id,
            metadata_payload={
                "old_status": old_status,
                "new_status": new_status,
                "reason": reason,
            },
        )
        await session.commit()
        return updated
