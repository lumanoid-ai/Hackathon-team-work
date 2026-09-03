"""
The one place that talks to the model.

Everything else calls complete(). Swap the provider here and the rest of
the agent does not change.
"""

from __future__ import annotations

import os
import re

MODEL = os.environ.get("ANALYST_MODEL", "gemini-3.6-flash")
MAX_TOKENS = 4000

_llm = None


class LLMError(RuntimeError):
    pass


def _get_llm():
    """Built once and reused -- creating a client per call is wasteful."""
    global _llm
    if _llm is not None:
        return _llm

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
    except ImportError as exc:
        raise LLMError("langchain-google-genai package not installed") from exc

    if not os.environ.get("GEMINI_API_KEY"):
        raise LLMError("GEMINI_API_KEY is not set")

    _llm = ChatGoogleGenerativeAI(
        model=MODEL,
        google_api_key=os.environ["GEMINI_API_KEY"],
        temperature=0,
        max_output_tokens=MAX_TOKENS,
    )
    return _llm


def complete(system: str, user: str, max_tokens: int = MAX_TOKENS) -> str:
    """Send one prompt, get plain text back."""
    from langchain_core.messages import HumanMessage, SystemMessage

    response = _get_llm().invoke(
        [SystemMessage(content=system), HumanMessage(content=user)]
    )

    text = response.content
    if isinstance(text, list):
        text = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in text
        )
    if not text or not text.strip():
        raise LLMError("Model returned an empty response")
    return text.strip()


def strip_code_fence(text: str) -> str:
    """LLMs wrap code in ```sql ... ``` no matter how firmly you ask them not to."""
    match = re.search(r"```(?:sql|json)?\s*(.*?)```", text, re.S)
    return (match.group(1) if match else text).strip()