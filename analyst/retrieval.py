"""
Schema retrieval.

On an enterprise database, sending every table's schema to the model is
not an option -- the prompt grows past what the model can use well, and
the tables that matter get lost among the ones that do not.

This picks the tables a question actually needs. Two safeguards keep it
from breaking the JOINs that make analysis possible:

  1. Below RETRIEVAL_THRESHOLD tables, retrieval is skipped entirely and
     every table is sent. Narrowing a small schema only loses information.
  2. Whatever is retrieved is expanded along foreign keys. A question that
     matches `hiring_funnel` also gets `open_reqs`, because the two are
     related and the answer almost certainly spans both.

Embeddings are used when a provider is configured. When it is not, a
keyword scorer runs instead -- less precise, no extra dependency, and the
FK expansion covers most of the difference.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from .ingest import TableProfile

# Under this many tables, send everything. Retrieval is a cost, not a win,
# on a small schema.
RETRIEVAL_THRESHOLD = int(os.environ.get("RETRIEVAL_THRESHOLD", "12"))

# How many tables to retrieve before FK expansion.
TOP_K = int(os.environ.get("RETRIEVAL_TOP_K", "6"))

# A table scoring below this fraction of the best match is dropped, even if
# it lands inside top_k. Keeps weak matches out of the prompt.
RELATIVE_CUTOFF = float(os.environ.get("RETRIEVAL_CUTOFF", "0.55"))

# Words that appear in every question and tell us nothing about which table.
STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "of", "in",
    "on", "at", "to", "for", "with", "by", "from", "as", "and", "or", "not",
    "we", "our", "us", "i", "me", "my", "you", "your", "it", "its", "this",
    "that", "these", "those", "what", "which", "who", "whom", "whose", "why",
    "how", "when", "where", "many", "much", "most", "least", "more", "less",
    "show", "give", "tell", "find", "get", "list", "count", "compare", "do",
    "does", "did", "can", "could", "should", "would", "have", "has", "had",
    "behind", "ahead", "up", "down", "out", "about", "into", "over", "all",
}


@dataclass
class RetrievalResult:
    profiles: list[TableProfile]
    used_retrieval: bool
    matched: list[str]
    added_by_fk: list[str]

    def summary(self) -> str:
        if not self.used_retrieval:
            return f"Sent all {len(self.profiles)} tables"
        parts = [f"Matched {', '.join(self.matched)}"]
        if self.added_by_fk:
            parts.append(f"pulled in {', '.join(self.added_by_fk)} via foreign keys")
        return "; ".join(parts)


# ---------------------------------------------------------------------------
# Describing a table well enough to match against
# ---------------------------------------------------------------------------


def table_document(profile: TableProfile) -> str:
    """
    The text a table is matched against.

    Column names carry most of the signal, but the values of categorical
    columns matter too: a question about 'offers' should find the table
    whose stage column contains 'Offer Extended', even though no column is
    named offer.
    """
    parts = [profile.name.replace("_", " ")]
    for col in profile.columns:
        parts.append(col.name.replace("_", " "))
        if col.values:
            parts.extend(str(v) for v in col.values[:15])
    return " ".join(parts)


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [w for w in words if w not in STOPWORDS and len(w) > 2]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def _keyword_scores(question: str, profiles: list[TableProfile]) -> dict[str, float]:
    """Overlap between question words and table words. No dependencies."""
    q = set(_tokens(question))
    scores: dict[str, float] = {}

    for profile in profiles:
        doc = set(_tokens(table_document(profile)))
        if not doc:
            scores[profile.name] = 0.0
            continue
        overlap = len(q & doc)
        # Normalise by question length so long questions do not inflate every
        # table equally.
        scores[profile.name] = overlap / max(len(q), 1)

    return scores


def _embedding_scores(
    question: str, profiles: list[TableProfile]
) -> dict[str, float] | None:
    """
    Cosine similarity via whichever embedding provider is configured.
    Returns None when none is available, so the caller falls back.
    """
    if os.environ.get("RETRIEVAL_MODE", "").lower() == "keyword":
        return None

    try:
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
    except ImportError:
        return None

    if not os.environ.get("GEMINI_API_KEY"):
        return None

    try:
        embedder = GoogleGenerativeAIEmbeddings(
            model=os.environ.get("EMBEDDING_MODEL", "models/text-embedding-004"),
            google_api_key=os.environ["GEMINI_API_KEY"],
        )
        docs = [table_document(p) for p in profiles]
        doc_vecs = embedder.embed_documents(docs)
        q_vec = embedder.embed_query(question)
    except Exception:
        return None

    def cosine(a, b) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = sum(x * x for x in a) ** 0.5
        nb = sum(y * y for y in b) ** 0.5
        return dot / (na * nb) if na and nb else 0.0

    return {
        profile.name: cosine(q_vec, vec) for profile, vec in zip(profiles, doc_vecs)
    }


# ---------------------------------------------------------------------------
# The safeguard: pull related tables back in
# ---------------------------------------------------------------------------


def expand_by_foreign_keys(
    chosen: list[str],
    fk_graph: dict[str, set[str]],
    all_names: set[str],
    max_added: int = 6,
) -> list[str]:
    """
    Any table one foreign-key hop from a chosen table joins the set.

    Without this, retrieval quietly destroys the agent's ability to answer
    anything requiring a JOIN -- which is most real questions.
    """
    added: list[str] = []
    for name in chosen:
        for neighbour in fk_graph.get(name, set()):
            if neighbour in all_names and neighbour not in chosen and neighbour not in added:
                added.append(neighbour)
                if len(added) >= max_added:
                    return added
    return added


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def retrieve(
    question: str,
    profiles: list[TableProfile],
    fk_graph: dict[str, set[str]] | None = None,
    top_k: int = TOP_K,
) -> RetrievalResult:
    """Pick the tables this question needs."""
    fk_graph = fk_graph or {}

    if len(profiles) < RETRIEVAL_THRESHOLD:
        return RetrievalResult(profiles, False, [], [])

    scores = _embedding_scores(question, profiles) or _keyword_scores(question, profiles)

    ranked = sorted(profiles, key=lambda p: scores.get(p.name, 0.0), reverse=True)
    best = scores.get(ranked[0].name, 0.0) if ranked else 0.0

    # Take top_k, but drop anything far weaker than the best match. Without
    # this, top_k always returns exactly top_k tables -- padding the prompt
    # with whatever ranked highest among the irrelevant ones.
    cutoff = best * RELATIVE_CUTOFF
    matched = [
        p.name
        for p in ranked[:top_k]
        if scores.get(p.name, 0.0) > 0 and scores.get(p.name, 0.0) >= cutoff
    ]

    # A question that matches nothing is better served by everything than by
    # an arbitrary slice.
    if not matched:
        return RetrievalResult(profiles, False, [], [])

    all_names = {p.name for p in profiles}
    added = expand_by_foreign_keys(matched, fk_graph, all_names)

    keep = set(matched) | set(added)
    selected = [p for p in profiles if p.name in keep]

    return RetrievalResult(selected, True, matched, added)
