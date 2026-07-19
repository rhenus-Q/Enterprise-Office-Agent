"""
Demo: Office Agent (v1.6 — deterministic, local-only).

Runs a few requests through `office_agent.engine.answer_office_request` and
prints the selected intent and response for each. By default it exercises only
the local mock capabilities (Daily Briefing, Email Summary, Calendar Lookup,
Task / Ticket Assistant, Meeting Agent / Meeting Prep, Workflow / Approval Agent)
plus one unsupported request — no API keys, no external services, no Chroma index
required.

Usage:
    uv run python scripts/demo_office_agent_v1.py
    uv run python scripts/demo_office_agent_v1.py --include-knowledge

`--include-knowledge` additionally sends one question through the real Enterprise
RAG pipeline (Knowledge Q&A), which may require the existing enterprise_rag setup:
a built Chroma index (`uv run python -m enterprise_rag.ingestion`) and API keys
(OPENAI_API_KEY, TAVILY_API_KEY). It is off by default so the demo stays local.
"""

import argparse
import sys
from pathlib import Path

# The mock tool output uses a few non-ASCII characters (e.g. the em-dash "—").
# Force UTF-8 on stdout so the demo prints cleanly on consoles whose default
# encoding (e.g. Windows cp1252) would otherwise raise UnicodeEncodeError.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Make repo-root imports (office_agent.*) work when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Local, deterministic requests — safe to run without any external services.
DEFAULT_REQUESTS = [
    ("Daily Briefing", "give me my daily briefing"),
    ("Email Summary", "summarize unread emails"),
    ("Calendar Lookup", "what meetings do I have today?"),
    ("Task / Ticket Assistant", "show blocked tickets"),
    ("Meeting Agent / Meeting Prep", "prepare me for my next meeting"),
    ("Workflow / Approval Agent", "show pending approvals"),
    ("Unsupported request", "order lunch for the team"),
]

# Only run when --include-knowledge is passed (may hit the real RAG pipeline).
KNOWLEDGE_REQUEST = ("Knowledge Q&A", "what is the VPN access policy?")


def _print_result(title: str, request: str) -> None:
    from office_agent.engine import answer_office_request

    response = answer_office_request(request)
    print("=" * 72)
    print(f"# {title}")
    print(f"Request: {request}")
    print(f"Intent : {response.intent}")
    print("-" * 72)
    print(response.content)
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Office Agent v1 demo (local-only by default).")
    parser.add_argument(
        "--include-knowledge",
        action="store_true",
        help="Also run the Knowledge Q&A example (may require the enterprise_rag setup/API keys).",
    )
    args = parser.parse_args(argv)

    requests = list(DEFAULT_REQUESTS)
    if args.include_knowledge:
        requests.append(KNOWLEDGE_REQUEST)

    print("Office Agent v1 demo")
    print(f"({len(requests)} request(s); local mock capabilities require no API keys)\n")
    for title, request in requests:
        _print_result(title, request)

    return 0


if __name__ == "__main__":
    sys.exit(main())
