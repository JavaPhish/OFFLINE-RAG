#!/usr/bin/env python3
from pypdf import PdfReader

pdf_path = r"D:\private_rag_llm\data\michael-hampton-figure-drawing-design-and-invention-1.pdf"
reader = PdfReader(pdf_path)
print(f"Total pages: {len(reader.pages)}")
print(f"First 3 pages content:")
for i, page in enumerate(reader.pages[:3]):
    text = page.extract_text() or ""
    print(f"\nPage {i+1}: {len(text)} chars")
    print(text[:200])
