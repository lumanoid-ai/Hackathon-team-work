"""
Supabase (Postgres) as a data source.

DuckDB attaches the Postgres database directly, so every query in the rest
of the agent runs unchanged -- executor.py, sql_writer.py and the others
never learn where the tables came from.

Two modes, chosen by SUPABASE_MODE in .env:

    attach  (default) -- query Supabase live. Always current. Each query
                         crosses the network.
    copy              -- pull the tables into local DuckDB once. Queries
                         are then instant, but the data is a snapshot.
"""

from __future__ import annotations

import os
from typing import Callable

import duckdb

from .ingest import TableProfile, describe_data

DEFAULT_SCHEMA = "public"

# Postgres internals and Supabase's own tables -- never useful to the agent.
SKIP_SCHEMAS = {
    "pg_catalog",
    "information_schema",
    "auth",
    "storage",
    "realtime",
    "vault",
    "extensions",
    "graphql",
    "graphql_public",
    "supabase_migrations",
    "net",
    "cron",
}


class SupabaseError(RuntimeError):
    pass


def _connection_string() -> str:
    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        raise SupabaseError(
            "SUPABASE_DB_URL is not set. Copy it from your Supabase project: "
            "Settings -> Database -> Connection string -> URI"
        )
    return url


def _wanted_tables() -> set[str] | None:
    """SUPABASE_TABLES=a,b,c limits the agent to those tables. Unset means all."""
    raw = os.environ.get("SUPABASE_TABLES", "").strip()
    if not raw:
        return None
    return {t.strip() for t in raw.split(",") if t.strip()}


def attach(
    con: duckdb.DuckDBPyConnection | None = None,
    emit: Callable[[str, str, dict], None] | None = None,
) -> tuple[duckdb.DuckDBPyConnection, list[str]]:
    """
    Attach Supabase to DuckDB and return the list of queryable table names.

    Table names come back unqualified (hiring_funnel, not db.public.hiring_funnel)
    because views are created for each one -- that keeps generated SQL simple.
    """
    con = con or duckdb.connect(database=":memory:")
    url = _connection_string()

    con.execute("INSTALL postgres")
    con.execute("LOAD postgres")
    try:
        con.execute(f"ATTACH '{url}' AS supa (TYPE postgres, READ_ONLY)")
    except Exception as exc:
        raise SupabaseError(f"Could not connect to Supabase: {exc}") from exc

    schema = os.environ.get("SUPABASE_SCHEMA", DEFAULT_SCHEMA)
    wanted = _wanted_tables()

    rows = con.execute(
        """
        SELECT table_name
        FROM supa.information_schema.tables
        WHERE table_schema = ?
          AND table_type IN ('BASE TABLE', 'VIEW')
        ORDER BY table_name
        """,
        [schema],
    ).fetchall()

    tables: list[str] = []
    mode = os.environ.get("SUPABASE_MODE", "attach").lower()

    for (name,) in rows:
        if wanted and name not in wanted:
            continue
        source = f'supa.{schema}."{name}"'
        if mode == "copy":
            con.execute(f'CREATE OR REPLACE TABLE "{name}" AS SELECT * FROM {source}')
        else:
            con.execute(f'CREATE OR REPLACE VIEW "{name}" AS SELECT * FROM {source}')
        tables.append(name)

    if not tables:
        raise SupabaseError(
            f"No tables found in schema '{schema}'. "
            "Check SUPABASE_SCHEMA, or set SUPABASE_TABLES to the ones you want."
        )

    if emit:
        emit(
            "tool_call",
            f"Connected to Supabase: {len(tables)} tables in '{schema}' ({mode} mode)",
            {"tables": tables, "schema": schema, "mode": mode},
        )

    return con, tables


def foreign_keys(
    con: duckdb.DuckDBPyConnection, schema: str | None = None
) -> dict[str, set[str]]:
    """
    Which tables reference which. Used to keep JOINs intact when schema
    retrieval narrows the table list.

    Returns an undirected map: {table: {tables it is related to}}
    """
    schema = schema or os.environ.get("SUPABASE_SCHEMA", DEFAULT_SCHEMA)

    try:
        rows = con.execute(
            """
            SELECT tc.table_name, ccu.table_name AS references_table
            FROM supa.information_schema.table_constraints tc
            JOIN supa.information_schema.constraint_column_usage ccu
              ON tc.constraint_name = ccu.constraint_name
             AND tc.table_schema = ccu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = ?
            """,
            [schema],
        ).fetchall()
    except Exception:
        # Not every Postgres exposes these views the same way. A missing
        # FK map degrades retrieval, it does not break it.
        return {}

    graph: dict[str, set[str]] = {}
    for child, parent in rows:
        if child == parent:
            continue
        graph.setdefault(child, set()).add(parent)
        graph.setdefault(parent, set()).add(child)
    return graph


def load_supabase(
    emit: Callable[[str, str, dict], None] | None = None,
) -> tuple[duckdb.DuckDBPyConnection, list[TableProfile], dict[str, set[str]]]:
    """Attach, profile, and map relationships in one call."""
    con, tables = attach(emit=emit)
    profiles = describe_data(con, tables, emit=emit or (lambda *a: None))
    return con, profiles, foreign_keys(con)
