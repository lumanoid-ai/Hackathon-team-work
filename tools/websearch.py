"""
tools/websearch.py -- web search. Free, no API key, no signup.

Uses DuckDuckGo through the `ddgs` package. Install it once:
    pip install ddgs

Set SEARCH_MODE in .env:
  live -> real web search
  mock -> canned results, works offline (use when demoing without wifi)
"""

import os
from dotenv import load_dotenv

load_dotenv()

MODE = os.getenv("SEARCH_MODE", "live").lower()


def search(query: str, max_results: int = 5) -> list[dict]:
    """
    Returns [{title, snippet, url}, ...]

    Never raises. If the network is down or DuckDuckGo rate-limits us,
    it falls back to mock results so your demo keeps moving.
    """
    if MODE == "mock":
        return _mock(query)

    try:
        from ddgs import DDGS
        raw = list(DDGS().text(query, max_results=max_results))
        if not raw:
            return _mock(query)
        return [{
            "title": r.get("title", ""),
            "snippet": r.get("body", "")[:400],
            "url": r.get("href", ""),
        } for r in raw]
    except Exception:
        return _mock(query)


def _mock(query: str) -> list[dict]:
    """Offline stand-ins so the agent still returns a shaped answer."""
    return [
        {"title": f"{query} - overview",
         "snippet": "Offline mode: this is a stand-in search result.",
         "url": "https://example.com/overview"},
        {"title": f"{query} - comparison guide",
         "snippet": "Offline mode: this is a stand-in search result.",
         "url": "https://example.org/compare"},
    ]
