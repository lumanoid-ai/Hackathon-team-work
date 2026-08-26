"""Embeddings BINA transformers ke.

Gemini ka embedding endpoint (free tier) + ChromaDB (local, free).
Koi torch / sentence-transformers install nahi hota.

NOTE: Chroma ko embedding_function pass NAHI karte — vectors khud bana ke
seedha bhejte hain. Isse code chromadb 0.5 aur 1.x dono pe chalta hai,
aur Chroma ke internal EmbeddingFunction interface badalne se kuch nahi tootta.
"""
from typing import Sequence

import chromadb
import google.generativeai as genai

from app.config import settings

_client = None
_configured = False


def _ensure():
    global _configured
    if not _configured:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _configured = True


def embed_texts(texts: Sequence[str], task_type: str = "retrieval_document") -> list[list[float]]:
    """Google text-embedding-004 -> 768-dim vectors. Free tier."""
    _ensure()
    out: list[list[float]] = []
    for t in texts:
        res = genai.embed_content(
            model=settings.GEMINI_EMBED_MODEL,
            content=t[:8000],
            task_type=task_type,
        )
        out.append(res["embedding"])
    return out


def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=settings.CHROMA_DIR)
    return _client


def get_collection(name: str = "policy"):
    return get_client().get_or_create_collection(name=name)


def chunk_text(text: str, words_per_chunk: int = 400, overlap: int = 60) -> list[str]:
    words = text.split()
    chunks, i = [], 0
    while i < len(words):
        chunks.append(" ".join(words[i: i + words_per_chunk]))
        i += words_per_chunk - overlap
    return [c for c in chunks if c.strip()]


def add_documents(chunks: Sequence[str], doc_id: str, source: str,
                  collection_name: str = "policy") -> int:
    col = get_collection(collection_name)
    vectors = embed_texts(chunks, task_type="retrieval_document")
    col.add(
        ids=[f"{doc_id}_{i}" for i in range(len(chunks))],
        documents=list(chunks),
        embeddings=vectors,
        metadatas=[{"doc_id": doc_id, "source": source, "chunk": i} for i in range(len(chunks))],
    )
    return len(chunks)


def query(question: str, k: int = 3, collection_name: str = "policy") -> list[dict]:
    col = get_collection(collection_name)
    if col.count() == 0:
        return []
    qvec = embed_texts([question], task_type="retrieval_query")[0]
    res = col.query(query_embeddings=[qvec], n_results=min(k, col.count()))
    return [
        {"text": d, "meta": m, "distance": dist}
        for d, m, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])
    ]
