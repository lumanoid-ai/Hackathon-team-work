"""
Step [3]: the question plus the real schema become a SQL query.

The model never sees the data itself -- only the profile built by
ingest.describe_data(). That profile carries the exact string values of
every low-cardinality column, which is what stops the model from
inventing 'offer' when the data says 'Offer Extended'.
"""

from __future__ import annotations

from .llm import complete, strip_code_fence

SYSTEM = """You write DuckDB SQL. You are given a question and the real schema.

Rules:
- Return ONLY the SQL query. No explanation, no markdown fence, no commentary.
- Use only tables and columns listed in the schema. Never invent a column.
- Match string values EXACTLY as listed in the schema. If the schema says
  'Offer Extended', never write 'offer' or 'Offer'.
- If the question asks WHY something is happening, or asks about a problem,
  a gap, or a cause, do NOT return a single number. Return a breakdown:
  GROUP BY the dimensions that could explain it (department, stage, source,
  month) so the pattern is visible in the rows.
- When the answer needs targets as well as actuals, JOIN the relevant tables.
- Keep the result under 100 rows. Use LIMIT if a query could return more.
- Quote column names that contain spaces or capitals with double quotes."""

RETRY_SYSTEM = SYSTEM + """

Your previous query failed. Read the error, find the mistake, and return a
corrected query. Return ONLY the SQL."""


def write_sql(question: str, schema: str) -> str:
    """First attempt."""
    user = f"SCHEMA:\n{schema}\n\nQUESTION:\n{question}"
    return strip_code_fence(complete(SYSTEM, user))


def fix_sql(question: str, schema: str, bad_sql: str, error: str) -> str:
    """Retry after a failure. The error text goes straight back to the model."""
    user = (
        f"SCHEMA:\n{schema}\n\n"
        f"QUESTION:\n{question}\n\n"
        f"YOUR QUERY:\n{bad_sql}\n\n"
        f"WHAT WENT WRONG:\n{error}"
    )
    return strip_code_fence(complete(RETRY_SYSTEM, user))
