from dotenv import load_dotenv

# Load .env up front.
# Imports are intentionally side-effect-free: every external client
# (ChatOpenAI / OpenAIEmbeddings / Chroma retriever / Tavily) lives behind a
# lazy @lru_cache factory, so importing the engine needs no API keys and no
# network — that is what lets the mocked test suites and CI run without
# secrets. The clients still read env vars (OPENAI_API_KEY, etc.) when first
# constructed at runtime, so .env must be loaded before the graph runs.
load_dotenv()

from enterprise_rag.graph.config import offline_mode, privacy_mode, web_search_enabled
from enterprise_rag.graph.engine import answer_question
from enterprise_rag.runtime_privacy import enforce_tracing_privacy

# Runtime privacy modes are applied immediately after .env is loaded, before any
# chain can run, so a PRIVACY_MODE / OFFLINE_MODE process never exports a trace.
enforce_tracing_privacy()

# Presentation lives in enterprise_rag/graph/formatting.py (shared with the eval harness and
# the engine). Re-exported here so existing imports `from main import ...`
# keep working.
from enterprise_rag.graph.formatting import (
    BUDGET_EXHAUSTED_NOTE,
    GENERATION_ERROR_NOTE,
    LOCAL_SOURCE_FALLBACK_LABEL,
    MAX_RETRIES_NOT_GROUNDED_NOTE,
    MAX_RETRIES_NOT_USEFUL_NOTE,
    RETRIEVAL_ERROR_NOTE,
    SOURCES_HEADER,
    STOP_REASON_NOTES,
    TOOL_ERROR_NOTE,
    WEB_FALLBACK_DISABLED_NOTE,
    WEB_SEARCH_DISABLED_NOTE,
    WEB_SEARCH_ERROR_NOTE,
    WEB_SOURCE_FALLBACK_LABEL,
    format_answer,
    format_sources,
)


def main():
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
