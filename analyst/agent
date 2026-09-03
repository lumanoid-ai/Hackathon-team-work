"""
The Data Analyst agent.

    from analyst.agent import DataAnalystAgent

    agent = DataAnalystAgent()                 # Supabase, from .env
    agent = DataAnalystAgent("./workspace")    # local CSVs

    answer = agent.ask("Why are we behind on Q3 hiring?")

The Manager agent only ever sees ask() and the AnalysisResult it returns.
Everything inside is free to change.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import charts, narrator, retrieval, sql_writer
from .events import Event, EventStream
from .executor import QueryFailed, QueryResult, run_sql
from .ingest import TableProfile, build_schema_prompt, describe_data, load_data


@dataclass
class AnalysisResult:
    question: str
    narrative: str
    sql: str
    chart: dict | None
    row_count: int
    events: list[dict]
    tables_used: list[str]
    failed: bool = False

    def to_dict(self) -> dict:
        return {
            "question": self.question,
            "narrative": self.narrative,
            "sql": self.sql,
            "chart_id": self.chart["id"] if self.chart else None,
            "chart": self.chart,
            "row_count": self.row_count,
            "tables_used": self.tables_used,
            "events": self.events,
            "failed": self.failed,
        }


class DataAnalystAgent:
    def __init__(
        self,
        workspace: str | Path | None = None,
        listener: Callable[[Event], None] | None = None,
    ):
        """
        workspace: a folder of CSVs. Leave it out to use Supabase, which is
        configured entirely through .env.
        """
        self.workspace = Path(workspace) if workspace else None
        self._listener = listener
        self._con = None
        self._profiles: list[TableProfile] = []
        self._fk_graph: dict[str, set[str]] = {}

    # -- steps [1] and [2], run once and cached -----------------------------

    def _ensure_loaded(self, stream: EventStream) -> None:
        if self._con is not None:
            return

        def emit(type, message, payload):
            stream.emit(type, message, **payload)

        if self.workspace is not None:
            self._con, tables = load_data(self.workspace, emit=emit)
            self._profiles = describe_data(self._con, tables, emit=emit)
            self._fk_graph = {}
        else:
            from .supabase_source import load_supabase

            self._con, self._profiles, self._fk_graph = load_supabase(emit=emit)

    # -- steps [3] through [6] ---------------------------------------------

    def ask(self, question: str) -> AnalysisResult:
        stream = EventStream(self._listener)
        self._ensure_loaded(stream)

        picked = retrieval.retrieve(question, self._profiles, self._fk_graph)
        schema = build_schema_prompt(picked.profiles)
        tables_used = [p.name for p in picked.profiles]
        stream.emit(
            "tool_call",
            f"Schema: {picked.summary()}",
            tables=tables_used,
            retrieved=picked.used_retrieval,
        )

        sql = sql_writer.write_sql(question, schema)
        stream.emit("thinking", "Wrote query", sql=sql)

        def on_error(bad_sql: str, error: str) -> str:
            fixed = sql_writer.fix_sql(question, schema, bad_sql, error)
            stream.emit("thinking", "Rewrote query", sql=fixed, reason=error)
            return fixed

        try:
            result: QueryResult = run_sql(
                self._con,
                sql,
                on_error=on_error,
                emit=lambda t, m: stream.emit(t, m),
            )
        except QueryFailed as exc:
            stream.emit("error", "Could not produce a working query")
            return AnalysisResult(
                question=question,
                narrative=(
                    "I could not answer this from the available data. "
                    f"The query kept failing: {exc.error}"
                ),
                sql=exc.sql,
                chart=None,
                row_count=0,
                events=stream.to_list(),
                tables_used=tables_used,
                failed=True,
            )

        chart = charts.make_chart(question, result)
        stream.emit("tool_call", f"Built {chart.type} chart", chart_id=chart.id)

        text = narrator.explain(question, result)
        stream.emit("result", "Analysis complete")

        return AnalysisResult(
            question=question,
            narrative=text,
            sql=result.sql,
            chart=chart.to_dict(),
            row_count=len(result.rows),
            events=stream.to_list(),
            tables_used=tables_used,
        )
