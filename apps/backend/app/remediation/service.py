from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.finding import Finding
from app.models.remediation import RemediationAttempt
from app.rag.service import PolicyService
from app.schemas.policy import RAGQueryRequest
from app.remediation.generator import PatchGenerator
from app.remediation.sandbox import SandboxPipeline
from app.repositories.audit_repository import AuditRepository
from app.repositories.finding_repository import FindingRepository
from app.repositories.remediation_repository import RemediationRepository
from app.schemas.remediation import (
    RemediationListResponse,
    RemediationResponse,
    RemediationStatus,
    ValidationStageStatus,
)
from app.security.path_traversal import validate_safe_path
from app.utils.logging import get_logger

logger = get_logger("codeguardian.remediation.service")


class RemediationService:
    """
    Coordinates AI patch generation, 5-stage sandboxed validation,
    persistence of RemediationAttempt records, and compliance auditing.
    """

    def __init__(
        self,
        generator: Optional[PatchGenerator] = None,
        sandbox: Optional[SandboxPipeline] = None,
    ):
        self.generator = generator or PatchGenerator()
        self.sandbox = sandbox or SandboxPipeline()
        self.policy_service = PolicyService()

    async def _resolve_file_content(
        self, finding: Finding, workspace_path: Optional[str] = None
    ) -> str:
        """Resolves target source code content from workspace or finding evidence."""
        if workspace_path:
            try:
                full_path = validate_safe_path(workspace_path, finding.file_path, allow_nonexistent=False)
                if full_path.is_file():
                    return full_path.read_text(encoding="utf-8")
            except Exception as path_err:
                logger.warning(f"Could not safely access workspace file '{finding.file_path}': {path_err}")

        # Fallback: Check finding evidence code snippets
        if finding.evidence:
            for ev in finding.evidence:
                if ev.code_snippet and ev.code_snippet.strip():
                    return ev.code_snippet

        # Fallback: Construct synthetic minimal context from description/recommendation
        return (
            f"# Source file: {finding.file_path}\n"
            f"# Finding: {finding.title}\n"
            f"def execute_task():\n"
            f"    # Line {finding.line_start or 1}\n"
            f"    return True\n"
        )

    async def generate_and_validate_remediation(
        self,
        session: AsyncSession,
        finding_id: str,
        requested_by: Optional[str] = None,
        custom_instructions: Optional[str] = None,
        workspace_path: Optional[str] = None,
    ) -> RemediationResponse:
        """
        Orchestrates patch generation, sandboxed validation pipeline,
        database persistence, and audit logging.
        """
        finding_repo = FindingRepository(session)
        remediation_repo = RemediationRepository(session)
        audit_repo = AuditRepository(session)

        # 1. Fetch Finding with evidence
        stmt = (
            select(Finding)
            .options(selectinload(Finding.evidence), selectinload(Finding.review_run))
            .where(Finding.id == finding_id)
        )
        res = await session.execute(stmt)
        finding = res.scalars().first()

        if not finding:
            raise ValueError(f"Finding with ID '{finding_id}' not found.")

        # 2. Retrieve Policy Context if available
        policy_context = None
        try:
            req = RAGQueryRequest(
                query=f"{finding.category} {finding.title} {finding.description}",
                limit=1,
            )
            rag_res = await self.policy_service.query_policies(session, req)
            if rag_res.matches:
                policy_context = f"{rag_res.matches[0].policy_title}: {rag_res.matches[0].chunk_text}"
        except Exception as e:
            logger.debug(f"Policy RAG lookup skipped for remediation: {e}")


        # 3. Resolve Original File Content
        original_content = await self._resolve_file_content(finding, workspace_path)

        # 4. Generate Candidate Patch
        candidate = await self.generator.generate_patch(
            finding=finding,
            file_content=original_content,
            policy_context=policy_context,
            custom_instructions=custom_instructions,
        )

        # 5. Persist Initial Remediation Attempt (status: VALIDATING)
        attempt = RemediationAttempt(
            finding_id=finding.id,
            requested_by=requested_by,
            patch=candidate.patch,
            status=RemediationStatus.VALIDATING.value,
            validation_result={},
            error_message=None,
        )
        session.add(attempt)
        await session.flush()

        # 6. Execute Sandboxed 5-Stage Validation Pipeline
        validation_result = await self.sandbox.execute_validation_pipeline(
            original_content=original_content,
            patch_str=candidate.patch,
            finding=finding,
            workspace_path=workspace_path,
        )

        # 7. Update Attempt Status & Details
        final_status = (
            RemediationStatus.VALIDATED.value
            if validation_result.overall == ValidationStageStatus.PASSED
            else RemediationStatus.REJECTED.value
        )
        val_dict = validation_result.model_dump()

        attempt.status = final_status
        attempt.validation_result = val_dict
        attempt.error_message = validation_result.error_summary

        # 8. Record Compliance Audit Log
        await audit_repo.record(
            actor=requested_by or "SYSTEM_REMEDIATION_ENGINE",
            action=f"REMEDIATION_{final_status}",
            resource_type="RemediationAttempt",
            resource_id=attempt.id,
            metadata_payload={
                "finding_id": finding.id,
                "overall": validation_result.overall.value,
                "can_create_pr": validation_result.can_create_pr,
                "stages": {
                    "patch": validation_result.patch_application.status.value,
                    "syntax": validation_result.syntax_check.status.value,
                    "scanner": validation_result.scanner_check.status.value,
                    "tests": validation_result.unit_tests.status.value,
                    "regression": validation_result.regression_check.status.value,
                },
            },
        )

        await session.commit()
        await session.refresh(attempt)

        return RemediationResponse(
            id=attempt.id,
            finding_id=attempt.finding_id,
            status=RemediationStatus(attempt.status),
            patch=attempt.patch,
            target_file=finding.file_path,
            explanation=candidate.explanation,
            validation_result=attempt.validation_result,
            error_message=attempt.error_message,
            can_create_pr=validation_result.can_create_pr,
            created_at=attempt.created_at,
            updated_at=attempt.updated_at,
        )

    async def get_remediation(
        self, session: AsyncSession, remediation_id: str
    ) -> Optional[RemediationResponse]:
        """Retrieves a remediation attempt by UUID."""
        remediation_repo = RemediationRepository(session)
        attempt = await remediation_repo.get_with_fix_pr(remediation_id)
        if not attempt:
            return None

        can_create_pr = attempt.status == RemediationStatus.VALIDATED.value and not attempt.fix_pr
        target_file = attempt.finding.file_path if attempt.finding else None

        return RemediationResponse(
            id=attempt.id,
            finding_id=attempt.finding_id,
            status=RemediationStatus(attempt.status),
            patch=attempt.patch,
            target_file=target_file,
            explanation=attempt.validation_result.get("explanation"),
            validation_result=attempt.validation_result,
            error_message=attempt.error_message,
            can_create_pr=can_create_pr,
            created_at=attempt.created_at,
            updated_at=attempt.updated_at,
        )

    async def list_remediations_for_finding(
        self, session: AsyncSession, finding_id: str
    ) -> RemediationListResponse:
        """Lists all remediation attempts for a given finding."""
        stmt = (
            select(RemediationAttempt)
            .options(selectinload(RemediationAttempt.finding))
            .where(RemediationAttempt.finding_id == finding_id)
            .order_by(RemediationAttempt.created_at.desc())
        )
        res = await session.execute(stmt)
        attempts = res.scalars().all()

        items = [
            RemediationResponse(
                id=a.id,
                finding_id=a.finding_id,
                status=RemediationStatus(a.status),
                patch=a.patch,
                target_file=a.finding.file_path if a.finding else None,
                explanation=a.validation_result.get("explanation"),
                validation_result=a.validation_result,
                error_message=a.error_message,
                can_create_pr=a.status == RemediationStatus.VALIDATED.value,
                created_at=a.created_at,
                updated_at=a.updated_at,
            )
            for a in attempts
        ]

        return RemediationListResponse(
            finding_id=finding_id,
            total=len(items),
            items=items,
        )

    async def revalidate_remediation(
        self,
        session: AsyncSession,
        remediation_id: str,
        workspace_path: Optional[str] = None,
    ) -> RemediationResponse:
        """Re-executes the sandboxed validation pipeline on an existing remediation attempt."""
        stmt = (
            select(RemediationAttempt)
            .options(
                selectinload(RemediationAttempt.finding).selectinload(Finding.evidence),
                selectinload(RemediationAttempt.finding).selectinload(Finding.review_run),
            )
            .where(RemediationAttempt.id == remediation_id)
        )
        res = await session.execute(stmt)
        attempt = res.scalars().first()

        if not attempt:
            raise ValueError(f"RemediationAttempt with ID '{remediation_id}' not found.")

        finding = attempt.finding
        original_content = await self._resolve_file_content(finding, workspace_path)

        validation_result = await self.sandbox.execute_validation_pipeline(
            original_content=original_content,
            patch_str=attempt.patch,
            finding=finding,
            workspace_path=workspace_path,
        )

        final_status = (
            RemediationStatus.VALIDATED.value
            if validation_result.overall == ValidationStageStatus.PASSED
            else RemediationStatus.REJECTED.value
        )
        attempt.status = final_status
        attempt.validation_result = validation_result.model_dump()
        attempt.error_message = validation_result.error_summary

        audit_repo = AuditRepository(session)
        await audit_repo.record(
            actor="SYSTEM_REMEDIATION_ENGINE",
            action=f"REMEDIATION_REVALIDATED_{final_status}",
            resource_type="RemediationAttempt",
            resource_id=attempt.id,
            metadata_payload={"status": final_status},
        )

        await session.commit()
        await session.refresh(attempt)

        return RemediationResponse(
            id=attempt.id,
            finding_id=attempt.finding_id,
            status=RemediationStatus(attempt.status),
            patch=attempt.patch,
            target_file=finding.file_path,
            explanation=f"Revalidated {finding.title}",
            validation_result=attempt.validation_result,
            error_message=attempt.error_message,
            can_create_pr=validation_result.can_create_pr,
            created_at=attempt.created_at,
            updated_at=attempt.updated_at,
        )
