from pathlib import Path
import os
import sys

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
sys.path.insert(0, str(BASE_DIR / "common"))
sys.path.insert(0, str(BASE_DIR / "embedding"))

from llm_client import LLMClient
from vector_store import VectorStore

app = FastAPI(title="Lumen Chat", version="0.1.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    reply: str
    sources: list[str]


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


@app.get("/", response_class=FileResponse)
async def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    message = request.message.strip()
    print(f"\n[input] {message!r}")
    if not message:
        return ChatResponse(reply="Tell me what you would like to explore.", sources=[])

    try:
        store, llm = get_rag_components()
        if store.count() == 0:
            raise HTTPException(
                status_code=503,
                detail="The Chroma collection is empty. Run the ingestion command first.",
            )
        results = store.search(message, n_results=int(os.environ.get("RETRIEVAL_RESULTS", "5")))

        print(f"[chroma] closest_results={len(results)}")
        for rank, result in enumerate(results, start=1):
            metadata = result["metadata"]
            source = metadata.get("source", "unknown source")
            chunk_index = metadata.get("chunk_index", "?")
            preview = " ".join(result["chunk"].split())[:160]
            print(
                f"[chroma] rank={rank} distance={result['distance']:.4f} "
                f"source={source}#{chunk_index} preview={preview!r}"
            )
        context, sources = build_context(results)
        print(f"[llm] context_chars={len(context)} sources={sources}")
        result = llm.chat(
            message,
            system=(

                "You are a direct, helpful assistant. Answer the user's question using "
                "the provided context when it is relevant. If the context does not contain "
                "the answer, say that clearly instead of inventing facts. "
                "Answer in clear Markdown. Do not include unsafe HTML. "
                "Use real newline characters between headings, paragraphs, list items, "
                "and fenced code blocks; never put an entire Markdown answer on one line. "
                "If context has URL picture links, display them as images in Markdown. "
                "Add sources to your answers using the format [source_name.type#chunk_index]. "
                "Do not mention the retrieval process unless asked.\n\n"
                f"Context:\n{context}"
            ),
            temperature=0.2,
            max_tokens=600,
        )
        
        print(f"[llm] response={result.text!r}")
        return ChatResponse(reply=result.text, sources=sources)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Assistant request failed: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)