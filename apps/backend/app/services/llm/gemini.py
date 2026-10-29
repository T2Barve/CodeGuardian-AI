import json
from typing import Any, Dict, List, Optional, Type, TypeVar
import structlog
from pydantic import BaseModel
from app.services.llm.base import BaseLLMProvider, TokenUsageTracking

logger = structlog.get_logger(__name__)
T = TypeVar("T", bound=BaseModel)


class GeminiProvider(BaseLLMProvider):
    """
    Google Gemini Foundation Model Provider.
    
    Uses official `google.genai` SDK with native JSON schema enforcement,
    token telemetry tracking, and structured Pydantic deserialization.
    """

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-2.5-flash",
    ):
        self.api_key = api_key
        self.model_name = model_name
        self._client = None
        self._init_client()

    def _init_client(self) -> None:
        try:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        except Exception as exc:
            logger.error("Failed to initialize Google GenAI Client", error=str(exc))
            self._client = None

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        if not self._client:
            raise RuntimeError("Gemini Client is uninitialized or API key is missing.")

        try:
            from google.genai import types

            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system_instruction,
            )
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            return response.text or ""
        except Exception as exc:
            logger.error("Gemini text generation failed", model=self.model_name, error=str(exc))
            raise

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> T:
        if not self._client:
            raise RuntimeError("Gemini Client is uninitialized or API key is missing.")

        try:
            from google.genai import types

            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=response_schema,
            )
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config,
            )
            raw_text = response.text or "{}"
            parsed_data = json.loads(raw_text)
            return response_schema.model_validate(parsed_data)
        except Exception as exc:
            logger.error("Gemini structured generation failed", model=self.model_name, error=str(exc))
            raise

    async def embed(self, texts: List[str]) -> List[List[float]]:
        if not self._client:
            raise RuntimeError("Gemini Client is uninitialized or API key is missing.")

        try:
            embeddings: List[List[float]] = []
            for text in texts:
                result = self._client.models.embed_content(
                    model="text-embedding-004",
                    contents=text,
                )
                if hasattr(result, "embedding") and hasattr(result.embedding, "values"):
                    embeddings.append(result.embedding.values)
                elif hasattr(result, "embeddings") and len(result.embeddings) > 0:
                    embeddings.append(result.embeddings[0].values)
                else:
                    embeddings.append([])
            return embeddings
        except Exception as exc:
            logger.error("Gemini embedding failed", error=str(exc))
            raise

    def get_model_name(self) -> str:
        return self.model_name
