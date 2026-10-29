"""Tests for NLP Code Optimization Engine, AST Complexity Visitor, and Multilingual Explanations."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.optimization.engine import ASTComplexityVisitor, CodeOptimizationEngine
from app.schemas.optimization import CodeOptimizationRequest


def test_ast_complexity_visitor_nested_loop_detection():
    """Verifies that nested for loops are flagged as quadratic O(N^2) bottlenecks."""
    code = """
def find_common_items(list1, list2):
    matches = []
    for item1 in list1:
        for item2 in list2:
            if item1 == item2:
                matches.append(item1)
    return matches
"""
    engine = CodeOptimizationEngine()
    req = CodeOptimizationRequest(code=code, target_language_explanation="hi")
    res = engine.analyze_and_optimize(req)

    assert res.is_optimized is True
    assert res.original_time_complexity == "O(N^2)"
    assert res.optimized_time_complexity == "O(N)"
    assert len(res.issues) > 0
    issues = res.issues
    assert any(i.issue_type == "NESTED_LOOP" for i in issues)
    assert res.syntax_valid is True
    assert "list2_set = set(list2)" in res.optimized_code


def test_ast_complexity_visitor_string_concat_detection():
    """Verifies in-loop string concatenation is flagged as quadratic memory allocation."""
    code = """
def build_report(items):
    report = ""
    for item in items:
        report += str(item)
    return report
"""
    engine = CodeOptimizationEngine()
    req = CodeOptimizationRequest(code=code, target_language_explanation="hinglish")
    res = engine.analyze_and_optimize(req)

    assert res.is_optimized is True
    assert any(i.issue_type == "STRING_CONCAT" for i in res.issues)
    assert "report.append" in res.optimized_code
    assert "''.join" in res.optimized_code


def test_ast_complexity_visitor_inefficient_range_len():
    """Verifies range(len(...)) is flagged for direct iteration."""
    code = """
def iterate_items(arr):
    for i in range(len(arr)):
        print(arr[i])
"""
    engine = CodeOptimizationEngine()
    req = CodeOptimizationRequest(code=code, target_language_explanation="mr")
    res = engine.analyze_and_optimize(req)

    assert any(i.issue_type == "INEFFICIENT_INDEXING" for i in res.issues)
    assert "enumerate" in res.optimized_code


def test_code_optimization_multilingual_explanations():
    """Verifies optimization explanations are generated across all 6 requested languages."""
    code = """
def slow_search(data1, data2):
    out = []
    for a in data1:
        for b in data2:
            if a == b:
                out.append(a)
    return out
"""
    engine = CodeOptimizationEngine()
    req = CodeOptimizationRequest(code=code, target_language_explanation="gu")
    res = engine.analyze_and_optimize(req)

    assert "en" in res.multilingual_explanations
    assert "hi" in res.multilingual_explanations
    assert "hinglish" in res.multilingual_explanations
    assert "ur" in res.multilingual_explanations
    assert "mr" in res.multilingual_explanations
    assert "gu" in res.multilingual_explanations

    # Check Gujarati content
    assert "કોડગાર્ડિયન" in res.multilingual_explanations["gu"]
    # Check Hindi content
    assert "कोडगार्डियन" in res.multilingual_explanations["hi"]
    # Check Urdu content
    assert "کوڈ گارڈین" in res.multilingual_explanations["ur"]
    # Check Marathi content
    assert "कोडगार्डियन" in res.multilingual_explanations["mr"]
    # Check Hinglish content
    assert "CodeGuardian" in res.multilingual_explanations["hinglish"]


def test_code_optimization_already_optimal():
    """Verifies that optimal code is recognized without introducing unnecessary changes."""
    code = """
def fast_lookup(key, mapping):
    return mapping.get(key, None)
"""
    engine = CodeOptimizationEngine()
    req = CodeOptimizationRequest(code=code, target_language_explanation="en")
    res = engine.analyze_and_optimize(req)

    assert res.is_optimized is False
    assert len(res.issues) == 0
    assert "already" in res.explanation.lower()


def test_code_optimization_syntax_error_handling():
    """Verifies that broken Python syntax is flagged with line number without crashing."""
    code = """
def broken_func(
    for x in 123
"""
    engine = CodeOptimizationEngine()
    req = CodeOptimizationRequest(code=code, target_language_explanation="hi")
    res = engine.analyze_and_optimize(req)

    assert res.syntax_valid is False
    assert len(res.issues) > 0
    assert res.issues[0].issue_type == "SYNTAX_ERROR"
    assert "सिंटैक्स" in res.multilingual_explanations["hi"]


@pytest.mark.asyncio
async def test_optimization_api_optimize_endpoint():
    """Verifies POST /api/v1/optimization/optimize returns 200 OK with full optimization payload."""
    code = """
def duplicate_scan(users1, users2):
    dups = []
    for u1 in users1:
        for u2 in users2:
            if u1 == u2:
                dups.append(u1)
    return dups
"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/optimization/optimize",
            json={"code": code, "target_language_explanation": "hi"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_optimized"] is True
    assert data["original_time_complexity"] == "O(N^2)"
    assert data["optimized_time_complexity"] == "O(N)"
    assert "multilingual_explanations" in data
    assert "hi" in data["multilingual_explanations"]


@pytest.mark.asyncio
async def test_optimization_api_audio_endpoint():
    """Verifies GET /api/v1/optimization/audio streams valid WAV PCM audio."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/optimization/audio?lang=hi")

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/wav"
    assert len(resp.content) > 1000
    # Check RIFF header magic bytes
    assert resp.content[:4] == b"RIFF"
    assert resp.content[8:12] == b"WAVE"
