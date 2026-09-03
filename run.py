"""
Interactive runner.

    python run.py              -- use Supabase (configured in .env)
    python run.py --csv        -- use the local ./workspace CSVs

Ask questions one after another. Type quit to exit.
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from analyst.agent import DataAnalystAgent
from analyst.events import print_listener

EXIT_WORDS = {"quit", "exit", "q", "bye"}


def main() -> None:
    use_csv = "--csv" in sys.argv
    agent = DataAnalystAgent(
        "./workspace" if use_csv else None,
        listener=print_listener,
    )

    source = "local CSVs" if use_csv else "Supabase"
    print(f"Data Analyst agent ready ({source}). Type quit to exit.\n")

    while True:
        try:
            question = input("Question: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not question:
            continue
        if question.lower() in EXIT_WORDS:
            break

        print()
        try:
            result = agent.ask(question)
        except Exception as exc:
            print(f"\nSomething went wrong: {exc}\n")
            continue

        print("\n--- SQL ---")
        print(result.sql)
        print("\n--- ANSWER ---")
        print(result.narrative)
        if result.chart:
            print(f"\n--- CHART: {result.chart['type']} ({result.row_count} rows) ---")
        print()


if __name__ == "__main__":
    main()