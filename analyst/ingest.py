"""
Ingest layer for the Data Analyst agent.

Steps [1] and [2] of the workflow:
    load_data()      -> CSVs in the workspace become DuckDB tables
    describe_data()  -> a compact, LLM-ready profile of those tables

Design rule: describe_data() output is the ONLY thing the SQL-writing
prompt sees about the data. It must be complete enough that correct SQL
is possible, and small enough that it fits in a prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

import duckdb

# How many distinct values a column can have before we stop listing them.
# Above this it is treated as free text / high cardinality.
MAX_ENUM_VALUES = 25

# Columns whose name looks like an identifier are never enumerated,
# even if cardinality happens to be low in a small sample.
ID_NAME_PATTERN = re.compile(r"(^|_)(id|uuid|guid|key|hash|email|phone)($|_)", re.I)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------

Emit = Callable[[str, str, dict], None]


def _noop_emit(event_type: str, message: str, payload: dict) -> None:
    """Default emitter. Replace with the one that streams to the Manager."""
    return None


# ---------------------------------------------------------------------------
# Profile data structures
# ---------------------------------------------------------------------------


@dataclass
class ColumnProfile:
    name: str
    dtype: str
    null_pct: float
    distinct_count: int
    values: list[Any] | None = None      # populated only for low-cardinality
    min_value: Any | None = None         # populated only for numeric / date
    max_value: Any | None = None

    def to_prompt_line(self) -> str:
        parts = [f"{self.name} ({self.dtype})"]
        if self.null_pct > 0:
            parts.append(f"{self.null_pct:.0f}% null")
        if self.values is not None:
            listed = ", ".join(repr(v) for v in self.values)
            parts.append(f"values: [{listed}]")
        elif self.min_value is not None:
            parts.append(f"range: {self.min_value} to {self.max_value}")
        elif self.distinct_count:
            parts.append(f"{self.distinct_count} distinct")
        return "  - " + " | ".join(parts)


@dataclass
class TableProfile:
    name: str
    source_file: str
    row_count: int
    columns: list[ColumnProfile]
    sample_rows: list[dict] = field(default_factory=list)

    def to_prompt(self) -> str:
        lines = [f"TABLE {self.name}  ({self.row_count} rows)"]
        lines += [c.to_prompt_line() for c in self.columns]
        if self.sample_rows:
            lines.append("  sample rows:")
            for row in self.sample_rows:
                lines.append("    " + repr(row))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# [1] load_data
# ---------------------------------------------------------------------------


def _table_name_from_path(path: Path) -> str:
    """hiring_funnel.csv -> hiring_funnel. Safe for SQL identifiers."""
    stem = path.stem.lower()
    stem = re.sub(r"[^a-z0-9_]+", "_", stem).strip("_")
    if not stem or stem[0].isdigit():
        stem = f"t_{stem}"
    return stem


def load_data(
    workspace: str | Path,
    con: duckdb.DuckDBPyConnection | None = None,
    emit: Emit = _noop_emit,
) -> tuple[duckdb.DuckDBPyConnection, list[str]]:
    """
    Load every CSV in the workspace into DuckDB as a table.

    DuckDB reads the CSV directly from disk -- we never pull it through
    pandas. That keeps memory flat and lets DuckDB do its own type
    sniffing, which is better than ours.
    """
    con = con or duckdb.connect(database=":memory:")
    workspace = Path(workspace)
    loaded: list[str] = []

    files: Iterable[Path] = sorted(workspace.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {workspace}")

    for path in files:
        table = _table_name_from_path(path)
        con.execute(
            f"CREATE OR REPLACE TABLE {table} AS "
            f"SELECT * FROM read_csv_auto(?, header=true, sample_size=-1)",
            [str(path)],
        )
        rows = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        loaded.append(table)

        emit(
            "tool_call",
            f"Loaded {path.name} ({rows} rows)",
            {"table": table, "file": path.name, "rows": rows},
        )

    return con, loaded


# ---------------------------------------------------------------------------
# [2] describe_data
# ---------------------------------------------------------------------------


def _profile_column(
    con: duckdb.DuckDBPyConnection,
    table: str,
    name: str,
    dtype: str,
    row_count: int,
) -> ColumnProfile:
    quoted = f'"{name}"'
    nulls, distinct = con.execute(
        f"SELECT count(*) FILTER (WHERE {quoted} IS NULL), "
        f"count(DISTINCT {quoted}) FROM {table}"
    ).fetchone()

    null_pct = (nulls / row_count * 100) if row_count else 0.0
    col = ColumnProfile(
        name=name,
        dtype=dtype,
        null_pct=null_pct,
        distinct_count=distinct,
    )

    is_identifier = bool(ID_NAME_PATTERN.search(name))
    numeric_or_temporal = any(
        token in dtype.upper()
        for token in ("INT", "DECIMAL", "DOUBLE", "FLOAT", "DATE", "TIMESTAMP")
    )

    if not is_identifier and 0 < distinct <= MAX_ENUM_VALUES and not numeric_or_temporal:
        # THE important branch: give the LLM the exact strings it must
        # match on, so it never invents 'offer' when the data says
        # 'Offer Extended'.
        rows = con.execute(
            f"SELECT DISTINCT {quoted} FROM {table} "
            f"WHERE {quoted} IS NOT NULL ORDER BY 1"
        ).fetchall()
        col.values = [r[0] for r in rows]
    elif numeric_or_temporal:
        lo, hi = con.execute(
            f"SELECT min({quoted}), max({quoted}) FROM {table}"
        ).fetchone()
        col.min_value, col.max_value = lo, hi

    return col


def describe_data(
    con: duckdb.DuckDBPyConnection,
    tables: list[str],
    sample_rows: int = 3,
    emit: Emit = _noop_emit,
) -> list[TableProfile]:
    """
    Build the profile that gets fed to the SQL-writing prompt.

    Returned objects render to text via TableProfile.to_prompt().
    """
    profiles: list[TableProfile] = []

    for table in tables:
        row_count = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        schema = con.execute(f"DESCRIBE {table}").fetchall()

        columns = [
            _profile_column(con, table, row[0], row[1], row_count)
            for row in schema
        ]

        cursor = con.execute(f"SELECT * FROM {table} LIMIT {sample_rows}")
        col_names = [d[0] for d in cursor.description]
        samples = [dict(zip(col_names, r)) for r in cursor.fetchall()]

        profile = TableProfile(
            name=table,
            source_file=f"{table}.csv",
            row_count=row_count,
            columns=columns,
            sample_rows=samples,
        )
        profiles.append(profile)

        emit(
            "tool_call",
            f"Profiled {table}: {len(columns)} columns, {row_count} rows",
            {"table": table, "columns": [c.name for c in columns]},
        )

    return profiles


def build_schema_prompt(profiles: list[TableProfile]) -> str:
    """Everything step [3] is allowed to know about the data."""
    return "\n\n".join(p.to_prompt() for p in profiles)


# ---------------------------------------------------------------------------
# Wiring for steps [1] and [2]
# ---------------------------------------------------------------------------


def ingest(workspace: str | Path, emit: Emit = _noop_emit):
    con, tables = load_data(workspace, emit=emit)
    profiles = describe_data(con, tables, emit=emit)
    return con, profiles, build_schema_prompt(profiles)


if __name__ == "__main__":
    import sys

    def printer(event_type: str, message: str, payload: dict) -> None:
        print(f"[{event_type}] {message}")

    _con, _profiles, schema_text = ingest(sys.argv[1], emit=printer)
    print("\n--- schema block sent to the LLM ---\n")
    print(schema_text)
