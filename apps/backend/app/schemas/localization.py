from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SupportedLanguage(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"
    HINGLISH = "hinglish"
    URDU = "ur"
    MARATHI = "mr"
    GUJARATI = "gu"


class FindingExplanationRequest(BaseModel):
    """Request payload to retrieve multilingual AI explanation of a finding."""

    language: SupportedLanguage = Field(
        default=SupportedLanguage.ENGLISH,
        description="Target language: en (English), hi (Hindi), hinglish (Hinglish), ur (Urdu), mr (Marathi), gu (Gujarati)",
    )
    include_voice_script: bool = Field(
        default=True,
        description="Whether to include TTS audio-ready voice narration script",
    )


class FindingExplanationResponse(BaseModel):
    """Multilingual, explainable AI breakdown of a finding with speech narration."""

    finding_id: str = Field(..., description="Target finding ID")
    language: str = Field(..., description="Selected language code")
    language_display_name: str = Field(..., description="Localized native name of the language")
    title: str = Field(..., description="Localized finding title")
    summary: str = Field(..., description="Concise explanation of the flaw in the selected language")
    root_cause: str = Field(..., description="Why this error or vulnerability occurs")
    risk_impact: str = Field(..., description="Real-world security or performance hazard")
    remediation_steps: List[str] = Field(..., description="Step-by-step resolution instructions")
    code_example_fix: Optional[str] = Field(None, description="Concrete before-and-after code snippet")
    voice_script: str = Field(..., description="Natural conversational script formatted for AI voice audio narration")
    audio_stream_url: Optional[str] = Field(None, description="URL endpoint to stream spoken explanation")
