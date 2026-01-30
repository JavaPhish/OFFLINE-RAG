"""Offline RAG example (local-only)

Requirements:
- Ollama installed locally and at least one local model pulled (see README notes below).
- Python packages in `requirements.txt`.

This script:
- Loads local documents from `./data/` (.txt/.md/.html)
- Splits into chunks with `RecursiveCharacterTextSplitter`
- Embeds using `SentenceTransformer` (local)
- Persists/loads a Chroma DB at `./chroma_db`
- Uses local Ollama CLI (`ollama predict`) to generate an answer using retrieved context

Notes:
- This calls the `ollama` CLI on the host — no external APIs are used.
"""

from pathlib import Path
import subprocess
import argparse
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma

# Prefer langchain's Document if available, otherwise use a minimal fallback.
try:
    from langchain.schema import Document  # type: ignore
except Exception:
    from dataclasses import dataclass
    from typing import Dict, Any

    @dataclass
    class Document:
        page_content: str
        metadata: Dict[str, Any]

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
MODEL_NAME = "all-MiniLM-L6-v2"
# If Ollama installed models under the registry path, use the registry identifier.
# Your install path suggests the registry ID: registry.ollama.ai/library/gemma3:12b
OLLAMA_MODEL = "registry.ollama.ai/library/gemma3:12b"  # set to your local Ollama model identifier


def load_local_documents(data_dir: Path):
    docs = []
    for p in sorted(data_dir.rglob("*")):
        if not p.is_file():
            continue

        suffix = p.suffix.lower()
        # Text/Markdown/HTML
        if suffix in (".txt", ".md", ".html"):
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:
                text = p.read_text(encoding="latin-1")
            docs.append(Document(page_content=text, metadata={"source": str(p)}))
        # PDFs: use pypdf if available
        elif suffix == ".pdf":
            try:
                from pypdf import PdfReader  # type: ignore

                reader = PdfReader(str(p))
                pages = []
                for page in reader.pages:
                    try:
                        pages.append(page.extract_text() or "")
                    except Exception:
                        pages.append("")
                text = "\n\n".join(pages)
            except Exception as e:
                text = f"[Failed to extract PDF {p}: {e}]"
            docs.append(Document(page_content=text, metadata={"source": str(p)}))
    return docs


def sentence_transform_embeddings(texts):
    return model.encode(texts)


class SentenceTransformerEmbeddings:
    """Adapter to provide embed_documents/embed_query for langchain-community Chroma."""

    def __init__(self, model: SentenceTransformer):
        self.model = model

    def embed_documents(self, texts):
        # Accept list[str] and return list[list[float]] with native Python floats
        arr = self.model.encode(texts, show_progress_bar=False)
        return [vec.tolist() for vec in arr]

    def embed_query(self, text):
        vec = self.model.encode([text], show_progress_bar=False)
        return vec[0].tolist()


if __name__ == "__main__":
    # 1) Load embedding model (local)
    model = SentenceTransformer(MODEL_NAME)

    # 2) Load local docs
    raw_docs = load_local_documents(DATA_DIR)
    if not raw_docs:
        print("No documents found in ./data/. Add .txt/.md/.html files and re-run.")
        raise SystemExit(1)

    # 3) Split
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    all_splits = text_splitter.split_documents(raw_docs)

    # 4) Build or load Chroma DB (local)
    embeddings_adapter = SentenceTransformerEmbeddings(model)
    vector_store = Chroma.from_documents(
        documents=all_splits,
        embedding=embeddings_adapter,
        persist_directory="./chroma_db",
    )

    # Attempt to verify the Ollama model exists locally; if not, try to auto-detect a "gemma" model.
    try:
        list_proc = subprocess.run(["ollama", "list"], capture_output=True, text=True, check=False)
        list_out = (list_proc.stdout or list_proc.stderr or "").lower()
        if OLLAMA_MODEL.lower() not in list_out:
            # look for a model name containing 'gemma' as a fallback
            for line in list_out.splitlines():
                if "gemma" in line:
                    # try to extract the first token as the model id
                    candidate = line.strip().split()[0]
                    if candidate:
                        print(f"Autodetected Ollama model: {candidate}")
                        OLLAMA_MODEL = candidate
                        break
    except FileNotFoundError:
        # Ollama not on PATH; we'll catch this later when invoking predict
        pass

    parser = argparse.ArgumentParser(description="Offline RAG demo using local Ollama model")
    parser.add_argument("--k", type=int, default=3, help="number of retrieved chunks")
    parser.add_argument("--show-embeddings", action="store_true", help="print raw embedding vectors (debug)")
    args = parser.parse_args()

    # 5) Query loop
    while True:
        query = input("Query (or 'exit'): ").strip()
        if not query or query.lower() in ("exit", "quit"):
            break

        retrieved = vector_store.similarity_search(query, k=args.k)

        # Pretty-print retrieved sources (don't print raw vectors)
        print("\n--- RETRIEVED ---\n")
        context_pieces = []
        for i, d in enumerate(retrieved, start=1):
            src = d.metadata.get("source")
            snippet = (d.page_content or "").strip().replace("\n", " ")[:800]
            print(f"[{i}] Source: {src}\n{snippet}\n{'-'*60}")
            context_pieces.append(f"Source: {src}\n{d.page_content}")

        if args.show_embeddings:
            try:
                # If the vectorstore exposes an _embedding_function, we can call it for debug
                emb_func = getattr(vector_store, "_embedding_function", None)
                if emb_func and hasattr(emb_func, "embed_documents"):
                    texts = [d.page_content for d in retrieved]
                    emb_vals = emb_func.embed_documents(texts)
                    print("\n--- EMBEDDINGS (debug) ---\n")
                    for vec in emb_vals:
                        print(vec)
                else:
                    print("Embeddings adapter not available for debug output.")
            except Exception as e:
                print(f"Failed to print embeddings: {e}")

        context = "\n\n".join(context_pieces)

        prompt = (
            "Use the following retrieved context to answer the question. If the answer is not contained, reply 'I don't know'.\n"
            "Do NOT repeat the context verbatim; answer concisely and cite sources only when necessary.\n\n"
            f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
        )

        # 6) Call Ollama CLI locally (no external network) using the robust wrapper
        try:
            # Use the resilient wrapper which tries `predict`, `run`, `generate`, and stdin/flag fallbacks
            from app.ollama import predict_with_ollama
            output = predict_with_ollama(prompt, model_id=OLLAMA_MODEL)
        except RuntimeError as e:
            print(f"Ollama call failed: {e}")
            raise
        except FileNotFoundError:
            print("'ollama' CLI not found. Install Ollama and ensure it's on PATH.")
            raise

        print("\n--- MODEL RESPONSE ---\n")
        print(output)
        print("\n----------------------\n")
