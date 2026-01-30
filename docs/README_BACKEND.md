# Backend — Local RAG API (FastAPI)

A production-ready FastAPI backend for retrieval-augmented generation (RAG) with:
- Automatic document ingestion (PDF, TXT, MD, HTML)
- Vector store persistence (Chroma with SQLite)
- Change detection for automatic re-indexing
- Ollama integration (CLI + HTTP API with fallbacks)
- Chat session management with server-side persistence
- Advanced LLM parameter controls

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure (Optional)

Edit `app/config.py` or set environment variables:
```bash
export RAG_DATA_DIR=./data
export RAG_CHROMA_DIR=./chroma_db
export RAG_OLLAMA_MODEL=gemma3:12b
export RAG_API_TOKEN=your-secret-token
```

### 3. Start Ollama

In a separate terminal:
```bash
ollama serve
```

Then ensure a model is available:
```bash
ollama pull gemma3:12b
```

### 4. Run the Backend

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Or with auto-reload during development:
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API will be available at `http://127.0.0.1:8000`

### 5. Test the API

```bash
curl -X POST http://127.0.0.1:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is in my data folder?", "k": 3}'
```

## API Endpoints

### `POST /query`
Execute a RAG query with optional history and cross-chat references.

**Request:**
```json
{
  "query": "What files do I have?",
  "k": 3,
  "use_rag": true,
  "reference_chats": ["chat-id-1", "chat-id-2"],
  "history": [
    {"role": "user", "content": "Previous question..."},
    {"role": "assistant", "content": "Previous answer..."}
  ],
  "temperature": 0.7,
  "top_p": 0.9,
  "top_k": 40,
  "repeat_penalty": 1.1,
  "seed": null,
  "max_tokens": 512,
  "num_ctx": 4096,
  "mirostat": 0,
  "mirostat_tau": 5.0,
  "mirostat_eta": 0.1,
  "stop": ["User:", "Assistant:"]
}
```

**Response:**
```json
{
  "answer": "You have Calculus_Made_Easy.pdf and Lease_Document.pdf...",
  "sources": [
    {
      "source": "/path/to/Calculus_Made_Easy.pdf",
      "snippet": "This is a reproduction of a library book..."
    },
    {
      "source": "/path/to/Lease_Document.pdf",
      "snippet": "Florida Lease Agreement Rev 2/2025..."
    }
  ]
}
```

### `GET /chats`
List all chat sessions.

```json
[
  {
    "id": "chat-123",
    "title": "Project Overview",
    "messages": [...],
    "updated_at": "2026-01-30T10:30:00"
  }
]
```

### `POST /chats`
Create a new chat session.

```json
{
  "id": "chat-456",
  "title": "New chat",
  "messages": [],
  "updated_at": "2026-01-30T10:35:00"
}
```

### `GET /chats/{chat_id}`
Retrieve a specific chat.

### `PUT /chats/{chat_id}`
Update a chat (save messages).

```json
{
  "id": "chat-123",
  "title": "Updated Title",
  "messages": [...]
}
```

### `DELETE /chats/{chat_id}`
Delete a chat session.

### `GET /chats/summary/{chat_id}`
Get a brief summary of a chat for cross-referencing.

```json
{
  "id": "chat-123",
  "title": "Project Overview",
  "first_question": "What is the project scope?",
  "message_count": 8
}
```

### `POST /reindex`
Force a rebuild of the vector store from source documents.

```json
{"status": "reindex_started"}
```

### `GET /health`
Health check endpoint.

```json
{"status": "ok"}
```

## Configuration

### `app/config.py`

```python
from pathlib import Path

# Data and storage directories
DATA_DIR = Path("./data")                    # Where to read documents
CHROMA_DIR = Path("./chroma_db")             # Where to persist vector store
CHATS_DIR = Path("./chat_store")             # Where to persist chat sessions

# Vector store settings
CHUNK_SIZE = 1000                            # Characters per chunk
CHUNK_OVERLAP = 200                          # Overlap between chunks
MODEL_NAME = "all-MiniLM-L6-v2"             # SentenceTransformer embedding model

# LLM settings
OLLAMA_MODEL = "gemma3:12b"                  # Ollama model name

# API security (optional)
API_TOKEN = None                             # Set to require Bearer token
```

### Environment Variables (Optional)

```bash
RAG_DATA_DIR=./my_documents
RAG_CHROMA_DIR=./my_vectors
RAG_OLLAMA_MODEL=llama2
RAG_API_TOKEN=my-secret-key
```

## Core Modules

### `app/main.py`
FastAPI application with RAG query endpoint and chat management.

**Key functions:**
- `query()` — Process RAG queries with history and references
- `_ensure_index_up_to_date()` — Auto-rebuild vector store if files changed
- `list_chat_sessions()` / `create_chat_session()` / `update_chat_session()` / `delete_chat_session()` — Chat CRUD
- `get_chat_summary()` — Summarize a chat for cross-referencing

### `app/indexer.py`
Document loading, chunking, embedding, and vector store management.

**Key functions:**
- `load_local_documents()` — Read PDFs, TXT, MD, HTML from `DATA_DIR`
- `_split_documents()` — Split documents into chunks using `RecursiveCharacterTextSplitter`
- `build_index()` — Create and persist vector store via Chroma
- `load_or_build()` — Load existing DB or rebuild if needed
- `needs_reindex()` — Check if source files have changed (via manifest hash)

### `app/ollama.py`
Robust Ollama invocation with CLI and HTTP API support.

**Key functions:**
- `_detect_ollama_commands()` — Parse `ollama --help` to detect available commands
- `predict_with_ollama()` — Call Ollama with fallback strategies (positional args → flags → stdin → HTTP API)
- `_ollama_http_generate()` — HTTP API fallback with advanced options

### `app/chat_store.py`
Chat session persistence to JSON files.

**Key functions:**
- `list_chats()` — List all chats from `CHATS_DIR`
- `get_chat()` / `save_chat()` / `delete_chat()` / `create_chat()` — Chat CRUD

### `app/schemas.py`
Pydantic models for request/response validation.

**Models:**
- `QueryRequest` — RAG query with LLM parameters
- `QueryResponse` — Answer + sources
- `QuerySource` — Document source and snippet
- `ChatSession` — Chat with messages
- `ChatCreate` — Create chat request

## Document Ingestion Pipeline

1. **Load** — Read files from `DATA_DIR` (supported: PDF, TXT, MD, HTML)
   - PDF: Extract text using `pypdf`; skip if <100 chars (likely image-based)
   - TXT/MD/HTML: Read as plain text

2. **Split** — Chunk documents into 1000-character segments with 200-character overlap
   - Uses `RecursiveCharacterTextSplitter` from LangChain

3. **Embed** — Convert each chunk to a vector using `SentenceTransformer` (all-MiniLM-L6-v2)
   - Local embeddings; no API calls

4. **Store** — Persist vectors and metadata to Chroma (SQLite backend)
   - Location: `./chroma_db/`

5. **Detect Changes** — Track file hashes in `./chat_store/manifest.json`
   - Rebuild if files change or manifest is missing

## RAG Query Flow

```
User Query
    ↓
Ensure Index Up-to-Date (check file changes)
    ↓
Retrieve Top-K Similar Chunks (vector similarity search)
    ↓
Format Context Block
    ├─ Document list (all indexed files)
    ├─ Retrieved chunks
    ├─ Chat history (last 8 turns)
    └─ Referenced past chats (summaries)
    ↓
Build Prompt
    ├─ System instruction
    ├─ Context block
    └─ User query
    ↓
Call Ollama LLM (with optional parameters)
    ↓
Stream/Return Answer + Sources
```

## Ollama Integration

The system supports multiple Ollama invocation methods for maximum compatibility:

1. **CLI Positional** — `ollama run model "prompt"`
2. **CLI Flags** — `ollama run model --system "..." --temperature 0.7`
3. **CLI Stdin** — `echo "prompt" | ollama run model`
4. **HTTP API** — POST to `/api/generate` with streaming

The `predict_with_ollama()` function tries each method in order until one succeeds.

### Supported Models
- `gemma3:12b` — 12B parameter model (good balance)
- `phi:2b` — 2B parameter model (fast)
- `llama2` — 7B parameter model (good quality)
- Any model available via `ollama pull <model>`

## Change Detection & Re-indexing

The system automatically re-indexes when:
- Files are added/removed from `./data/`
- File modification times change
- Vector store is missing
- Manifest is missing

Manual re-indexing:
```bash
# Delete and restart
rm -rf ./chroma_db
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Or call the API
curl -X POST http://127.0.0.1:8000/reindex
```

## Performance Tips

- **Embedding Model** — `all-MiniLM-L6-v2` is fast and accurate
- **Chunk Size** — 1000 chars is a good default; increase for longer documents
- **Ollama Model** — Smaller models (2B–7B) are faster; larger (12B+) are more accurate
- **RAG Toggle** — Disable RAG for faster pure-LLM responses
- **Top-K** — Fewer chunks = faster retrieval; start with 3–5

## Troubleshooting

### Backend won't start
- Check Python version: `python --version` (need 3.10+)
- Install dependencies: `pip install -r requirements.txt`
- Verify Ollama is running: `ollama serve` in another terminal

### Vector store has old data
```bash
rm -rf ./chroma_db
# Restart backend to trigger rebuild
```

### Ollama not responding
- Ensure Ollama is running: `ollama serve`
- Check model is available: `ollama list`
- Pull a model if needed: `ollama pull gemma3:12b`

### PDF extraction fails
- Check if PDF is text-based or scanned (scanned PDFs don't extract text)
- Try converting with a PDF tool or OCR service
- System automatically skips PDFs with <100 characters of text

### API token not working
- Set `API_TOKEN` in `app/config.py`
- Pass `Authorization: Bearer <token>` header in requests

## Frontend Setup

The React frontend is in `./frontend/`. See [Frontend README](README_FRONTEND.md) for setup.

## Next Steps

- [ ] Add file upload UI
- [ ] Implement background file watcher
- [ ] Add hybrid search (BM25 + semantic)
- [ ] Support multi-user with auth
- [ ] Deploy with Docker
- [ ] Add OCR for scanned PDFs

---

For full project setup, see [Main README](../README.md).
