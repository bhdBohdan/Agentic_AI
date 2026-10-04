"""Week 3 — embed a corpus once, into a store that survives the process.

    python ingest.py corpus/                 # every .txt, .md, .csv, and .xlsx under corpus/
    python ingest.py corpus/ --reset         # re-chunk from scratch
    python ingest.py corpus/ --chunk-size 300 --overlap 60

Why this is a script and not a notebook cell
--------------------------------------------
Ingestion is a slow, one-off batch job; querying is interactive. They belong in
different places, which is the same "ingest once, query every call" split the
lecture draws.

The slowness is not incidental. `gemini-embedding-001` allows roughly 100 texts
per minute (measured 2026-09-14), counted per text rather than per request, so
batching cannot speed it up -- only waiting works. A 3,000-chunk corpus is about
half an hour. `EmbeddingClient` paces itself so this runs unattended.

Run it once, leave it running, and every notebook afterwards opens the finished
index in `./chroma/` instantly. Re-run with `--reset` only when you change the
chunk size, because that invalidates every chunk boundary you already stored.

Lab 2 requires a re-seedable `ingest.py`. This is that file's ancestor: keep it
working as your corpus grows.
"""

import argparse
import csv
import pathlib
import sys
import time

from openpyxl import load_workbook

from chunking import chunk_text
from vector_store import VectorStore

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SUFFIXES = {".txt", ".md", ".csv", ".xlsx"}


def read_corpus(source: pathlib.Path) -> list[tuple[str, str]]:
    """Return [(filename, text)] from text, CSV, and Excel files."""
    if source.is_file():
        return [_read_document(source)]
    files = sorted(p for p in source.rglob("*") if p.suffix.lower() in SUFFIXES)
    if not files:
        raise SystemExit(f"No .txt, .md, .csv, or .xlsx files under {source}")
    return [_read_document(path) for path in files]


def _read_document(path: pathlib.Path) -> tuple[str, str]:
    """Read a supported document and return its filename and searchable text."""
    if path.suffix.lower() == ".csv":
        sections: list[str] = []
        with path.open("r", encoding="utf-8-sig", newline="") as csv_file:
            for row_number, values in enumerate(csv.reader(csv_file), start=1):
                cells = [
                    " ".join(value.split())
                    for value in values
                    if value.strip()
                ]
                if cells:
                    sections.append(f"Row {row_number}: " + " | ".join(cells))
        return path.name, "\n".join(sections)

    if path.suffix.lower() != ".xlsx":
        return path.name, path.read_text(encoding="utf-8")

    workbook = load_workbook(path, read_only=True, data_only=True)
    sections: list[str] = []
    try:
        for worksheet in workbook.worksheets:
            rows: list[str] = []
            for row_number, values in enumerate(worksheet.iter_rows(values_only=True), start=1):
                cells = [
                    " ".join(str(value).split())
                    for value in values
                    if value is not None and str(value).strip()
                ]
                if cells:
                    rows.append(
                        f"Sheet: {worksheet.title} | Row {row_number}: "
                        + " | ".join(cells)
                    )
            if rows:
                sections.extend(rows)
    finally:
        workbook.close()

    return path.name, "\n".join(sections)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", type=pathlib.Path, help="A file, or a directory of .txt/.md/.csv/.xlsx")
    parser.add_argument("--chunk-size", type=int, default=200, help="Words per chunk")
    parser.add_argument("--overlap", type=int, default=40, help="Words repeated between chunks")
    parser.add_argument("--name", default="chunks", help="Chroma collection name")
    parser.add_argument("--reset", action="store_true", help="Clear the collection first")
    args = parser.parse_args()

    documents = read_corpus(args.source)
    chunks: list[str] = []
    metadatas: list[dict] = []
    step = args.chunk_size - args.overlap  # words advanced per chunk; see chunking.py
    for filename, text in documents:
        is_tabular = pathlib.Path(filename).suffix.lower() in {".csv", ".xlsx"}
        pieces = (
            [line for line in text.splitlines() if line.strip()]
            if is_tabular
            else chunk_text(text, chunk_size=args.chunk_size, overlap=args.overlap)
        )
        for j, piece in enumerate(pieces):
            chunks.append(piece)
            # Provenance travels with each chunk: which document, which chunk of
            # it, and roughly where (word offset) it starts. search() hands this
            # back so an answer can cite its sources.
            metadata = {
                "source": filename,
                "chunk_index": j,
                "n_chunks": len(pieces),
            }
            if not is_tabular:
                metadata["start_word"] = j * step
            metadatas.append(metadata)
        print(f"  {filename:<40} {len(text.split()):>6} words -> {len(pieces):>4} chunks")

    if not chunks:
        raise SystemExit("Corpus produced no chunks -- is it empty?")

    store = VectorStore(name=args.name, reset=args.reset)
    already = store.count()
    if already and not args.reset:
        print(f"\nCollection {args.name!r} already holds {already} chunks.")
        print("Pass --reset to rebuild it, or --name to ingest alongside it.")
        return

    minutes = len(chunks) / 90
    print(f"\n{len(documents)} documents -> {len(chunks)} chunks")
    print(f"Embedding at ~90 texts/minute: expect roughly {minutes:.0f} minute(s).")
    print("Leave this running.\n")

    started = time.time()
    store.add(chunks, metadatas=metadatas)
    elapsed = time.time() - started

    print(f"\nDone. {store.count()} chunks indexed in {elapsed / 60:.1f} minutes.")
    print(f"Stored in {store.path} -- open it from a notebook with VectorStore(name={args.name!r}).")


if __name__ == "__main__":
    main()
