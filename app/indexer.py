import json
from pathlib import Path
from typing import List
from .config import DATA_DIR, CHROMA_DIR, MODEL_NAME, MANIFEST_PATH, CHUNK_SIZE, CHUNK_OVERLAP
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma

# Prefer pypdf if available
try:
    from pypdf import PdfReader  # type: ignore
except Exception:
    PdfReader = None


class Document:
    def __init__(self, page_content: str, metadata: dict):
        self.page_content = page_content
        self.metadata = metadata


def load_local_documents(data_dir: Path = DATA_DIR) -> List[Document]:
    docs = []
    for p in sorted(Path(data_dir).rglob("*")):
        if not p.is_file():
            continue
        suffix = p.suffix.lower()
        if suffix in (".txt", ".md", ".html"):
            try:
                text = p.read_text(encoding="utf-8")
            except Exception:
                text = p.read_text(encoding="latin-1")
            docs.append(Document(page_content=text, metadata={"source": str(p)}))
        elif suffix == ".pdf":
            if PdfReader:
                try:
                    reader = PdfReader(str(p))
                    pages = []
                    for page in reader.pages:
                        pages.append(page.extract_text() or "")
                    text = "\n\n".join(pages)
                    # Skip PDFs that have no extractable text (scanned images, etc.)
                    if len(text.strip()) < 100:
                        print(f"Skipping {p.name}: insufficient text ({len(text)} chars)")
                        continue
                except Exception as e:
                    text = f"[Failed to extract PDF {p}: {e}]"
            else:
                text = f"[pypdf not installed; cannot extract PDF {p}]"
            docs.append(Document(page_content=text, metadata={"source": str(p)}))
    return docs


def _split_documents(docs: List[Document]):
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)
    # Our lightweight Document already exposes `page_content` and `metadata` attributes
    # Pass the objects directly to the splitter (it requires objects with .page_content)
    return text_splitter.split_documents(docs)


class SentenceTransformerEmbeddings:
    def __init__(self, model_name: str = MODEL_NAME):
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts):
        # Ensure we return plain Python floats (no numpy.float32 objects)
        arr = self.model.encode(texts, show_progress_bar=False)
        return [vec.tolist() for vec in arr]

    def embed_query(self, text):
        vec = self.model.encode([text], show_progress_bar=False)
        return vec[0].tolist()


def _read_manifest() -> dict:
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _write_manifest(manifest: dict):
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f)


def _compute_manifest_from_files(data_dir: Path = DATA_DIR) -> dict:
    manifest = {}
    for p in sorted(Path(data_dir).rglob("*")):
        if not p.is_file():
            continue
        manifest[str(p)] = int(p.stat().st_mtime)
    return manifest


def needs_reindex(data_dir: Path = DATA_DIR) -> bool:
    old = _read_manifest()
    new = _compute_manifest_from_files(data_dir)
    return old != new


def build_index(data_dir: Path = DATA_DIR, persist_directory: Path = CHROMA_DIR):
    """Rebuild the entire vector DB from all files in data_dir."""
    docs = load_local_documents(data_dir)
    if not docs:
        raise RuntimeError("No documents found to index. Add files in ./data/ and try again.")
    splits = _split_documents(docs)
    embeddings = SentenceTransformerEmbeddings()
    # Recreate the DB (from_documents will write to persist_directory)
    vector_store = Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        persist_directory=str(persist_directory),
    )
    # Update manifest
    manifest = _compute_manifest_from_files(data_dir)
    _write_manifest(manifest)
    return vector_store


def load_or_build(data_dir: Path = DATA_DIR, persist_directory: Path = CHROMA_DIR):
    """Load DB if exists and up-to-date; otherwise rebuild.

    Attempts multiple Chroma constructor patterns to be compatible with different
    langchain / chroma package versions. If loading fails, try to rebuild the
    index from sources so the service can recover automatically.
    """
    import logging
    logger = logging.getLogger("uvicorn")
    
    if not persist_directory.exists():
        logger.info(f"Chroma DB not found at {persist_directory}, building from scratch")
        return build_index(data_dir, persist_directory)
    
    if needs_reindex(data_dir):
        logger.info(f"Files in {data_dir} have changed, rebuilding index")
        return build_index(data_dir, persist_directory)

    embeddings = SentenceTransformerEmbeddings()

    # Try several constructor signatures for broad compatibility
    tried_errors = []
    try:
        vector_store = Chroma(persist_directory=str(persist_directory), embedding_function=embeddings)
        return vector_store
    except TypeError as e:
        tried_errors.append(e)
    except Exception as e:
        tried_errors.append(e)

    try:
        # older versions sometimes accept 'embedding' kwarg
        vector_store = Chroma(persist_directory=str(persist_directory), embedding=embeddings)
        return vector_store
    except TypeError as e:
        tried_errors.append(e)
    except Exception as e:
        tried_errors.append(e)

    try:
        # fallback: try without passing embeddings and hope existing DB contains vectors
        vector_store = Chroma(persist_directory=str(persist_directory))
        return vector_store
    except Exception as e:
        tried_errors.append(e)

    # If all loading attempts failed, attempt to rebuild the DB from source files
    try:
        return build_index(data_dir, persist_directory)
    except Exception as e:
        tried_errors.append(e)
        # If rebuild also fails, raise a combined error to surface the root causes
        raise RuntimeError(f"Failed to load or build Chroma vector store. Errors: {tried_errors}")

