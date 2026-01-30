from pydantic import BaseModel
from typing import List, Optional


class ChatMessage(BaseModel):
    role: str
    content: str
    sources: Optional[List[dict]] = None


class ChatSession(BaseModel):
    id: str
    title: str
    messages: List[ChatMessage]
    updated_at: Optional[int] = None


class ChatCreate(BaseModel):
    title: Optional[str] = None
    messages: Optional[List[ChatMessage]] = None


class QueryRequest(BaseModel):
    query: str
    k: int = 3
    history: Optional[List[ChatMessage]] = None
    use_rag: bool = True
    reference_chats: Optional[List[str]] = None
    # Optional LLM parameters (Ollama options)
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    repeat_penalty: Optional[float] = None
    seed: Optional[int] = None
    max_tokens: Optional[int] = None  # mapped to Ollama num_predict
    num_ctx: Optional[int] = None
    mirostat: Optional[int] = None
    mirostat_tau: Optional[float] = None
    mirostat_eta: Optional[float] = None
    stop: Optional[List[str]] = None


class QuerySource(BaseModel):
    source: str
    snippet: str


class QueryResponse(BaseModel):
    answer: str
    sources: List[QuerySource]
