"""H6 — handbook Q&A. ChromaDB + Gemini embeddings (transformers ka koi zikr nahi)."""
from app.core import embeddings
from app.core.llm import llm_text
from app.database import db_session
from app.models import PolicyDoc
from app.tools.resume_tools import extract_text

ANSWER_PROMPT = """Answer the employee's question using ONLY the handbook sections below.
If the answer is not in them, say "Handbook mein yeh nahi likha — HR se confirm karein."
Always quote the exact sentence you relied on, in a > blockquote.

QUESTION: {question}

HANDBOOK SECTIONS:
{context}
"""


def index_handbook(file_path: str, filename: str, workspace_id: str | None = None) -> dict:
    text = extract_text(file_path)
    chunks = embeddings.chunk_text(text)
    db = db_session()
    try:
        doc = PolicyDoc(filename=filename, path=file_path,
                        workspace_id=workspace_id, chunks=len(chunks))
        db.add(doc)
        db.commit()
        db.refresh(doc)
        embeddings.add_documents(chunks, doc.id, filename)
        return {"doc_id": doc.id, "chunks": len(chunks)}
    finally:
        db.close()


def ask_policy(question: str, k: int = 3) -> dict:
    hits = embeddings.query(question, k=k)
    if not hits:
        return {"answer": "Abhi koi handbook upload nahi hui.", "sources": []}
    ctx = "\n\n---\n\n".join(f"[{h['meta']['source']} #{h['meta']['chunk']}]\n{h['text']}" for h in hits)
    answer = llm_text(ANSWER_PROMPT.format(question=question, context=ctx), temperature=0.2)
    return {"answer": answer,
            "sources": [{"source": h["meta"]["source"], "chunk": h["meta"]["chunk"]} for h in hits]}
