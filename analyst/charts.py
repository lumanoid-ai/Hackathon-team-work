"""
Step [5]: pick a chart type and build its config.

The model only chooses -- type, x, y, and an optional series column. The
config itself is assembled in Python from the actual result rows, so no
data point can be altered on the way through.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from .executor import QueryResult
from .llm import complete, strip_code_fence

CHART_TYPES = {"bar", "grouped_bar", "line", "pie", "table"}

SYSTEM = """You choose how to chart a result set. Reply with ONLY a JSON object:

{"type": "...", "x": "column name", "y": "column name", "series": "column name or null", "title": "short title"}

type must be one of: bar, grouped_bar, line, pie, table
- bar: one category against one number
- grouped_bar: two categories against one number (use series for the second)
- line: something changing over time
- pie: parts of a whole, only when there are 6 or fewer slices
- table: anything that does not fit the above, or more than 3 columns of detail

x and y must be exact column names from the result. No explanation."""


@dataclass
class Chart:
    id: str
    type: str
    title: str
    x: str
    y: str
    series: str | None
    data: list[dict[str, Any]]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "x": self.x,
            "y": self.y,
            "series": self.series,
            "data": self.data,
        }


def _fallback(result: QueryResult) -> dict:
    """Used when the model returns something unusable."""
    return {
        "type": "table",
        "x": result.columns[0],
        "y": result.columns[-1],
        "series": None,
        "title": "Query result",
    }


def make_chart(question: str, result: QueryResult) -> Chart:
    user = (
        f"QUESTION: {question}\n\n"
        f"COLUMNS: {', '.join(result.columns)}\n\n"
        f"FIRST ROWS:\n{result.to_prompt(limit=5)}"
    )

    try:
        spec = json.loads(strip_code_fence(complete(SYSTEM, user, max_tokens=300)))
    except Exception:
        spec = _fallback(result)

    # Never trust the model's column names -- verify against the real result.
    if spec.get("type") not in CHART_TYPES:
        spec = _fallback(result)
    if spec.get("x") not in result.columns or spec.get("y") not in result.columns:
        spec = _fallback(result)
    if spec.get("series") not in result.columns:
        spec["series"] = None

    return Chart(
        id=f"chart_{uuid.uuid4().hex[:8]}",
        type=spec["type"],
        title=spec.get("title") or "Query result",
        x=spec["x"],
        y=spec["y"],
        series=spec["series"],
        data=result.rows,
    )
