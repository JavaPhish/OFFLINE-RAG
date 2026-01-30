from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from .indexer import load_or_build, build_index, needs_reindex, load_local_documents
from .ollama import predict_with_ollama
from .config import DATA_DIR, CHROMA_DIR, OLLAMA_MODEL, API_TOKEN, CHATS_DIR
from .schemas import QueryRequest, QueryResponse, QuerySource, ChatSession, ChatCreate
from .chat_store import list_chats, get_chat, save_chat, delete_chat, create_chat
from typing import List
from pathlib import Path
import logging

app = FastAPI(title="Local RAG API")

# Allow CORS from localhost dev servers
app.add_middleware(
    CORSMiddleware,
    # Allow common local dev origins (localhost and 127.0.0.1 on common ports)
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger("uvicorn")

# Keep a single vector_store in memory for faster responses
vector_store = None


def _ensure_index_up_to_date():
    """Refresh the in-memory vector store if source files changed or if not loaded."""
    global vector_store
    if vector_store is None or needs_reindex(DATA_DIR):
        logger.info("Detected file changes or missing index; rebuilding vector store.")
        vector_store = build_index(DATA_DIR, CHROMA_DIR)


@app.on_event("startup")
def startup_event():
    global vector_store
    try:
        vector_store = load_or_build(DATA_DIR, CHROMA_DIR)
        logger.info("Vector store loaded.")
    except Exception as e:
        logger.warning(f"Failed to load/build vector store at startup: {e}")


def _require_token(request: Request):
    if API_TOKEN:
        token = request.headers.get("authorization")
        if not token or token != f"Bearer {API_TOKEN}":
            raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/chats/summary/{chat_id}")
def get_chat_summary(chat_id: str, request: Request):
    """Get a brief summary of a chat for cross-reference context."""
    _require_token(request)
    chat = get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    messages = chat.get("messages", [])
    first_user_msg = next((m for m in messages if m.get("role") == "user"), None)
    first_question = first_user_msg.get("content", "")[:100] if first_user_msg else ""
    return {
        "id": chat["id"],
        "title": chat.get("title", "Chat"),
        "first_question": first_question,
        "message_count": len(messages)
    }


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, request: Request):
    """Handle a RAG query: on-call reindex if files changed, then retrieve and call Ollama."""
    _require_token(request)
    global vector_store
    try:
        _ensure_index_up_to_date()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    sources = []
    context_pieces = []
    all_sources = []
    data_files = []
    no_text_files = []
    if req.use_rag:
        retrieved = vector_store.similarity_search(req.query, k=req.k)
        for d in retrieved:
            src = d.metadata.get("source")
            snippet = (d.page_content or "").strip().replace("\n", " ")[:800]
            sources.append(QuerySource(source=src, snippet=snippet))
            context_pieces.append(f"Source: {src}\n{d.page_content}")
        try:
            metadatas = vector_store._collection.get(include=["metadatas"]).get("metadatas", [])
            all_sources = sorted({Path(m.get("source", "")).name for m in metadatas if m.get("source")})
        except Exception:
            all_sources = []
        try:
            data_files = sorted([p.name for p in Path(DATA_DIR).rglob("*") if p.is_file()])
        except Exception:
            data_files = []
        if data_files:
            no_text_files = [name for name in data_files if name not in all_sources]

    history_block = ""
    if req.history:
        # Keep only the most recent turns to avoid overlong prompts
        recent = req.history[-8:]
        lines = []
        for m in recent:
            role = "User" if m.role == "user" else "Assistant"
            lines.append(f"{role}: {m.content}")
        if lines:
            history_block = "Conversation so far:\n" + "\n".join(lines) + "\n\n"

    reference_block = ""
    if req.reference_chats:
        refs = []
        for chat_id in req.reference_chats[:3]:  # Limit to 3 referenced chats
            chat = get_chat(chat_id)
            if not chat:
                continue
            messages = chat.get("messages", [])
            title = chat.get("title", "Chat")
            # Extract key points from the chat
            user_msgs = [m for m in messages if m.get("role") == "user"]
            assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
            summary = f"'{title}': {len(user_msgs)} questions, {len(assistant_msgs)} responses"
            if user_msgs:
                first_q = user_msgs[0].get("content", "")[:80]
                summary += f". First question: {first_q}"
            refs.append(summary)
        if refs:
            reference_block = "Related past conversations:\n" + "\n".join(refs) + "\n\n"

    if req.use_rag:
        # Extract unique source file names for document awareness
        unique_sources = set()
        for d in retrieved:
            src = d.metadata.get("source", "")
            if src:
                # Extract just the filename from the path
                unique_sources.add(Path(src).name)
        
        sources_summary = ""
        if data_files:
            sources_summary = f"Files in your data folder: {', '.join(data_files)}\n\n"
            if no_text_files:
                sources_summary += (
                    "Note: These files have little or no extractable text and may require OCR: "
                    f"{', '.join(no_text_files)}\n\n"
                )
        elif all_sources:
            sources_summary = f"All indexed documents in your knowledge base: {', '.join(all_sources)}\n\n"
        elif unique_sources:
            sources_summary = f"Available documents in your knowledge base: {', '.join(sorted(unique_sources))}\n\n"
        
        prompt = (
            "You are a helpful assistant with access to the user's personal knowledge base.\n"
            "Use the following retrieved context to answer the question. Answer naturally and conversationally.\n"
            "If the context contains relevant information, synthesize it into a clear answer.\n"
            "If the user asks what documents or data exist, list the files from the data folder list.\n"
            "If the user asks for a brief overview of the data store, mention each file; if a file has no extractable text, say it appears to be image-based or needs OCR.\n"
            "Only say 'I don't know' if the context is completely unrelated to the question.\n\n"
            + sources_summary
            + reference_block
            + history_block
            + "Context:\n"
            + "\n\n".join(context_pieces)
            + f"\n\nQuestion: {req.query}\nAnswer:"
        )
    else:
        prompt = (
            "You are a helpful assistant. Answer the user's question naturally and conversationally.\n"
            "If unsure, say you don't know.\n\n"
            + reference_block
            + history_block
            + f"Question: {req.query}\nAnswer:"
        )

    llm_options = {}
    if req.temperature is not None:
        llm_options["temperature"] = req.temperature
    if req.top_p is not None:
        llm_options["top_p"] = req.top_p
    if req.top_k is not None:
        llm_options["top_k"] = req.top_k
    if req.repeat_penalty is not None:
        llm_options["repeat_penalty"] = req.repeat_penalty
    if req.seed is not None:
        llm_options["seed"] = req.seed
    if req.max_tokens is not None:
        llm_options["num_predict"] = req.max_tokens
    if req.num_ctx is not None:
        llm_options["num_ctx"] = req.num_ctx
    if req.mirostat is not None:
        llm_options["mirostat"] = req.mirostat
    if req.mirostat_tau is not None:
        llm_options["mirostat_tau"] = req.mirostat_tau
    if req.mirostat_eta is not None:
        llm_options["mirostat_eta"] = req.mirostat_eta
    if req.stop:
        llm_options["stop"] = req.stop

    try:
        answer = predict_with_ollama(prompt, model_id=OLLAMA_MODEL, options=llm_options or None)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return QueryResponse(answer=answer, sources=sources)


@app.post("/reindex")
def reindex(background: BackgroundTasks, request: Request):
    _require_token(request)
    global vector_store

    def _do_reindex():
        global vector_store
        vector_store = build_index(DATA_DIR, CHROMA_DIR)

    background.add_task(_do_reindex)
    return JSONResponse({"status": "reindex_started"})


@app.get("/chats")
def list_chat_sessions(request: Request):
    _require_token(request)
    try:
        chats = list_chats()
        logger.info(f"Returning {len(chats)} chats from {CHATS_DIR}")
        # Ensure each chat has required fields for ChatSession
        result = []
        for chat in chats:
            result.append({
                "id": chat.get("id"),
                "title": chat.get("title", "Chat"),
                "messages": chat.get("messages", []),
                "updated_at": chat.get("updated_at")
            })
        return result
    except Exception as e:
        logger.error(f"Error listing chats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chats")
def create_chat_session(payload: ChatCreate | None = None, request: Request = None):
    try:
        if request:
            _require_token(request)
        if payload:
            data = payload.dict()
            result = create_chat(title=data.get("title"), messages=data.get("messages"))
        else:
            result = create_chat()
        logger.info(f"Created chat {result['id']}")
        return result
    except Exception as e:
        logger.error(f"Error creating chat: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/chats/{chat_id}", response_model=ChatSession)
def get_chat_session(chat_id: str, request: Request):
    _require_token(request)
    chat = get_chat(chat_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


@app.put("/chats/{chat_id}", response_model=ChatSession)
def update_chat_session(chat_id: str, session: ChatSession, request: Request):
    _require_token(request)
    data = session.dict()
    data["id"] = chat_id
    return save_chat(data)


@app.delete("/chats/{chat_id}")
def delete_chat_session(chat_id: str, request: Request):
    _require_token(request)
    ok = delete_chat(chat_id)
    return {"deleted": ok}


@app.get("/sources")
def sources(request: Request):
    _require_token(request)
    docs = load_local_documents(DATA_DIR)
    return [d.metadata.get("source") for d in docs]


@app.get("/health")
def health():
    ok = True
    msg = "ok"
    try:
        # quick check: ensure vector_store exists and ollama is callable (no heavy ops)
        if vector_store is None:
            ok = False
            msg = "vector_store_not_loaded"
    except Exception as e:
        ok = False
        msg = str(e)
    return {"ok": ok, "msg": msg}
