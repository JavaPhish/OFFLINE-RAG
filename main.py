import bs4
from langchain.agents import AgentState, create_agent
from langchain_community.document_loaders import WebBaseLoader
from langchain.messages import MessageLikeRepresentation
from langchain.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma  # Import Chroma
from sentence_transformers import SentenceTransformer  # Import SentenceTransformer
import subprocess

# Load and chunk contents of the blog
loader = WebBaseLoader(
    web_paths=("https://lilianweng.github.io/posts/2023-06-23-agent/",),
    bs_kwargs=dict(
        parse_only=bs4.SoupStrainer(
            class_=("post-content", "post-title", "post-header")
        )
    ),
)
docs = loader.load()

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
all_splits = text_splitter.split_documents(docs)

# Initialize vector_store
model_name = "all-MiniLM-L6-v2"  # A smaller, fast model - good for offline use. Experiment with others
embed_model = SentenceTransformer(model_name)  # Load the Sentence Transformer model


# Embeddings adapter for Chroma
class SentenceTransformerEmbeddings:
    def __init__(self, model: SentenceTransformer):
        self.model = model

    def embed_documents(self, texts):
        return [list(vec) for vec in self.model.encode(texts, show_progress_bar=False)]

    def embed_query(self, text):
        vec = self.model.encode([text], show_progress_bar=False)
        return list(vec[0])


embeddings_adapter = SentenceTransformerEmbeddings(embed_model)

# Initialize vector_store with embeddings
vector_store = Chroma.from_documents(
    documents=all_splits,
    embedding=embeddings_adapter,
    persist_directory="./chroma_db",
)

# Construct a tool for retrieving context
@tool(response_format="content_and_artifact")
def retrieve_context(query: str):
    """Retrieve information to help answer a query."""
    retrieved_docs = vector_store.similarity_search(query, k=2)
    serialized = "\n\n".join(
        (f"Source: {doc.metadata}\nContent: {doc.page_content}")
        for doc in retrieved_docs
    )
    return serialized, retrieved_docs

tools = [retrieve_context]

# If desired, specify custom instructions
prompt = (
    "You have access to a tool that retrieves context from a blog post. "
    "Use the tool to help answer user queries."
)


def call_ollama_with_prompt(model_id: str, prompt_text: str) -> str:
    try:
        proc = subprocess.run(
            ["ollama", "predict", model_id, "--prompt", prompt_text],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        raise RuntimeError("'ollama' CLI not found. Install Ollama and ensure it's on PATH.")
    return proc.stdout.strip() or proc.stderr.strip()


# Simple demo flow: retrieve context and call local Ollama model
OLLAMA_MODEL_ID = "registry.ollama.ai/library/gemma3:12b"


query = "What is task decomposition?"

# Retrieve top-k chunks from Chroma
retrieved = vector_store.similarity_search(query, k=3)

print("\n--- RETRIEVED ---\n")
for i, d in enumerate(retrieved, start=1):
    src = d.metadata.get("source")
    snippet = (d.page_content or "").strip().replace("\n", " ")[:800]
    print(f"[{i}] Source: {src}\n{snippet}\n{'-'*60}")

context = "\n\n".join(f"Source: {d.metadata.get('source')}\n{d.page_content}" for d in retrieved)

prompt_text = (
    "Use the following retrieved context to answer the question. If the answer is not contained, say you don't know.\n\n"
    f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
)

print("\n--- CALLING OLLAMA ---\n")
resp = call_ollama_with_prompt(OLLAMA_MODEL_ID, prompt_text)
print(resp)
