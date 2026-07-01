from __future__ import annotations

from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from app.config import settings

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"


class RAGEngine:
    def __init__(self) -> None:
        self._embedder: SentenceTransformer | None = None
        self._client: chromadb.PersistentClient | None = None
        self._collection = None
        self._cached_count: int = 0

    def _ensure_ready(self) -> None:
        if self._embedder is None:
            self._embedder = SentenceTransformer(settings.embedding_model)
        if self._client is None:
            persist = Path(settings.chroma_persist_dir)
            persist.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(persist),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name="pentest_knowledge",
                metadata={"hnsw:space": "cosine"},
            )

    def ingest_directory(self, directory: Path | None = None) -> int:
        self._ensure_ready()
        root = directory or KNOWLEDGE_DIR
        if not root.exists():
            return 0

        docs: list[str] = []
        ids: list[str] = []
        metas: list[dict] = []

        for path in sorted(root.glob("**/*")):
            if path.suffix.lower() not in {".md", ".txt", ".json"}:
                continue
            text = path.read_text(encoding="utf-8")
            if not text.strip():
                continue
            doc_id = path.stem
            docs.append(text)
            ids.append(doc_id)
            metas.append({"source": str(path.relative_to(root))})

        if not docs:
            return 0

        assert self._embedder is not None
        embeddings = self._embedder.encode(docs, show_progress_bar=False).tolist()
        assert self._collection is not None
        self._collection.upsert(ids=ids, documents=docs, embeddings=embeddings, metadatas=metas)
        self._cached_count = len(docs)
        return len(docs)

    def document_count(self) -> int:
        if self._cached_count:
            return self._cached_count
        self._ensure_ready()
        assert self._collection is not None
        count = self._collection.count()
        self._cached_count = count
        return count

    def list_sources(self) -> list[str]:
        self._ensure_ready()
        assert self._collection is not None
        if self._collection.count() == 0:
            return []
        result = self._collection.get(include=["metadatas"])
        metas = result.get("metadatas") or []
        return sorted({m.get("source", "") for m in metas if m.get("source")})

    def query(self, question: str, top_k: int = 3) -> list[str]:
        self._ensure_ready()
        assert self._embedder is not None
        assert self._collection is not None

        if self._collection.count() == 0:
            self.ingest_directory()

        if self._collection.count() == 0:
            return []

        embedding = self._embedder.encode([question], show_progress_bar=False).tolist()
        results = self._collection.query(
            query_embeddings=embedding,
            n_results=min(top_k, self._collection.count()),
        )
        documents = results.get("documents", [[]])[0]
        return [doc for doc in documents if doc]

    def build_context(self, question: str, top_k: int = 3) -> str:
        chunks = self.query(question, top_k=top_k)
        if not chunks:
            return ""
        joined = "\n\n---\n\n".join(chunks)
        return f"## Retrieved security knowledge\n\n{joined}"


rag_engine = RAGEngine()
