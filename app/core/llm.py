"""Gemini ka patla wrapper. Poore project mein LLM sirf yahan se call hoga."""
import json
import re
import time
from typing import Any

import google.generativeai as genai

from app.config import settings

_configured = False


def _ensure():
    global _configured
    if not _configured:
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("GEMINI_API_KEY .env mein set karein")
        genai.configure(api_key=settings.GEMINI_API_KEY)
        _configured = True


def llm_text(prompt: str, system: str | None = None, temperature: float = 0.4,
             max_retries: int = 3) -> str:
    """Plain text response."""
    _ensure()
    model = genai.GenerativeModel(settings.GEMINI_MODEL, system_instruction=system)
    last = None
    for attempt in range(max_retries):
        try:
            resp = model.generate_content(
                prompt, generation_config={"temperature": temperature}
            )
            return (resp.text or "").strip()
        except Exception as e:                       # free tier rate limit / 503
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"LLM call fail hui: {last}")


_FENCE = re.compile(r"^```(?:json)?|```$", re.MULTILINE)


def llm_json(prompt: str, system: str | None = None, temperature: float = 0.2,
             max_retries: int = 3) -> Any:
    """JSON response. Markdown fences khud saaf karta hai aur invalid JSON pe retry karta hai."""
    guard = "\n\nReturn ONLY valid JSON. No markdown, no explanation, no code fences."
    for attempt in range(max_retries):
        raw = llm_text(prompt + guard, system=system, temperature=temperature)
        cleaned = _FENCE.sub("", raw).strip()
        # kabhi kabhi model JSON ke aage peeche text likh deta hai
        start = min([i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1], default=-1)
        if start > 0:
            cleaned = cleaned[start:]
        end = max(cleaned.rfind("}"), cleaned.rfind("]"))
        if end != -1:
            cleaned = cleaned[: end + 1]
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            if attempt == max_retries - 1:
                raise
            time.sleep(1)
    raise RuntimeError("JSON parse nahi hua")
