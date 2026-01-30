#!/usr/bin/env python3
from app.indexer import load_or_build
from app.config import DATA_DIR, CHROMA_DIR

vs = load_or_build(DATA_DIR, CHROMA_DIR)

# Get the collection and count documents
collection = vs._collection
print(f"Total chunks in vector store: {collection.count()}")

# Try to get a sample of what sources are in there
all_docs = collection.get(include=["metadatas"])
sources = set()
for meta in all_docs.get("metadatas", []):
    sources.add(meta.get("source", "unknown"))

print(f"\nUnique sources indexed:")
for source in sorted(sources):
    count = sum(1 for m in all_docs["metadatas"] if m.get("source") == source)
    print(f"  {source}: {count} chunks")
