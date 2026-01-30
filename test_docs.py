#!/usr/bin/env python3
from app.indexer import load_local_documents

docs = load_local_documents()
print(f"Found {len(docs)} documents")
for doc in docs:
    chars = len(doc.page_content)
    source = doc.metadata.get("source", "unknown")
    print(f"{source}: {chars} chars, preview: {doc.page_content[:100]}")
