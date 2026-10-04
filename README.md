# Lumen Chat

A small FastAPI chat interface designed as a starting point for a future RAG assistant.

## Run locally

From this folder, use the project virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload
```

Then open http://127.0.0.1:8000.

## Ingest the corpus

Build the persistent Chroma collection once before using chat:

```powershell
python .\embedding\ingest.py .\corpus\cr --name=cr_chunks  --reset
python .\embedding\ingest.py .\corpus\steam --name=steam_chunks  --reset
```

The collection is stored in `embedding/chroma/`. Re-run with `--reset` when
the corpus or chunk settings change. The API reads the `chunks` collection by
default; set `CHROMA_COLLECTION` if you ingest under another name.

## API shape

`POST /api/chat`

```json
{
  "message": "What should I learn next?"
}
```

The endpoint retrieves the nearest corpus chunks from Chroma, attaches them as
context to `LLMClient`, and returns the generated answer plus source citations.
