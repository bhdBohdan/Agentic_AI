"""Build the Clash Royale graph, ready for retrieval. One command.

    python build_graph.py

It empties the database and loads the Clash Royale corpus extraction, copies available
chunk vectors, and checks that stored vectors come from the embedding model.
"""

import pathlib
import sys
import time

_HERE = pathlib.Path(__file__).resolve().parent

# Add directories to path correctly
sys.path.insert(0, str(_HERE))                    # Current directory
sys.path.insert(0, str(_HERE.parent))             # Parent directory (where graph_db folder lives)
sys.path.insert(0, str(_HERE.parent / "createKG"))  # createKG folder
for _d in ("embedding",):
    sys.path.insert(0, str(_HERE.parent.parent / _d))

from embedding_client import EmbeddingClient  # noqa: E402
from graph_db import breakdown, connect, run  # noqa: E402
from kg_loader import (
    CORPUS,
    copy_vectors,
    load_all,
    read_chunks,
    resolve_results,
)
from extraction import load_results
from vector_check import check_and_record  # noqa: E402


def build(driver) -> dict:
    """The whole rebuild. Returns the resolution, for reading what it merged and dropped."""
    chunks = read_chunks(CORPUS)

    results_path = _HERE.parent / "extractions" / "clash_royale.json"
    results = load_results(results_path, chunks)
    resolved = resolve_results(results)
    
    run(driver, "MATCH (n) DETACH DELETE n")
    load_all(driver, chunks, resolved)
    vectors = copy_vectors(driver, chunks)
    model = "not checked"
    if vectors:
        model = check_and_record(driver, EmbeddingClient())
    print(f"{len(resolved['entities'])} entities ({len(resolved['type_conflicts'])} names still "
          f"under two types, {len(resolved['dropped_relations'])} relationships dropped); "
          f"{vectors} chunk vectors from {model}")
    return resolved


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    started = time.time()
    driver = connect()
    build(driver)
    detail = breakdown(driver)
    print("nodes by label:        " + ", ".join(f"{k} {v}" for k, v in detail["labels"].items()))
    print("relationships by type: " + ", ".join(f"{k} {v}" for k, v in detail["relationships"].items()))
    print(f"{time.time() - started:.1f}s")
    driver.close()
