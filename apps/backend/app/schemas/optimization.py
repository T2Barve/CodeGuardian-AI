from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class OptimizationIssue(BaseModel):
    """Specific algorithmic or performance bottleneck identified in code."""

    issue_type: str = Field(..., description="Category: NESTED_LOOP, STRING_CONCAT, LINEAR_LOOKUP, UNCACHED_RECURSION, REDUNDANT_CALL")
    line_number: Optional[int] = Field(None, description="Line number of detected bottleneck")
    description: str = Field(..., description="Technical explanation of the inefficiency")
    current_complexity: str = Field(..., description="Current Big-O complexity (e.g. O(N^2), O(2^N))")
    target_complexity: str = Field(..., description="Target Big-O complexity after optimization (e.g. O(N), O(1))")
    suggestion: str = Field(..., description="Actionable suggestion for algorithmic improvement")


class CodeOptimizationRequest(BaseModel):
    """Request payload to analyze and optimize code snippet."""

    code: str = Field(..., min_length=1, max_length=50000, description="Source code to analyze and optimize")
    file_path: Optional[str] = Field("main.py", description="File path or name for language context")
    language: Optional[str] = Field("python", description="Programming language: python, javascript, typescript")
    target_language_explanation: Optional[str] = Field(
        "en",
        description="Language for explanation: en, hi (Hindi), hinglish (Hinglish), ur (Urdu), mr (Marathi), gu (Gujarati)",
    )


class CodeOptimizationResponse(BaseModel):
    """Result of algorithmic code optimization and complexity reduction."""

    is_optimized: bool = Field(..., description="Whether the original code was already optimal or required optimization")
    original_code: str = Field(..., description="Verbatim original code provided")
    optimized_code: str = Field(..., description="Drop-in replacement optimized code")
    diff: str = Field(..., description="Unified diff showing exact algorithmic improvements")
    syntax_valid: bool = Field(..., description="Whether optimized code passes AST syntax validation")
    issues: List[OptimizationIssue] = Field(default_factory=list, description="List of detected algorithmic bottlenecks")
    original_time_complexity: str = Field(..., description="Estimated original time complexity: O(1), O(N), O(N^2), etc.")
    optimized_time_complexity: str = Field(..., description="Optimized time complexity: O(1), O(N), O(N log N)")
    original_space_complexity: str = Field(..., description="Estimated original space complexity")
    optimized_space_complexity: str = Field(..., description="Optimized space complexity")
    performance_improvement_factor: str = Field(..., description="Human-readable performance gain factor")
    explanation: str = Field(..., description="In-depth explanation of optimization in chosen language")
    multilingual_explanations: Dict[str, str] = Field(
        default_factory=dict,
        description="Explanations across English, Hindi, Hinglish, Urdu, Marathi, and Gujarati",
    )
    voice_script: str = Field(..., description="Phonetically formatted voice-to-voice narration script")
    audio_stream_url: Optional[str] = Field(None, description="Direct URL to stream synthesized AI voice audio")
