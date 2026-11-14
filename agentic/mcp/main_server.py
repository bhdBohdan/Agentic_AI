"""Clash Royale MCP server and bounded agent-loop demonstration.

Run the MCP server from the project root:

    python agentic/mcp/main_server.py

Run a local demonstration that deliberately stops at the model-call limit:

    python agentic/mcp/main_server.py --demo-limit

Run a follow-up conversation demonstration:

    python agentic/mcp/main_server.py --demo-conversation

The server exposes read-only tools over the Clash Royale Neo4j graph. The optional
agent runner uses LangChain's loop with both model-call and per-tool limits. Every
query writes a complete trace to ``agentic/logs``.
"""

import argparse
import asyncio
import json
import logging
import pathlib
import sys
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parent.parent
sys.path.insert(0, str(_ROOT / "neo4j"))
sys.path.insert(0, str(_ROOT / "neo4j" / "createKG"))
sys.path.insert(0, str(_ROOT / "neo4j" / "extractKG"))
sys.path.insert(0, str(_ROOT / "embedding"))
sys.path.insert(0, str(_ROOT / "common"))
sys.path.insert(0, str(_ROOT / "agentic"))

from mcp.server.fastmcp import FastMCP  # noqa: E402
from mcp.server.fastmcp.prompts import base  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402
from pydantic import Field  # noqa: E402

from graph_db import connect  # noqa: E402
from retrievers import hybrid, read  # noqa: E402
from embedding_client import EmbeddingClient  # noqa: E402

INSTRUCTION = (
    "You are a Clash Royale knowledge-graph assistant. Answer only from the "
    "conversation and tool results. Use the tools when the answer requires corpus "
    "evidence, card statistics, deck composition, or graph relationships. Cite "
    "evidence using the source or chunk identifiers returned by tools. If the "
    "available evidence does not answer the question, say: not stated."
)

READ_ONLY = ToolAnnotations(readOnlyHint=True)
LOG_DIR = _ROOT / "agentic" / "logs"
DOCUMENTS_MENTIONING = """
MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk)-[:MENTIONS]->(e)
WHERE (e:Card OR e:DeckType OR e:GameMechanic OR e:Role OR
       e:TowerTroop OR e:CrownTower)
  AND toLower(e.name) CONTAINS toLower($name)
RETURN DISTINCT d.name AS document, collect(DISTINCT c.id) AS chunks
ORDER BY document
"""
CARD_STATS = """
MATCH (c:Card)
WHERE toLower(c.name) CONTAINS toLower($name)
RETURN c.name AS card, properties(c) AS properties
ORDER BY card
LIMIT $limit
"""
DECK_CARDS = """
MATCH (d:DeckType)-[r:INCLUDES_CARD]->(c:Card)
WHERE toLower(d.name) CONTAINS toLower($deck)
RETURN d.name AS deck_type, c.name AS card, properties(c) AS card_properties,
       r.chunks AS evidence
ORDER BY card
LIMIT $limit
"""

logging.getLogger("asyncio").addFilter(
    lambda record: not (
        record.exc_info and record.exc_info[0] is ConnectionResetError
    )
)

driver = connect()
emb = EmbeddingClient()
mcp = FastMCP("clash-royale", port=8002)


@mcp.tool(annotations=READ_ONLY)
def search_clash_royale(
    query: str = Field(description="A question about Clash Royale cards, decks, or rules"),
) -> str:
    """Search Clash Royale passages and graph facts relevant to a question."""
    return "\n".join(hybrid(driver, emb, query)) or "Nothing found."


@mcp.tool(annotations=READ_ONLY)
def card_stats(
    name: str = Field(description="A card name, for example Golem or Miner"),
    limit: int = Field(default=10, ge=1, le=25, description="Maximum cards to return"),
) -> str:
    """Return structured statistics for matching Clash Royale cards."""
    rows = read(driver, CARD_STATS, name=name, limit=limit)
    return json.dumps(rows, ensure_ascii=False, default=str) if rows else "No cards found."


@mcp.tool(annotations=READ_ONLY)
def deck_cards(
    deck_type: str = Field(description="A deck archetype, for example Beatdown or Siege"),
    limit: int = Field(default=20, ge=1, le=40, description="Maximum cards to return"),
) -> str:
    """Return cards, properties, and evidence for a deck archetype."""
    rows = read(driver, DECK_CARDS, deck=deck_type, limit=limit)
    return json.dumps(rows, ensure_ascii=False, default=str) if rows else "No deck found."


@mcp.tool(annotations=READ_ONLY)
def documents_mentioning(
    name: str = Field(description="A card, deck type, mechanic, or tower troop name"),
) -> str:
    """List source documents and chunks that mention a named graph entity."""
    rows = read(driver, DOCUMENTS_MENTIONING, name=name)
    return json.dumps(rows, ensure_ascii=False) if rows else f"No documents mention {name!r}."


@mcp.resource(
    "clash://instruction",
    name="instruction",
    title="Clash Royale assistant instruction",
    description="Grounding and citation rules for the Clash Royale assistant",
    mime_type="text/plain",
)
def instruction() -> str:
    return INSTRUCTION


@mcp.prompt(
    name="explain_card",
    title="Explain a Clash Royale card",
    description="Explain a card using graph evidence and card statistics.",
)
def explain_card(
    card: str = Field(description="The card to explain, such as Golem"),
) -> list[base.Message]:
    return [base.UserMessage(f"Explain the Clash Royale card {card} using the graph and cite evidence.")]


def _message_role(message: Any) -> str:
    if isinstance(message, dict):
        return str(message.get("role", "unknown"))
    return str(getattr(message, "type", "unknown"))


def _message_text(message: Any) -> str:
    if isinstance(message, dict):
        content = message.get("content", "")
    else:
        content = getattr(message, "text", getattr(message, "content", ""))
    if isinstance(content, list):
        return " ".join(str(part) for part in content)
    return str(content)


def _serialize_messages(messages: list[Any]) -> list[dict[str, str]]:
    return [{"role": _message_role(message), "content": _message_text(message)}
            for message in messages]


@dataclass
class ConversationHistory:
    """Rolling history shared by follow-up queries.

    The newest messages stay verbatim. Older user and assistant messages are reduced
    to a deterministic summary, so history growth does not consume an unbounded
    amount of context or require an extra model call.
    """

    max_messages: int = 8
    messages: list[Any] = field(default_factory=list)
    summary: str = ""

    def __post_init__(self) -> None:
        if self.max_messages < 1:
            raise ValueError("max_messages must be at least 1")

    def context_for(self, question: str) -> list[Any]:
        context: list[Any] = []
        if self.summary:
            context.append({
                "role": "system",
                "content": "SUMMARY OF EARLIER CONVERSATION:\n" + self.summary,
            })
        context.extend(self.messages)
        context.append({"role": "user", "content": question})
        return context

    def update(self, messages: list[Any]) -> None:
        if len(messages) <= self.max_messages:
            self.messages = list(messages)
            return
        older = messages[:-self.max_messages]
        summary_lines = []
        for message in older:
            role = _message_role(message)
            if role in {"human", "user", "ai", "assistant"}:
                text = " ".join(_message_text(message).split())
                if text:
                    summary_lines.append(f"{role}: {text[:500]}")
        if summary_lines:
            addition = "\n".join(summary_lines)
            self.summary = f"{self.summary}\n{addition}".strip()
        self.messages = list(messages[-self.max_messages:])


def _trace_messages(messages: list[Any]) -> list[dict[str, Any]]:
    steps = []
    for message in messages:
        message_type = getattr(message, "type", "")
        if message_type == "ai":
            for call in getattr(message, "tool_calls", []) or []:
                steps.append({
                    "kind": "tool_call",
                    "tool": call.get("name"),
                    "arguments": call.get("args", {}),
                })
        elif message_type == "tool":
            steps.append({
                "kind": "tool_result",
                "tool": getattr(message, "name", None),
                "returned": getattr(message, "text", str(message)),
            })
    return steps


def _write_trace(question: str, messages: list[Any], *, model_calls: int,
                 tool_counts: Counter, status: str, context: list[Any],
                 history: ConversationHistory, summary_used: str,
                 error: str | None = None) -> pathlib.Path:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}.json"
    payload = {
        "question": question,
        "status": status,
        "model_calls": model_calls,
        "tool_calls": dict(tool_counts),
        "steps": _trace_messages(messages),
        "answer": getattr(messages[-1], "text", "") if messages else "",
        "context": {
            "system_instruction": INSTRUCTION,
            "history_policy": (
                f"Keep the newest {history.max_messages} messages. Replace older "
                "user/assistant messages with a deterministic summary; do not keep "
                "older tool payloads verbatim."
            ),
            "summary_used_for_this_query": summary_used,
            "summary_after_this_query": history.summary,
            "messages_before_agent_loop": _serialize_messages(context),
            "subsequent_model_calls": (
                "LangChain adds the assistant tool call and tool result messages to "
                "the agent state before the next model call."
            ),
        },
    }
    if error:
        payload["error"] = error
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


async def run_agent(question: str, *, max_model_calls: int = 4,
                    max_calls_per_tool: int = 2,
                    conversation: ConversationHistory | None = None) -> dict[str, Any]:
    """Run a bounded agent turn and persist a complete trace.

    ``conversation`` may be reused for follow-up questions. Its compacted history
    is included before the new user message.
    """
    from agent_kit import COUNTER, openrouter_model
    from langchain.agents import create_agent
    from langchain.tools import tool
    from langchain.agents.middleware import ModelCallLimitMiddleware

    model = openrouter_model()
    tool_counts: Counter = Counter()

    def check_limit(name: str) -> None:
        if tool_counts[name] >= max_calls_per_tool:
            raise RuntimeError(f"tool call limit reached for {name}: {max_calls_per_tool}")
        tool_counts[name] += 1

    @tool
    def search_tool(query: str) -> str:
        """Search Clash Royale passages and graph facts relevant to a question."""
        check_limit("search_clash_royale")
        return search_clash_royale(query)

    @tool
    def card_stats_tool(name: str, limit: int = 10) -> str:
        """Return structured statistics for matching Clash Royale cards."""
        check_limit("card_stats")
        return card_stats(name, limit)

    @tool
    def deck_cards_tool(deck_type: str, limit: int = 20) -> str:
        """Return cards and evidence for a Clash Royale deck archetype."""
        check_limit("deck_cards")
        return deck_cards(deck_type, limit)

    @tool
    def documents_tool(name: str) -> str:
        """List source documents and chunks mentioning a graph entity."""
        check_limit("documents_mentioning")
        return documents_mentioning(name)

    tools = [search_tool, card_stats_tool, deck_cards_tool, documents_tool]
    agent = create_agent(
        model,
        tools=tools,
        system_prompt=INSTRUCTION,
        middleware=[ModelCallLimitMiddleware(
            run_limit=max_model_calls,
            exit_behavior="error",
        )],
    )
    before = COUNTER.calls
    conversation = conversation or ConversationHistory()
    summary_used = conversation.summary
    context = conversation.context_for(question)
    messages: list[Any] = []
    status = "completed"
    error = None
    try:
        result = await agent.ainvoke({"messages": context})
        messages = result["messages"]
        conversation.update(messages)
    except Exception as exc:
        status = "stopped_by_limit" if "limit" in str(exc).lower() else "failed"
        error = f"{type(exc).__name__}: {exc}"
    calls = COUNTER.calls - before
    trace = _write_trace(
        question,
        messages,
        model_calls=calls,
        tool_counts=tool_counts,
        status=status,
        context=context,
        history=conversation,
        summary_used=summary_used,
        error=error,
    )
    return {
        "status": status,
        "model_calls": calls,
        "tool_calls": dict(tool_counts),
        "trace": str(trace),
        "answer": getattr(messages[-1], "text", "") if messages else "",
    }


async def demo_limit() -> None:
    """Demonstrate a run stopped by a deliberately small model-call limit."""
    result = await run_agent(
        "Compare Beatdown and Siege decks, list representative cards, and explain "
        "which mechanics make them different.",
        max_model_calls=1,
        max_calls_per_tool=1,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


async def demo_conversation() -> None:
    """Demonstrate a first question followed by a context-dependent follow-up."""
    conversation = ConversationHistory(max_messages=8)
    for question in (
        "What is a Beatdown deck and which cards are commonly used in it?",
        "And how do I change this strategy to defend better?",
    ):
        result = await run_agent(question, conversation=conversation)
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--demo-limit", action="store_true",
                        help="Run the bounded agent with one model call to demonstrate stopping")
    parser.add_argument("--demo-conversation", action="store_true",
                        help="Run a first question and a follow-up using shared history")
    parser.add_argument("--question", help="Run one bounded Clash Royale agent query")
    parser.add_argument("--follow-up", action="append", default=[],
                        help="Additional follow-up question; may be supplied more than once")
    parser.add_argument("--history-messages", type=int, default=8,
                        help="Number of newest messages retained verbatim")
    parser.add_argument("--max-model-calls", type=int, default=4)
    parser.add_argument("--max-tool-calls", type=int, default=2)
    args = parser.parse_args()
    if args.demo_limit:
        asyncio.run(demo_limit())
    elif args.demo_conversation:
        asyncio.run(demo_conversation())
    elif args.question:
        conversation = ConversationHistory(max_messages=args.history_messages)

        async def run_turns() -> None:
            for question in [args.question, *args.follow_up]:
                result = await run_agent(
                    question,
                    max_model_calls=args.max_model_calls,
                    max_calls_per_tool=args.max_tool_calls,
                    conversation=conversation,
                )
                print(json.dumps(result, indent=2, ensure_ascii=False))

        asyncio.run(run_turns())
    else:
        mcp.run(transport="streamable-http")
