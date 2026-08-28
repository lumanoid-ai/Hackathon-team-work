"""
run_manager.py -- run the Manager from your terminal.

    python run_manager.py
    python run_manager.py "Why did revenue drop last quarter?"

Use this constantly while you build. It is much faster than testing through
a browser, and you see every event printed as it happens.
"""

import sys
from agents.manager import ManagerAgent

DEFAULT_REQUEST = "We're behind on Q3 hiring and I don't know why."


def main():
    request = " ".join(sys.argv[1:]) or DEFAULT_REQUEST

    manager = ManagerAgent()
    outcome = manager.handle(request)

    print("\n" + "=" * 62)
    print("THE BRIEF")
    print("=" * 62)
    print(outcome["brief"])
    print("=" * 62 + "\n")


if __name__ == "__main__":
    main()
