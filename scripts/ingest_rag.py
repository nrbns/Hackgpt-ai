"""Ingest knowledge files into ChromaDB for RAG."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag import rag_engine

if __name__ == "__main__":
    count = rag_engine.ingest_directory()
    print(f"Ingested {count} documents into RAG index.")
