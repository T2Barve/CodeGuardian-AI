import hashlib
from typing import Any, Callable, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel
from app.services.llm.base import BaseLLMProvider, TokenUsageTracking

T = TypeVar("T", bound=BaseModel)


class MockLLMProvider(BaseLLMProvider):
    """
    Deterministic Mock LLM Provider for unit testing and offline development.
    
    Guarantees:
    - Zero external network calls.
    - Deterministic token accounting.
    - Automatic synthesis of valid Pydantic instances matching the requested schema.
    - Custom override hooks for specific prompt testing.
    """

    def __init__(
        self,
        model_name: str = "mock-guardian-llm",
        default_text_response: str = "Analysis completed successfully with zero identified anomalies.",
    ):
        self.model_name = model_name
        self.default_text_response = default_text_response
        self.structured_handlers: Dict[Type[BaseModel], Callable[[str], BaseModel]] = {}
        self.recorded_prompts: List[str] = []
        self.total_tokens_used: int = 0

    def register_structured_handler(
        self, schema: Type[T], handler: Callable[[str], T]
    ) -> None:
        """Registers a custom factory function for a specific Pydantic schema."""
        self.structured_handlers[schema] = handler

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        self.recorded_prompts.append(prompt)
        prompt_tokens = len(prompt.split())
        completion_tokens = len(self.default_text_response.split())
        self.total_tokens_used += prompt_tokens + completion_tokens
        return self.default_text_response

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> T:
        self.recorded_prompts.append(prompt)
        prompt_tokens = len(prompt.split())

        # Check if an explicit mock handler was registered
        if response_schema in self.structured_handlers:
            result = self.structured_handlers[response_schema](prompt)
        else:
            # Dynamically synthesize valid dummy instance based on schema field definitions
            fields = response_schema.model_fields
            data: Dict[str, Any] = {}
            for field_name, field_info in fields.items():
                annotation = field_info.annotation
                if annotation == str or str(annotation) == "<class 'str'>":
                    data[field_name] = f"Mock {field_name}"
                elif annotation == int or str(annotation) == "<class 'int'>":
                    data[field_name] = 1
                elif annotation == float or str(annotation) == "<class 'float'>":
                    data[field_name] = 0.5
                elif annotation == bool or str(annotation) == "<class 'bool'>":
                    data[field_name] = True
                elif "Dict" in str(annotation) or "dict" in str(annotation):
                    data[field_name] = {}
                elif "List" in str(annotation) or "list" in str(annotation):
                    data[field_name] = []
                else:
                    data[field_name] = None
            result = response_schema.model_validate(data)

        completion_tokens = 50
        self.total_tokens_used += prompt_tokens + completion_tokens
        return result

    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generates deterministic 384-dimensional float embeddings using SHA-256 hashing."""
        embeddings = []
        for text in texts:
            seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:8], 16)
            vector = [((seed * (i + 1)) % 1000) / 1000.0 for i in range(384)]
            embeddings.append(vector)
        return embeddings

    def get_model_name(self) -> str:
        return self.model_name
