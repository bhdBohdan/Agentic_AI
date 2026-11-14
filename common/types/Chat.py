from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    sources: list[str]
    conversation_id: str


class NewChatResponse(BaseModel):
    conversation_id: str


class ChatSummary(BaseModel):
    conversation_id: str
    title: str
    updated_at: float


class ChatHistoryMessage(BaseModel):
    role: str
    content: str


class ChatHistoryResponse(BaseModel):
    conversation_id: str
    title: str
    messages: list[ChatHistoryMessage]