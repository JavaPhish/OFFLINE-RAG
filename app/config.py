from pathlib import Path
import os

# Paths and defaults
ROOT = Path(__file__).parent.parent
DATA_DIR = Path(os.getenv("RAG_DATA_DIR", ROOT / "data"))
CHROMA_DIR = Path(os.getenv("RAG_CHROMA_DIR", ROOT / "chroma_db"))
CHATS_DIR = Path(os.getenv("RAG_CHATS_DIR", ROOT / "chat_store"))
MODEL_NAME = os.getenv("RAG_EMBEDDING_MODEL", "all-MiniLM-L6-v2")
OLLAMA_MODEL = os.getenv("RAG_OLLAMA_MODEL", "registry.ollama.ai/library/gemma3:12b")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
MANIFEST_PATH = CHROMA_DIR / "manifest.json"

# Simple security token (optional)
API_TOKEN = os.getenv("RAG_API_TOKEN", None)

# Splitter settings
CHUNK_SIZE = int(os.getenv("RAG_CHUNK_SIZE", 1000))
CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", 200))
