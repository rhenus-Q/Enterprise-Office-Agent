"""
enterprise_rag.cli — the Enterprise RAG interactive command-line interface.

`main()` runs an interactive Q&A loop over
`enterprise_rag.graph.engine.answer_question()`: it loads `.env`, applies the
runtime tracing-privacy floor, prints the active-mode banner, then reads
questions and prints formatted answers (with caveats and Sources) until the
user exits.

Imports are intentionally side-effect-free: every external client
(ChatOpenAI / OpenAIEmbeddings / Chroma retriever / Tavily) lives behind a lazy
@lru_cache factory, so importing this module needs no API keys and no network —
that is what lets the mocked test suites and CI run without secrets. `.env`
loading and tracing-privacy enforcement are done inside `main()` (not at import
time) so the module stays importable without side effects; the clients still
read env vars (OPENAI_API_KEY, etc.) when first constructed at runtime, so
`.env` must be loaded before the graph runs, which `main()` guarantees.
"""

from dotenv import load_dotenv

from enterprise_rag.graph.config import offline_mode, privacy_mode, web_search_enabled
from enterprise_rag.graph.engine import answer_question
from enterprise_rag.graph.formatting import format_answer
from enterprise_rag.runtime_privacy import enforce_tracing_privacy


def main() -> None:
    # Load .env, then apply the runtime privacy modes immediately, before any
    # chain can run, so a PRIVACY_MODE / OFFLINE_MODE process never exports a
    # trace.
    load_dotenv()
    enforce_tracing_privacy()

    print("Agentic RAG Assistant for Enterprise Document Q&A")
    print("Type 'exit' to quit.\n")

    # Runtime privacy modes, most restrictive first. OFFLINE_MODE disables the
    # OpenAI path entirely, so every question ends with the offline caveat --
    # say so up front instead of letting the user discover it per question.
    if offline_mode():
        print(
            "OFFLINE_MODE is ENABLED. No external service is contacted, so "
            "Knowledge Q&A is unavailable and every question returns the "
            "deterministic offline response.\n"
        )
    elif privacy_mode():
        print(
            "PRIVACY_MODE is ENABLED. Tavily web search and LangSmith tracing "
            "are disabled and answers come from the local knowledge base, but "
            "this is not offline operation: questions and retrieved document "
            "text are still sent to OpenAI to generate the answer.\n"
        )
    # Privacy mode toggle: when WEB_SEARCH_ENABLED=false, questions are never
    # sent to an external web search service (Tavily).
    elif not web_search_enabled():
        print(
            "Web search is DISABLED (WEB_SEARCH_ENABLED=false). "
            "Answers come from the local knowledge base only.\n"
        )

    while True:
        question = input("Enter your question:\n> ").strip()

        if question.lower() in ["exit", "quit", "q"]:
            print("Bye.")
            break

        if not question:
            continue

        # The engine seeds the full GraphState (including the per-run
        # web_search_enabled / web_fallback_policy resolution) and runs the
        # compiled graph.
        result = answer_question(question)

        print("\nAnswer:")
        print(format_answer(result.raw_state))
        print("-" * 80)


if __name__ == "__main__":
    main()
