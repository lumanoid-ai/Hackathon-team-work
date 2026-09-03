"""
Load a CSV into an existing Supabase table.

    python load_csv_to_supabase.py ai_job_market.csv ai_job_market

Create the table first (run its schema.sql in the SQL Editor). This script
fills a table, it does not create one.

Reads SUPABASE_DB_URL from .env -- the same value the agent uses.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import duckdb
from dotenv import load_dotenv

load_dotenv()

BATCH = 2000


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__.strip())

    csv_path = Path(sys.argv[1])
    table = sys.argv[2]

    if not csv_path.exists():
        sys.exit(f"{csv_path} not found")

    url = os.environ.get("SUPABASE_DB_URL") or os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("SUPABASE_DB_URL is not set in .env")

    schema = os.environ.get("SUPABASE_SCHEMA", "public")

    con = duckdb.connect(database=":memory:")
    con.execute("INSTALL postgres")
    con.execute("LOAD postgres")
    con.execute(f"ATTACH '{url}' AS supa (TYPE postgres)")

    con.execute(
        "CREATE TABLE staged AS SELECT * FROM "
        "read_csv_auto(?, header=true, sample_size=-1)",
        [str(csv_path)],
    )
    total = con.execute("SELECT count(*) FROM staged").fetchone()[0]
    print(f"read {total} rows from {csv_path.name}")

    # Sent in batches: one 10,000-row INSERT over a pooled connection is a
    # good way to hit a statement timeout.
    sent = 0
    while sent < total:
        con.execute(
            f'INSERT INTO supa.{schema}."{table}" '
            f"SELECT * FROM staged LIMIT {BATCH} OFFSET {sent}"
        )
        sent += BATCH
        print(f"  {min(sent, total)}/{total}")

    final = con.execute(f'SELECT count(*) FROM supa.{schema}."{table}"').fetchone()[0]
    print(f"\n{table} now has {final} rows")


if __name__ == "__main__":
    main()
