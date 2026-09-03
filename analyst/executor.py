"""
Step [4]: run the query, and when it goes wrong, hand the problem back to
the model.

Two kinds of wrong are handled here:

  1. The query errors. DuckDB tells us why; that text goes back verbatim.
  2. The query succeeds but returns nothing. This is the dangerous one --
     no exception is raised, so without an explicit check the empty table
     would flow straight into the narrative step and the model would be
     asked to explain nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import duckdb

MAX_RETRIES = 2


@dataclass
class QueryResult:
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    attempts: int

    @property
    def is_empty(self) -> bool:
        return not self.rows

    def to_prompt(self, limit: int = 60) -> str:
        """The only view of the data the narrator is allowed to see."""
        if self.is_empty:
            return "(no rows)"
        shown = self.rows[:limit]
        lines = [" | ".join(self.columns)]
        lines += [" | ".join(str(r[c]) for c in self.columns) for r in shown]
        if len(self.rows) > limit:
            lines.append(f"... {len(self.rows) - limit} more rows")
        return "\n".join(lines)


class QueryFailed(RuntimeError):
    def __init__(self, sql: str, error: str, attempts: int):
        super().__init__(error)
        self.sql = sql
        self.error = error
        self.attempts = attempts


def _run_once(
    con: duckdb.DuckDBPyConnection, sql: str
) -> tuple[list[str], list[dict]]:
    cursor = con.execute(sql)
    columns = [d[0] for d in cursor.description]
    rows = [dict(zip(columns, r)) for r in cursor.fetchall()]
    return columns, rows


def run_sql(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    on_error,
    emit=None,
) -> QueryResult:
    """
    Execute with retries.

    on_error(bad_sql, error_text) -> corrected_sql
    Supplied by the caller so this module never imports the LLM directly.
    """
    attempt = 0
    current = sql

    while True:
        attempt += 1
        try:
            columns, rows = _run_once(con, current)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        else:
            if rows:
                if emit:
                    emit("result", f"Query returned {len(rows)} rows")
                return QueryResult(current, columns, rows, attempt)
            error = (
                "The query ran but returned zero rows. The filter values "
                "probably do not match the data. Check the exact string "
                "values in the schema and widen or correct the WHERE clause."
            )

        if attempt > MAX_RETRIES:
            raise QueryFailed(current, error, attempt)

        if emit:
            emit("error", f"Attempt {attempt} failed, rewriting query")
        current = on_error(current, error)
