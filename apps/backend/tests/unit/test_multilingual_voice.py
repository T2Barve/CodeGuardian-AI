"""Tests for Multilingual Technical Localization Service and AI Voice Speech Synthesis."""

import io
import struct
import pytest
from httpx import ASGITransport, AsyncClient

from app.database.session import async_session_maker
from app.localization.service import MultilingualExplanationService
from app.main import app
from app.models.finding import Finding
from app.models.pull_request import PullRequest
from app.models.repository import Repository
from app.models.review import ReviewJob, ReviewRun
from app.schemas.localization import SupportedLanguage
from app.voice.service import AIVoiceService


def test_multilingual_service_sql_injection_translations():
    """Verifies that SQL Injection is translated accurately across all 6 languages."""
    service = MultilingualExplanationService()

    for lang in [
        SupportedLanguage.ENGLISH,
        SupportedLanguage.HINDI,
        SupportedLanguage.HINGLISH,
        SupportedLanguage.URDU,
        SupportedLanguage.MARATHI,
        SupportedLanguage.GUJARATI,
    ]:
        res = service.explain_finding(
            finding_id="f-sql-1",
            title="SQL Injection Detected in User Query",
            description="User input is concatenated into query without parameterization",
            category="SECURITY",
            severity="CRITICAL",
            language=lang,
        )
        assert res.finding_id == "f-sql-1"
        assert res.language == lang.value
        assert len(res.remediation_steps) > 0
        assert len(res.voice_script) > 10

    # Specifically verify Hindi, Marathi, Gujarati, and Urdu scripts
    hi_res = service.explain_finding(
        finding_id="f-1",
        title="SQL Injection",
        description="Raw SQL",
        category="SECURITY",
        severity="CRITICAL",
        language=SupportedLanguage.HINDI,
    )
    assert "एसक्यूएल" in hi_res.title or "SQL" in hi_res.title
    assert "पैरामीटराइज़्ड" in hi_res.remediation_steps[0]

    ur_res = service.explain_finding(
        finding_id="f-2",
        title="SQL Injection",
        description="Raw SQL",
        category="SECURITY",
        severity="CRITICAL",
        language=SupportedLanguage.URDU,
    )
    assert "انجیکشن" in ur_res.title

    mr_res = service.explain_finding(
        finding_id="f-3",
        title="SQL Injection",
        description="Raw SQL",
        category="SECURITY",
        severity="CRITICAL",
        language=SupportedLanguage.MARATHI,
    )
    assert "पॅरामीटराइझ्ड" in mr_res.remediation_steps[0]

    gu_res = service.explain_finding(
        finding_id="f-4",
        title="SQL Injection",
        description="Raw SQL",
        category="SECURITY",
        severity="CRITICAL",
        language=SupportedLanguage.GUJARATI,
    )
    assert "પેરામીટરાઇઝ્ડ" in gu_res.remediation_steps[0]


def test_ai_voice_service_wav_synthesis():
    """Verifies AI Voice Service synthesizes valid, audible WAV streams with proper RIFF headers."""
    voice_service = AIVoiceService()

    wav_bytes = voice_service.synthesize_wav_stream(
        text="Attention developer. A critical vulnerability was found in your pull request.",
        lang="en",
    )

    assert len(wav_bytes) > 500
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"
    assert wav_bytes[12:16] == b"fmt "

    # Check fmt subchunk
    subchunk1_size = struct.unpack("<I", wav_bytes[16:20])[0]
    assert subchunk1_size == 16
    audio_format = struct.unpack("<H", wav_bytes[20:22])[0]
    assert audio_format == 1  # PCM format


@pytest.mark.asyncio
async def test_findings_api_multilingual_explain_and_audio_endpoints():
    """Verifies POST /api/v1/findings/{id}/explain and GET /api/v1/findings/{id}/audio."""
    import random
    rand_id = random.randint(50000000, 99999999)
    async with async_session_maker() as session:
        repo = Repository(
            github_repo_id=rand_id,
            name=f"voice-demo-repo-{rand_id}",
            owner="guardian-org",
            url=f"https://github.com/guardian-org/voice-demo-repo-{rand_id}",
            default_branch="main",
            is_active=True,
        )
        session.add(repo)
        await session.flush()

        pr = PullRequest(
            github_pr_id=rand_id + 1,
            repository_id=repo.id,
            number=random.randint(100, 9999),
            title="Add user query handler",
            author="test-dev",
            source_branch="feature/query",
            target_branch="main",
            commit_sha="b" * 40,
            status="OPEN",
        )
        session.add(pr)
        await session.flush()

        job = ReviewJob(
            pull_request_id=pr.id,
            status="COMPLETED",
        )
        session.add(job)
        await session.flush()

        run = ReviewRun(
            review_job_id=job.id,
            status="COMPLETED",
        )
        session.add(run)
        await session.flush()

        finding = Finding(
            review_run_id=run.id,
            fingerprint="test-fp-voice-001",
            category="SECURITY",
            severity="CRITICAL",
            confidence=0.98,
            status="OPEN",
            file_path="app/query.py",
            line_start=15,
            line_end=17,
            title="Raw SQL Injection in Query Builder",
            description="String formatting is used to build SQL query dynamically",
            impact="Unauthorized database access",
            recommendation="Use parameterized query",
        )
        session.add(finding)
        await session.commit()
        finding_id = finding.id

    # 1. Test Multilingual Explanation Endpoint
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            f"/api/v1/findings/{finding_id}/explain",
            json={"language": "hi", "include_voice_script": True},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["language"] == "hi"
    assert "एसक्यूएल" in data["title"] or "SQL" in data["title"]
    assert "audio_stream_url" in data

    # 2. Test Audio Streaming Endpoint
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        audio_resp = await client.get(f"/api/v1/findings/{finding_id}/audio?lang=hi")

    assert audio_resp.status_code == 200
    assert audio_resp.headers["content-type"] == "audio/wav"
    assert audio_resp.content[:4] == b"RIFF"
