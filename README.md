# Lumen Chat

A small FastAPI chat interface designed as a starting point for a future RAG assistant.

## Run locally

From this folder, use the project virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn main:app --reload
```

Then open http://127.0.0.1:8080.

## API shape

`POST /api/chat`

```json
{
  "message": "What should I learn next?"
}
```

The response already includes a `sources` array. Replace the demo logic in `main.py` with document retrieval, prompt assembly, and your model client when the RAG layer is ready.
