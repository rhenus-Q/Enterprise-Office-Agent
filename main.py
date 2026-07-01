from dotenv import load_dotenv

# Load .env up front.
# Imports are intentionally side-effect-free: every external client
# (ChatOpenAI / OpenAIEmbeddings / Chroma retriever / Tavily) lives behind a
# lazy @lru_cache factory, so importing the engine needs no API keys and no
# network — that is what lets the mocked test suites and CI run without
# secrets. The clients still read env vars (OPENAI_API_KEY, etc.) when first
# constructed at runtime, so .env must be loaded before the graph runs.
load_dotenv()

from graph.config import web_search_enabled
from graph.engine import answer_question

# Presentation lives in graph/formatting.py (shared with the eval harness and
# the engine). Re-exported here so existing imports `from main import ...`
# keep working.
from graph.formatting import (
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

    # Privacy mode toggle: when WEB_SEARCH_ENABLED=false, questions are never
    # sent to an external web search service (Tavily).
    if not web_search_enabled():
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
