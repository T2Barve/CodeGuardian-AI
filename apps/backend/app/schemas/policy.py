from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class PolicyChunkResponse(BaseModel):
    id: str
    policy_id: str
    chunk_index: int
    content: str
    embedding_reference: str
    metadata_payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class PolicyCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255, description="Human-readable title of the policy")
    category: str = Field(..., description="Category: SECURITY, QUALITY, TESTING, DOCUMENTATION, DEPENDENCY")
    version: str = Field(default="1.0.0", max_length=32)
    source: str = Field(..., max_length=255, description="Origin file path or URL")
    active: bool = True


class PolicyResponse(BaseModel):
    id: str
    name: str
    category: str
    version: str
    source: str
    active: bool
    created_at: datetime
    updated_at: datetime
    chunks: Optional[List[PolicyChunkResponse]] = None


class PolicyIngestRequest(BaseModel):
    name: str = Field(..., description="Title of the policy")
    category: str = Field(..., description="Category: SECURITY, QUALITY, TESTING, DOCUMENTATION, DEPENDENCY")
    source: str = Field(..., description="Source path (e.g. policies/security/db_security.md)")
    version: str = Field(default="1.0.0")
    content: str = Field(..., min_length=10, description="Raw markdown or plaintext content")
    language_scope: Optional[List[str]] = Field(default=None, description="Optional target languages")


class PolicyIngestResult(BaseModel):
    policy_id: str
    name: str
    category: str
    chunks_created: int
    vector_refs: List[str]
    status: str = "INGESTED"


class RetrievedPolicyChunk(BaseModel):
    chunk_id: str
    policy_id: str
    policy_name: str
    category: str
    section: str
    source_file: str
    content: str
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, description="Semantic search query or finding description")
    category: Optional[str] = Field(default=None, description="Optional category pre-filter")
    target_languages: Optional[List[str]] = Field(default=None, description="Target languages in PR diff")
    top_k: int = Field(default=3, ge=1, le=10)
    similarity_threshold: float = Field(default=0.60, ge=0.0, le=1.0)


class RAGQueryResponse(BaseModel):
    query: str
    category_filter: Optional[str] = None
    results_count: int
    chunks: List[RetrievedPolicyChunk] = Field(default_factory=list)
    formatted_context: str = Field(..., description="Context string or Anti-Hallucination Sentinel")
    retrieval_duration_ms: float
