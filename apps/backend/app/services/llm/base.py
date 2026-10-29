from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class TokenUsageTracking(BaseModel):
    """Normalized token accounting model across LLM providers."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model_name: str = "unknown"
    estimated_cost: float = 0.0

    def add(self, other: "TokenUsageTracking") -> None:
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.total_tokens += other.total_tokens
        self.estimated_cost += other.estimated_cost


class LLMResponse(BaseModel, Generic[T]):
    """Standardized response container returned by LLM abstraction."""
    raw_content: str
    structured_data: Optional[T] = None
    token_usage: TokenUsageTracking = Field(default_factory=TokenUsageTracking)


class BaseLLMProvider(ABC):
    """
    Abstract LLM Provider interface.
    
    Adheres to Rule 37: LLM Provider Abstraction.
    All agents interact exclusively with this contract, preventing provider lock-in.
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> str:
        """Generates natural language text given a prompt and optional system instructions."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        prompt: str,
        response_schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 4096,
    ) -> T:
        """Generates validated, schema-conforming structured output parsed into Pydantic model T."""
        pass

    @abstractmethod
    async def embed(self, texts: List[str]) -> List[List[float]]:
        """Generates numerical vector embeddings for a list of input strings."""
        pass

    @abstractmethod
    def get_model_name(self) -> str:
        """Returns the identifier of the active foundation model."""
        pass
