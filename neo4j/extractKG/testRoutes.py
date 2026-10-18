"""Evaluate only the hybrid and Cypher retrievers on the Clash Royale test set.

    python testRoutes.py
    python testRoutes.py --runs 2
    python testRoutes.py --test another_test_set.json --output results/routes.json

Each question is sent through both retrievers. The retrieved sources are passed to
the same grounded answering step used by the other Graph RAG scripts. Progress is
saved after every result so an interrupted run can continue without repeating
completed calls.
"""

import argparse
import json
import pathlib
import sys
from typing import Any

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE.parent.parent / "embedding"))
sys.path.insert(0, str(_HERE.parent.parent / "common"))

from graph_db import connect  # noqa: E402
from llm_client import LLMClient  # noqa: E402
from embedding_client import EmbeddingClient  # noqa: E402
from retrievers import answer  # noqa: E402
from router import retrieve  # noqa: E402

RETRIEVERS = ("hybrid", "cypher")
DEFAULT_TEST = _HERE / "test_set.json"
DEFAULT_OUTPUT = _HERE / "results" / "testRoutes.json"


def _load_questions(path: pathlib.Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    questions = data.get("questions")
    if not isinstance(questions, list):
        raise ValueError(f"{path} must contain a 'questions' list")
    return questions


def _save(path: pathlib.Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")


def _compact(text: str, length: int = None) -> str:
    cleaned = " ".join(text.split())
    return cleaned[:length] if length else cleaned


def _write_report(
    path: pathlib.Path,
    test_path: pathlib.Path,
    questions: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> None:
    lines = [
        f"# Retriever Test Results: `{test_path.name}`",
        "",
        "**Evaluated Retrievers:** `hybrid`, `cypher`",
        "",
        "---",
        "",
    ]

    for question in questions:
        question_id = question["id"]
        lines.extend([
            f"## Question {question_id}",
            "",
            f"> {question['question']}",
            "",
            f"**Expected Answer:** {question.get('expected', '')}",
            "",
            "| Run | Retriever | Answer | Problem |",
            "|:---:|:---|:---|:---|",
        ])

        matching = [row for row in rows if row["id"] == question_id]
        sorted_matching = sorted(matching, key=lambda item: (item["retriever"], item["run"]))

        for row in sorted_matching:
            answer = _compact(row["answer"]).replace("|", "/")
            problem = _compact(row.get("problem") or "").replace("|", "/")
            lines.append(f"| {row['run']} | `{row['retriever']}` | {answer} | {problem} |")

        lines.append("")

        # Add queries grouped cleanly below the table if present
        queries_to_show = [r for r in sorted_matching if r.get("query")]
        if queries_to_show:
            lines.append("**Generated Queries:**")
            lines.append("")
            for row in queries_to_show:
                lines.extend([
                    f"- **Run {row['run']} ({row['retriever']}):**",
                    "  ```cypher",
                    f"  {row['query']}",
                    "  ```",
                    "",
                ])

        lines.extend(["---", ""])

    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--test", type=pathlib.Path, default=DEFAULT_TEST,
                        help="Competency-question JSON file")
    parser.add_argument("--runs", type=int, default=1,
                        help="Number of runs per question and retriever")
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT,
                        help="JSON progress/output file")
    parser.add_argument("--fresh", action="store_true",
                        help="Ignore an existing output file and start again")
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")

    questions = _load_questions(args.test)
    rows = [] if args.fresh or not args.output.exists() else json.loads(
        args.output.read_text(encoding="utf-8")
    )
    done = {(row["run"], row["id"], row["retriever"]) for row in rows}
    driver = connect()
    emb = EmbeddingClient()
    llm = LLMClient(provider="gemini", model="gemini-3.1-flash-lite")
    try:
        for run_number in range(1, args.runs + 1):
            for question in questions:
                for retriever_name in RETRIEVERS:
                    key = (run_number, question["id"], retriever_name)
                    if key in done:
                        continue
                    result = retrieve(driver, emb, llm, question["question"],
                                      retriever_name)
                    problem = result.get("problem")
                    text = answer(llm, question["question"], result["sources"])
                    if problem:
                        text = f"(query refused or failed: {problem})"
                    row = {
                        "run": run_number,
                        "id": question["id"],
                        "retriever": retriever_name,
                        "answer": text,
                        "sources": result["sources"],
                        "problem": problem,
                    }
                    if result.get("query"):
                        row["query"] = result["query"]
                    rows.append(row)
                    done.add(key)
                    _save(args.output, rows)
                    print(f"run {run_number} {question['id']} {retriever_name}: "
                          f"{_compact(text)}")
    finally:
        driver.close()

    report = args.output.with_suffix(".md")
    _write_report(report, args.test, questions, rows)
    print(f"\nJSON results: {args.output}")
    print(f"Markdown report: {report}")


if __name__ == "__main__":
    main()
