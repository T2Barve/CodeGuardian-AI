from fastapi import APIRouter, HTTPException, Query, Response, status

from app.optimization.engine import CodeOptimizationEngine
from app.schemas.optimization import (
    CodeOptimizationRequest,
    CodeOptimizationResponse,
)
from app.voice.service import AIVoiceService

router = APIRouter(prefix="/optimization", tags=["NLP Code Optimization & Complexity Engine"])

optimization_engine = CodeOptimizationEngine()
voice_service = AIVoiceService()


@router.post(
    "/optimize",
    response_model=CodeOptimizationResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze code complexity and perform AST algorithmic optimization",
    description="Inspects code for quadratic bottlenecks O(N^2), in-loop string reallocations, and inefficient lookups, producing drop-in replacement code and multilingual explanations.",
)
async def optimize_code(request: CodeOptimizationRequest) -> CodeOptimizationResponse:
    """Performs static AST complexity analysis and algorithmic code optimization."""
    try:
        return optimization_engine.analyze_and_optimize(request)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Optimization analysis failed: {str(exc)}",
        )


@router.get(
    "/audio",
    summary="Stream AI Voice explanation audio for code optimization",
    description="Streams synthesized WAV audio narration explaining the code optimization in the requested language (en, hi, hinglish, ur, mr, gu).",
)
async def stream_optimization_audio(
    lang: str = Query("en", description="Target language: en, hi, hinglish, ur, mr, gu"),
) -> Response:
    """Streams synthesized PCM WAV voice audio."""
    sample_text = "CodeGuardian Code Optimization Engine. Algorithmic complexity reduced to linear time."
    if lang == "hi":
        sample_text = "कोडगार्डियन ऑप्टिमाइज़ेशन इंजन। नेस्टेड लूप हटाकर कोड की गति पचास गुना बढ़ा दी गई है।"
    elif lang == "hinglish":
        sample_text = "CodeGuardian Optimization Engine. Nested loop optimize karke execution linear time mein fast kar di gayi hai."
    elif lang == "ur":
        sample_text = "کوڈ گارڈین پرفارمنس انجن۔ کوڈ کی رفتار میں نمایاں بہتری کی گئی ہے۔"
    elif lang == "mr":
        sample_text = "कोडगार्डियन ऑप्टिमायझेशन इंजिन. कोडची वेळ कमी करून गती वाढवली आहे."
    elif lang == "gu":
        sample_text = "કોડગાર્ડિયન ઓપ્ટિમાઇઝેશન એન્જિન. નેસ્ટેડ લૂપ સુધારીને કોડ ઝડપી બનાવ્યો છે."

    wav_bytes = voice_service.synthesize_wav_stream(text=sample_text, lang=lang)
    return Response(content=wav_bytes, media_type="audio/wav")
