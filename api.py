"""
HTTP API for the Data Analyst agent.

    python api.py                 -- Supabase, port 5000
    python api.py --csv           -- local ./workspace CSVs
    python api.py --port 8000

Endpoints:
    GET  /health          is the service up, and is the schema loaded
    GET  /tables          what the agent can see
    POST /ask             {"question": "..."} -> answer, sql, chart, events
    POST /ask/stream      same, but events arrive as they happen (SSE)

The agent holds a DuckDB connection that is not safe to use from two
threads at once, and Flask serves requests on threads. One lock serialises
every call into the agent -- questions queue instead of corrupting the
connection.
"""

from __future__ import annotations

import argparse
import datetime
import decimal
import json
import queue
import threading
from typing import Any

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, Response, jsonify, request
from flask.json.provider import DefaultJSONProvider

from analyst.agent import DataAnalystAgent
from analyst.events import Event


class IsoJSON(DefaultJSONProvider):
    """
    Dates as 2026-08-16, not 'Sun, 16 Aug 2026 00:00:00 GMT'.

    Flask's default renders dates in HTTP header format, which is useless
    to a charting frontend and to anything that has to sort them.
    """

    def default(self, o: Any):
        if isinstance(o, (datetime.date, datetime.datetime)):
            return o.isoformat()
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super().default(o)


app = Flask(__name__)
app.json = IsoJSON(app)

_agent: DataAnalystAgent | None = None
_lock = threading.Lock()


def get_agent() -> DataAnalystAgent:
    if _agent is None:
        raise RuntimeError("Agent not initialised")
    return _agent


def _error(message: str, status: int = 400):
    return jsonify({"error": message}), status


# ---------------------------------------------------------------------------
# Health and introspection
# ---------------------------------------------------------------------------


@app.get("/")
def index():
    """So opening the API in a browser shows something useful, not a 404."""
    return jsonify(
        {
            "service": "Data Analyst agent",
            "endpoints": {
                "GET /health": "service and schema status",
                "GET /tables": "tables the agent can see (also warms the schema)",
                "POST /ask": "{'question': '...'} -> narrative, sql, chart, events",
                "POST /ask/stream": "same, streamed as server-sent events",
            },
        }
    )


@app.get("/health")
def health():
    agent = get_agent()
    loaded = agent._con is not None
    return jsonify(
        {
            "status": "ok",
            "source": "csv" if agent.workspace else "supabase",
            "schema_loaded": loaded,
            "table_count": len(agent._profiles) if loaded else None,
        }
    )


@app.get("/tables")
def tables():
    """
    Forces the schema to load if it has not yet. Useful as a warm-up call
    before a demo, so the first real question is not slowed by ingestion.
    """
    agent = get_agent()
    with _lock:
        from analyst.events import EventStream

        agent._ensure_loaded(EventStream())
        return jsonify(
            {
                "tables": [
                    {
                        "name": p.name,
                        "rows": p.row_count,
                        "columns": [c.name for c in p.columns],
                    }
                    for p in agent._profiles
                ]
            }
        )


# ---------------------------------------------------------------------------
# Ask
# ---------------------------------------------------------------------------


def _question_from_request() -> str | None:
    body: dict[str, Any] = request.get_json(silent=True) or {}
    question = (body.get("question") or "").strip()
    return question or None


@app.post("/ask")
def ask():
    question = _question_from_request()
    if not question:
        return _error("Body must be JSON with a non-empty 'question' field")

    agent = get_agent()
    with _lock:
        try:
            result = agent.ask(question)
        except Exception as exc:
            return _error(f"{type(exc).__name__}: {exc}", 500)

    payload = result.to_dict()
    # A failed analysis is a valid answer, not an HTTP error -- the Manager
    # still gets the narrative explaining what went wrong.
    return jsonify(payload), 200


@app.post("/ask/stream")
def ask_stream():
    """
    Server-sent events. Each step of the pipeline arrives as it happens,
    then a final 'done' event carries the full result.

    The agent's listener runs on the worker thread; events are handed to
    the response generator through a queue.
    """
    question = _question_from_request()
    if not question:
        return _error("Body must be JSON with a non-empty 'question' field")

    agent = get_agent()
    events: queue.Queue = queue.Queue()
    SENTINEL = object()

    def listener(event: Event) -> None:
        events.put(
            {"type": event.type, "message": event.message, "payload": event.payload}
        )

    def work() -> None:
        with _lock:
            previous = agent._listener
            agent._listener = listener
            try:
                result = agent.ask(question)
                events.put({"type": "done", "result": result.to_dict()})
            except Exception as exc:
                events.put({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
            finally:
                agent._listener = previous
                events.put(SENTINEL)

    threading.Thread(target=work, daemon=True).start()

    def generate():
        while True:
            item = events.get()
            if item is SENTINEL:
                break
            yield f"data: {json.dumps(item, default=str)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def create_app(workspace: str | None = None) -> Flask:
    global _agent
    _agent = DataAnalystAgent(workspace)
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Data Analyst agent API")
    parser.add_argument("--csv", action="store_true", help="use ./workspace CSVs")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    create_app("./workspace" if args.csv else None)

    source = "local CSVs" if args.csv else "Supabase"
    print(f"Data Analyst API on http://{args.host}:{args.port}  ({source})")
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
