import re
from typing import Any, Dict, List, Optional


class PolicyChunkItem:
    def __init__(
        self,
        chunk_index: int,
        section: str,
        content: str,
        metadata: Dict[str, Any],
    ):
        self.chunk_index = chunk_index
        self.section = section
        self.content = content.strip()
        self.metadata = metadata

    def to_dict(self) -> Dict[str, Any]:
        return {
            "chunk_index": self.chunk_index,
            "section": self.section,
            "content": self.content,
            "metadata": self.metadata,
        }


class PolicyChunker:
    """
    Intelligent Markdown and plaintext chunker preserving structural section boundaries (## / ###),
    code blocks, and section metadata for RAG indexing.
    """

    def __init__(self, max_chunk_chars: int = 1500, overlap_chars: int = 200):
        self.max_chunk_chars = max_chunk_chars
        self.overlap_chars = overlap_chars

    def chunk_document(
        self,
        raw_text: str,
        policy_name: str,
        category: str,
        source: str,
        version: str = "1.0.0",
        language_scope: Optional[List[str]] = None,
    ) -> List[PolicyChunkItem]:
        if not raw_text or not raw_text.strip():
            return []

        clean_text = raw_text.strip()

        # Split document by markdown section headers (## or ###)
        section_pattern = re.compile(r"^(#{2,3}\s+.+)$", re.MULTILINE)
        parts = section_pattern.split(clean_text)

        chunks: List[PolicyChunkItem] = []
        chunk_counter = 0

        # Base metadata common to all chunks
        base_metadata: Dict[str, Any] = {
            "policy_name": policy_name,
            "category": category,
            "source_file": source,
            "version": version,
            "language_scope": language_scope or ["all"],
        }

        # If document has ## or ### headers
        if len(parts) > 1:
            i = 0
            current_section = "Overview"
            # If parts[0] is preamble / # Title, ignore if only title or include in first section
            if not section_pattern.match(parts[0]):
                i = 1

            while i < len(parts):
                part = parts[i].strip()
                if section_pattern.match(part):
                    section_title = re.sub(r"^#{2,3}\s+", "", part)
                    # Next element contains the body
                    body = parts[i + 1].strip() if (i + 1 < len(parts)) else ""
                    i += 2

                    if not body:
                        continue

                    sub_chunks = self._split_if_oversized(body)
                    for sc in sub_chunks:
                        meta = {**base_metadata, "section": section_title}
                        chunks.append(
                            PolicyChunkItem(
                                chunk_index=chunk_counter,
                                section=section_title,
                                content=f"## {section_title}\n{sc}",
                                metadata=meta,
                            )
                        )
                        chunk_counter += 1
                else:
                    i += 1
        else:
            # Plain document without ## headers
            sub_chunks = self._split_if_oversized(clean_text)
            for idx, sc in enumerate(sub_chunks):
                meta = {**base_metadata, "section": "General Standard"}
                chunks.append(
                    PolicyChunkItem(
                        chunk_index=idx,
                        section="General Standard",
                        content=sc,
                        metadata=meta,
                    )
                )

        return chunks

    def _split_if_oversized(self, text: str) -> List[str]:
        text = text.strip()
        if len(text) <= self.max_chunk_chars:
            return [text]

        paragraphs = text.split("\n\n")
        result: List[str] = []
        buffer = ""

        for p in paragraphs:
            if len(buffer) + len(p) + 2 <= self.max_chunk_chars:
                buffer = f"{buffer}\n\n{p}".strip()
            else:
                if buffer:
                    result.append(buffer)
                buffer = p

        if buffer:
            result.append(buffer)

        return result if result else [text]
