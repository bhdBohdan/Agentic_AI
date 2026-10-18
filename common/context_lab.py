"""Utilities for formatting grounded question-and-source prompts."""

from collections.abc import Iterable


def render(question: str, *, task: str, fmt: str,
           sources: Iterable[str]) -> str:
    """Render a numbered source context for a grounded answer prompt."""
    source_text = "\n\n".join(
        f"[{index}] {source}" for index, source in enumerate(sources, start=1)
    )
    return (
        f"QUESTION:\n{question}\n\n"
        f"TASK:\n{task}\n\n"
        f"FORMAT:\n{fmt}\n\n"
        f"SOURCES:\n{source_text}"
    )
