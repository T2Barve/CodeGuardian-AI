import math
import re
from typing import Any, Dict, List, Optional, Tuple


def _tokenize(text: str) -> List[str]:
    """Tokenize and normalize text into clean alphanumeric tokens."""
    return re.findall(r"\b[a-zA-Z0-9_-]+\b", text.lower())


def _compute_tf(tokens: List[str]) -> Dict[str, float]:
    """Calculate term frequencies for token list."""
    tf: Dict[str, float] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0.0) + 1.0
    total = float(len(tokens)) or 1.0
    for t in tf:
        tf[t] = tf[t] / total
    return tf


def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
    """Compute cosine similarity between two sparse vector representations."""
    if not vec_a or not vec_b:
        return 0.0

    dot_product = 0.0
    for token, val_a in vec_a.items():
        if token in vec_b:
            dot_product += val_a * vec_b[token]

    norm_a = math.sqrt(sum(val * val for val in vec_a.values()))
    norm_b = math.sqrt(sum(val * val for val in vec_b.values()))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return min(1.0, max(0.0, dot_product / (norm_a * norm_b)))


class VectorRecord:
    def __init__(
        self,
        id: str,
        content: str,
        metadata: Dict[str, Any],
        vector: Optional[Dict[str, float]] = None,
    ):
        self.id = id
        self.content = content
        self.metadata = metadata
        self.vector = vector or _compute_tf(_tokenize(f"{content} {metadata.get('section', '')} {metadata.get('policy_name', '')}"))


class VectorStoreInterface:
    async def add_documents(self, documents: List[VectorRecord]) -> None:
        raise NotImplementedError

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 3,
        threshold: float = 0.60,
    ) -> List[Tuple[VectorRecord, float]]:
        raise NotImplementedError

    async def delete_by_policy_id(self, policy_id: str) -> None:
        raise NotImplementedError

    async def count(self) -> int:
        raise NotImplementedError


class MemoryVectorStore(VectorStoreInterface):
    """
    High-performance in-memory vector store with deterministic cosine similarity
    and metadata pre-filtering.
    """

    def __init__(self):
        self._records: Dict[str, VectorRecord] = {}

    async def add_documents(self, documents: List[VectorRecord]) -> None:
        for doc in documents:
            self._records[doc.id] = doc

    async def search(
        self,
        query: str,
        category: Optional[str] = None,
        top_k: int = 3,
        threshold: float = 0.60,
    ) -> List[Tuple[VectorRecord, float]]:
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        query_vec = _compute_tf(query_tokens)
        results: List[Tuple[VectorRecord, float]] = []

        for record in self._records.values():
            # Category filter
            if category:
                rec_cat = str(record.metadata.get("category", "")).upper()
                if rec_cat != category.upper():
                    continue

            score = _cosine_similarity(query_vec, record.vector)
            if score >= threshold:
                results.append((record, round(score, 4)))

        # Sort descending by similarity score
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    async def delete_by_policy_id(self, policy_id: str) -> None:
        to_delete = [
            doc_id
            for doc_id, doc in self._records.items()
            if doc.metadata.get("policy_id") == policy_id
        ]
        for doc_id in to_delete:
            del self._records[doc_id]

    async def count(self) -> int:
        return len(self._records)

    def clear(self) -> None:
        self._records.clear()


# Global singleton instance for runtime and test access
_global_vector_store: Optional[VectorStoreInterface] = None


def get_vector_store() -> VectorStoreInterface:
    global _global_vector_store
    if _global_vector_store is None:
        _global_vector_store = MemoryVectorStore()
    return _global_vector_store


def reset_vector_store() -> None:
    global _global_vector_store
    _global_vector_store = MemoryVectorStore()
