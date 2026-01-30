#!/usr/bin/env python3
from app.indexer import load_or_build
from app.config import DATA_DIR, CHROMA_DIR

# Load vector store 
vs = load_or_build(DATA_DIR, CHROMA_DIR)

# Try a query
results = vs.similarity_search("outline data files", k=2)
print(f"Search results: {len(results)} documents found\n")
for i, doc in enumerate(results):
    source = doc.metadata.get("source", "unknown")
    print(f"\n--- Result {i+1}: {source} ---")
    print(f"Content preview: {doc.page_content[:200]}...")
