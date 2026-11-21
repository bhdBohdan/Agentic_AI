"""FastAPI entry point for the in-memory MCP-backed Clash Royale chat."""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware

from agentic.agent_kit import openrouter_model
from agentic.mcp.mcp_host import connect_servers
from common.types.Chat import (
    ChatHistoryMessage,
    ChatHistoryResponse,
    ChatRequest,
    ChatResponse,
    ChatSummary,
    NewChatResponse,
)


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
MAX_SESSIONS = int(os.environ.get("MAX_CHAT_SESSIONS", "100"))
MAX_HISTORY_MESSAGES = int(os.environ.get("MAX_HISTORY_MESSAGES", "12"))

SYSTEM_PROMPT = """You are the Clash Royale knowledge-graph assistant.
Answer using the conversation and evidence returned by the connected MCP tools.
Use the tools for cards, decks, mechanics, documents, and graph relationships.
Cite source or chunk identifiers when the tools return them. If the evidence does
not answer the question, say "not stated" rather than inventing facts.
For damage questions, retrieve the relevant card and tower statistics first, then
call the battle_damage_calculator tool. Do not estimate simulated damage manually.
Use earlier conversation messages when the user refers to a card or statistic already
discussed.
Answer in clear Markdown with real line breaks."""
logging.basicConfig(
    level=logging.INFO,
    # format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    format="%(message)s",
)
logger = logging.getLogger(__name__)


@dataclass
class ChatSession:
    messages: list[Any] = field(default_factory=list)
    last_used: float = field(default_factory=time.monotonic)

    @property
    def title(self) -> str:
        for message in self.messages:
            if _message_role(message) in {"human", "user"}:
                text = " ".join(_message_text(message).split())
                if text:
                    return text[:48] + ("..." if len(text) > 48 else "")
        return "New conversation"

    def context(self, question: str, memory: list[str]) -> list[Any]:
        context: list[Any] = []
        if memory:
            context.append({
                "role": "system",
                "content": "ABOUT THE USER:\n" + "\n".join(f"- {fact}" for fact in memory),
            })
        context.extend(self.messages)
        context.append({"role": "user", "content": question})
        return context

    def update(self, messages: list[Any]) -> None:
        self.messages = list(messages[-MAX_HISTORY_MESSAGES:])
        self.last_used = time.monotonic()

    def transcript(self) -> list[ChatHistoryMessage]:
        return [
            ChatHistoryMessage(role=_message_role(message), content=_message_text(message))
            for message in self.messages
            if _message_role(message) in {"human", "user", "ai", "assistant"}
            and _message_text(message).strip()
        ]


class UserMemory:
    """Explicit, process-only facts shared by all chat sessions."""

    _CUES = (
        "i prefer ",
        "i use ",
        "i like ",
        "i dislike ",
        "i don't like ",
        "my name is ",
        "my ",
        "remember that ",
    )

    def __init__(self, limit: int = 20) -> None:
        self.facts: list[str] = []
        self.limit = limit

    def remember(self, message: str) -> None:
        fact = " ".join(message.strip().split())
        lowered = fact.casefold()
        if not fact or not any(cue in lowered for cue in self._CUES):
            return
            
        if not any(existing.casefold() == lowered for existing in self.facts):
            self.facts.append(fact)
            self.facts = self.facts[-self.limit:]


class InMemoryChatStore:
    """Session histories that disappear when this process stops."""

    def __init__(self) -> None:
        self._sessions: OrderedDict[str, ChatSession] = OrderedDict()
        self.user_memory = UserMemory()

    def new(self) -> str:
        conversation_id = uuid.uuid4().hex
        self._sessions[conversation_id] = ChatSession()
        self._trim()
        return conversation_id

    def get(self, conversation_id: str) -> ChatSession:
        session = self._sessions.get(conversation_id)
        if session is None:
            raise KeyError(conversation_id)
        self._sessions.move_to_end(conversation_id)
        session.last_used = time.monotonic()
        return session

    def summaries(self) -> list[ChatSummary]:
        return [
            ChatSummary(
                conversation_id=conversation_id,
                title=session.title,
                updated_at=session.last_used,
            )
            for conversation_id, session in reversed(self._sessions.items())
        ]

    def _trim(self) -> None:
        while len(self._sessions) > MAX_SESSIONS:
            self._sessions.popitem(last=False)

    def remember(self, message: str) -> None:
        self.user_memory.remember(message)

    def memory(self) -> list[str]:
        return list(self.user_memory.facts)


class MCPAgentRuntime:
    """Lazily connects to the configured MCP servers and builds one agent loop."""

    def __init__(self) -> None:
        self._client = None
        self._agent = None
        self._lock = asyncio.Lock()

    async def agent(self):
        async with self._lock:
            if self._agent is not None:
                return self._agent
            self._client = connect_servers()
            tools = await self._client.get_tools()
            if not tools:
                raise RuntimeError("No tools were loaded from the configured MCP servers.")
            self._agent = create_agent(
                openrouter_model(),
                tools=tools,
                system_prompt=SYSTEM_PROMPT,
                middleware=[
                    ModelCallLimitMiddleware(
                        run_limit=int(os.environ.get("MAX_MODEL_CALLS", "8")),
                        exit_behavior="error",
                    )
                ],
            )
            return self._agent


app = FastAPI(title="Lance Chat", version="0.2.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
sessions = InMemoryChatStore()
runtime = MCPAgentRuntime()


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


def _log_agent_steps(messages: list[Any], model_calls: int, seen: set[str]) -> None:
    for message in messages:
        tool_calls = getattr(message, "tool_calls", []) or []
        signature = repr((
            _message_role(message),
            getattr(message, "id", None),
            _message_text(message),
            tool_calls,
        ))
        if signature in seen:
            continue
        seen.add(signature)
        if _message_role(message) == "ai":
            for call in tool_calls:
                logger.info(
                    "[assistant] tool_call name=%s arguments=%s",
                    call.get("name"),
                    call.get("args", {}),
                )
            if _message_text(message).strip():
                logger.info("[assistant] %s", _message_text(message)[:1000])
        elif _message_role(message) == "tool":
            logger.info(
                "[tool] result name=%s value=%s",
                getattr(message, "name", "unknown"),
                _message_text(message)[:1000],
            )
    logger.info("[agent] state model_calls=%d messages=%d", model_calls, len(messages))


@app.get("/", response_class=FileResponse)
async def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/chat/new", response_model=NewChatResponse)
async def new_chat() -> NewChatResponse:
    conversation_id = sessions.new()
    logger.info("[chat] new conversation=%s", conversation_id)
    return NewChatResponse(conversation_id=conversation_id)


@app.get("/api/chats", response_model=list[ChatSummary])
async def list_chats() -> list[ChatSummary]:
    return sessions.summaries()


@app.get("/api/chats/{conversation_id}", response_model=ChatHistoryResponse)
async def get_chat(conversation_id: str) -> ChatHistoryResponse:
    try:
        session = sessions.get(conversation_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found.") from exc
    return ChatHistoryResponse(
        conversation_id=conversation_id,
        title=session.title,
        messages=session.transcript(),
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    message = request.message.strip()
    if not message:
        conversation_id = request.conversation_id or sessions.new()
        return ChatResponse(
            reply="Tell me what you would like to explore.",
            sources=[],
            conversation_id=conversation_id,
        )

    conversation_id = request.conversation_id or sessions.new()
    try:
        session = sessions.get(conversation_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found. Start a new chat.",
        ) from exc

    try:
        from agentic.agent_kit import COUNTER

        logger.info(
            "[memory] facts=%s",
            sessions.memory() or "(none)",
        )
        logger.info(
            "[user] conversation=%s message=%r history_messages=%d",
            conversation_id,
            message,
            len(session.messages),
        )
        sessions.remember(message)
        memory = sessions.memory()
        logger.info("[memory] after_user_message=%s", memory or "(none)")
        before_calls = COUNTER.calls
        agent = await runtime.agent()
        seen_steps: set[str] = set()
        last_model_calls = 0
        messages: list[Any] = []
        async for state in agent.astream(
            {"messages": session.context(message, memory)},
            stream_mode="values",
        ):
            state_messages = state.get("messages", [])
            messages = list(state_messages)
            model_calls = COUNTER.calls - before_calls
            if model_calls != last_model_calls:
                logger.info(
                    "[agent] model_call=%d/%s",
                    model_calls,
                    os.environ.get("MAX_MODEL_CALLS", "8"),
                )
                last_model_calls = model_calls
            _log_agent_steps(messages, model_calls, seen_steps)
        messages = list(messages)
        if not messages:
            raise RuntimeError("The MCP agent returned no messages.")
        session.update(messages)
        answer = getattr(messages[-1], "text", "") or str(messages[-1].content)
        logger.info(
            "[assistant] conversation=%s title=%r answer=%s",
            conversation_id,
            session.title,
            answer[:1000],
        )
        return ChatResponse(
            reply=answer,
            sources=[],
            conversation_id=conversation_id,
        )
    except HTTPException:
        raise
    except Exception as exc:
        error_id = uuid.uuid4().hex[:8]
        logger.exception("[chat] failed id=%s conversation=%s", error_id, conversation_id)
        if type(exc).__name__ == "ModelCallLimitExceededError":
            logger.info(
                "[agent] stopped_by_limit conversation=%s model_calls=%d",
                conversation_id,
                COUNTER.calls - before_calls,
            )
            return ChatResponse(
                reply=(
                    "I reached the model-call limit before finishing this calculation. "
                    "Please retry the question, or increase MAX_MODEL_CALLS."
                ),
                sources=[],
                conversation_id=conversation_id,
            )
        raise HTTPException(
            status_code=502,
            detail=f"Assistant request failed [{error_id}]: {exc}",
        ) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000)
