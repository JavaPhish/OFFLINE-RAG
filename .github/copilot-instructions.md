# Copilot / AI agent instructions — private_rag_llm

Purpose: quickly orient an AI coding agent to the project's architecture, conventions, and developer workflows so changes are focused and low-risk.

1. Big picture
- Single-script RAG demo in `main.py`: pipeline is WebBaseLoader (HTML) -> `RecursiveCharacterTextSplitter` -> SentenceTransformer embeddings -> Chroma vector store persisted to `./chroma_db` -> LangChain agent created with `create_agent` and a small retrieval tool.
- Data persistence: `chroma_db/chroma.sqlite3` holds the vector DB; the code uses `persist_directory="./chroma_db"`.

2. Key files to inspect
- `main.py` — only entry point and canonical example for adding loaders, splitters, and tools.
- `chroma_db/` — contains the persisted Chroma DB; remove to rebuild from scratch.

3. Important patterns & conventions (copy/paste examples)
- Vector DB creation:

```py
vector_store = Chroma.from_documents(
    documents=all_splits,
    persist_directory="./chroma_db",
)
```

- Embedding model default: `model_name = "all-MiniLM-L6-v2"`. To change embeddings, update `model_name` and (if needed) pass an embedding function to Chroma.
- Text splitting: `RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)` — keep similar chunk sizes when adding new sources.
- Tool shape: tools are plain callables exposed to the agent. The example tool returns both serialized content and the raw retrieved docs:

```py
@tool(response_format="content_and_artifact")
def retrieve_context(query: str):
    retrieved_docs = vector_store.similarity_search(query, k=2)
    return serialized, retrieved_docs
```

- Agent usage: the repo uses `agent.stream(..., stream_mode="values")` and calls `.pretty_print()` on the last message.

4. Developer workflows
- Install (use the imports in `main.py` to construct the environment):

```bash
pip install beautifulsoup4 langchain langchain-community langchain-text-splitters sentence-transformers chromadb
```

- Run the demo:

```bash
python main.py
```

- Rebuild vector DB: delete the `chroma_db/` folder (or `chroma_db/chroma.sqlite3`) and re-run `main.py`.
- Inspect DB: open `chroma_db/chroma.sqlite3` with any SQLite browser to verify persisted tables.

5. Integration points & external dependencies
- Web scraping: `langchain_community.document_loaders.WebBaseLoader` — check `bs_kwargs` in `main.py` when adding new pages.
- Embeddings: `sentence_transformers.SentenceTransformer` used directly; changing to a remote embedding service will require adapting the `sentence_transform_embeddings` function or passing an embeddings object to `Chroma.from_documents`.
- Vector store: `langchain_community.vectorstores.Chroma` persists locally to `./chroma_db`.

6. When making changes
- Keep PRs small and focused: update only one integration at a time (loader, splitter, embedding, or vectorstore).
- Preserve `persist_directory` unless you intentionally change DB location; document migration steps if you do.
- If adding new tools, follow the `retrieve_context` pattern and ensure return types match callers.

7. Missing/unknowns (what to ask the repo owner)
- No `requirements.txt` or CI detected — ask if there's a preferred environment or pinned dependency versions.
- Confirm whether `sentence_transform_embeddings` should be passed to Chroma (it's defined in `main.py` but not wired through `from_documents`).

If anything here is unclear or you'd like me to add examples for changing the embedding or vectorstore code paths, tell me which part to expand.
