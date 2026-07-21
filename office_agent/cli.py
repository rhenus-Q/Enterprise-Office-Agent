"""
office_agent.cli — the Enterprise Office Agent interactive command-line interface.

`main()` runs an interactive loop over
`office_agent.engine.answer_office_request()`: it reads a request, shows how the
deterministic router classified it (intent + selected tool), prints the tool's
response, and surfaces the carried-through observability fields (stop reason,
sources, run id) when present. It duplicates no router or tool logic — it is a
pure presentation layer over the single Office Agent entry point.

This module imports nothing from `enterprise_rag`, preserving Office Agent
module independence. Tracing privacy for the Knowledge Q&A path is already
enforced per-run inside `enterprise_rag`'s `answer_question()` (which the
knowledge adapter calls); the deterministic tools and the optional LLM-assist
gates (`office_agent/llm_assist/config.py`) need no `enterprise_rag` import.
`.env` is loaded inside `main()` (not at import time) so the module stays
importable without side effects; it is needed only by the Knowledge Q&A path
and the optional, default-off assists, and is harmless otherwise.
"""

import sys

from dotenv import load_dotenv

from office_agent.engine import answer_office_request


def main() -> None:
    load_dotenv()

    # The deterministic mock tool output uses a few non-ASCII characters (e.g.
    # the em-dash "—"). Force UTF-8 on stdout so the CLI prints cleanly on
    # consoles whose default encoding (e.g. Windows cp1252) would otherwise
    # raise UnicodeEncodeError.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("Enterprise Office Agent")
    print("Type 'exit' to quit.\n")

    while True:
        try:
            request = input("Enter your request:\n> ").strip()
        except (KeyboardInterrupt, EOFError):
            # Ctrl+C / EOF at the prompt: exit cleanly, exactly like an explicit
            # quit command -- never surface a traceback. These are control-flow
            # signals, not engine failures.
            print("\nBye.")
            break

        if request.lower() in ["exit", "quit", "q"]:
            print("Bye.")
            break

        if not request:
            continue

        # Single entry point: the router picks the intent and the engine
        # dispatches to the matching tool. Everything printed below comes from
        # the returned OfficeAgentResponse fields only. The deterministic tools
        # do not raise, but the Knowledge Q&A path reaches the RAG engine, whose
        # contract does not promise a result for an unexpected internal error;
        # keep the loop alive and surface only the exception *type* (a message
        # could carry paths or secrets), matching the repo convention.
        try:
            response = answer_office_request(request)
        except Exception as exc:
            print(f"\n---REQUEST FAILED ({type(exc).__name__})---")
            print("-" * 80)
            continue

        print(f"\nIntent : {response.intent}")
        print(f"Tool   : {response.tool or '-'}")
        print("-" * 80)
        print(response.content)

        if response.stop_reason:
            print(f"\nStop reason: {response.stop_reason}")
        if response.sources:
            print("\nSources:")
            for source in response.sources:
                print(f"- {source}")
        if response.run_id is not None:
            print(f"\nRun id : {response.run_id}")

        print("-" * 80)


if __name__ == "__main__":
    main()
