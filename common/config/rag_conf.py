from common.llm_client import LLMClient
from embedding.vector_store import VectorStore
import os
import sys

_store: VectorStore | None = None
_llm: LLMClient | None = None

def get_rag_components() -> tuple[VectorStore, LLMClient]:
    global _store, _llm
    if _store is None:
        _store = VectorStore(name=os.environ.get("CHROMA_COLLECTION", "cr"))
    if _llm is None:
        _llm = LLMClient()
    return _store, _llm


def build_context(results: list[dict]) -> tuple[str, list[str]]:
    context_parts = []
    sources = []
    for result in results:
        metadata = result["metadata"]
        source = metadata.get("source", "unknown source")
        chunk_index = metadata.get("chunk_index", "?")
        citation = f"{source}#{chunk_index}"
        context_parts.append(f"[{citation}]\n{result['chunk']}")
        if citation not in sources:
            sources.append(citation)
    return "\n\n".join(context_parts), sources