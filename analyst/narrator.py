"""
Step [6]: write the answer.

The prompt built here contains the question and the query rows. Nothing
else -- no schema, no sample rows, no file contents. If a number is not in
those rows, the model has no way to produce it.
"""

from __future__ import annotations

from .executor import QueryResult
from .llm import complete

SYSTEM = """You explain query results to a manager.

Rules:
- Use ONLY the numbers in the rows given. Never estimate, extrapolate, or
  bring in outside knowledge. If the rows do not answer the question, say so.
- Lead with the finding, not the method. No "the query shows" or
  "based on the data".
- Quote the specific numbers that matter. A manager should be able to act
  on the first sentence.
- If the rows reveal a cause, name it. If they only show a symptom, say
  what would need to be checked next.
- Three to five sentences. Plain prose, no bullet points, no headings."""


def explain(question: str, result: QueryResult) -> str:
    user = f"QUESTION:\n{question}\n\nRESULT ROWS:\n{result.to_prompt()}"
    return complete(SYSTEM, user, max_tokens=600)
