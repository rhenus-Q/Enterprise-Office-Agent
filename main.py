from dotenv import load_dotenv

# Load .env before importing app.
# Importing graph.graph triggers module-level init of nodes / chains
# (constructing ChatOpenAI / OpenAIEmbeddings / retriever), which needs the env vars.
load_dotenv()

from graph.config import web_search_enabled  # noqa: E402
from graph.consts import (  # noqa: E402
    STOP_REASON_BUDGET_EXHAUSTED,
    STOP_REASON_GENERATION_ERROR,
    STOP_REASON_MAX_RETRIES_NOT_GROUNDED,
    STOP_REASON_MAX_RETRIES_NOT_USEFUL,
    STOP_REASON_RETRIEVAL_ERROR,
    STOP_REASON_TOOL_ERROR,
    STOP_REASON_WEB_SEARCH_DISABLED,
    STOP_REASON_WEB_SEARCH_ERROR,
)
from graph.graph import app  # noqa: E402


# Caveat shown when the workflow stopped because it would have needed web
# search, but web search is disabled (privacy mode).
WEB_SEARCH_DISABLED_NOTE = (
    "Note: Web search is disabled, so I could only use the local knowledge base. "
    "I may not have enough information to fully answer this question."
)

# Caveat shown when the retry limit was reached and the final answer still
# failed the grounding (anti-hallucination) check.
MAX_RETRIES_NOT_GROUNDED_NOTE = (
    "Warning: This answer did not pass the grounding (anti-hallucination) check "
    "after the retry limit was reached. It may contain information that is not "
    "supported by the source documents, so do not treat it as fully reliable."
)

# Caveat shown when the retry limit was reached and the final answer is
# grounded but still failed the usefulness check.
MAX_RETRIES_NOT_USEFUL_NOTE = (
    "Warning: This answer did not pass the usefulness check after the retry "
    "limit was reached. It is grounded in the source documents but may not "
    "fully answer your question."
)

# Caveat shown when the per-run cost/latency budget stopped the run before
# the answer passed (or finished) the quality gates.
BUDGET_EXHAUSTED_NOTE = (
    "Note: This answer stopped because the per-run cost/latency budget was "
    "reached. The answer may be incomplete or not fully verified."
)

# Caveat shown when the local retriever (Chroma) failed; the run degraded to
# web search (or the insufficient-context answer in privacy mode).
RETRIEVAL_ERROR_NOTE = (
    "Note: Local document retrieval failed, so the answer may be incomplete "
    "or unavailable."
)

# Caveat shown when the web search call (Tavily) failed; the run continued
# with the local knowledge base only.
WEB_SEARCH_ERROR_NOTE = (
    "Note: Web search failed, so I answered only from the local knowledge "
    "base. The answer may be incomplete."
)

# Caveat shown when the generation LLM call itself failed; the answer above
# is a safe placeholder, not a real generated answer.
GENERATION_ERROR_NOTE = (
    "Note: The language model call failed before a reliable answer could be "
    "generated. Please try again."
)

# Caveat shown when an internal tool call (a grader or the query rewriter)
# failed; the answer may be missing dropped content or skipped verification.
TOOL_ERROR_NOTE = (
    "Note: An internal step failed during processing, so this answer may be "
    "incomplete or not fully verified."
)

# Maps a recorded stop reason to the caveat appended to the final answer.
STOP_REASON_NOTES = {
    STOP_REASON_WEB_SEARCH_DISABLED: WEB_SEARCH_DISABLED_NOTE,
    STOP_REASON_MAX_RETRIES_NOT_GROUNDED: MAX_RETRIES_NOT_GROUNDED_NOTE,
    STOP_REASON_MAX_RETRIES_NOT_USEFUL: MAX_RETRIES_NOT_USEFUL_NOTE,
    STOP_REASON_BUDGET_EXHAUSTED: BUDGET_EXHAUSTED_NOTE,
    STOP_REASON_RETRIEVAL_ERROR: RETRIEVAL_ERROR_NOTE,
    STOP_REASON_WEB_SEARCH_ERROR: WEB_SEARCH_ERROR_NOTE,
    STOP_REASON_GENERATION_ERROR: GENERATION_ERROR_NOTE,
    STOP_REASON_TOOL_ERROR: TOOL_ERROR_NOTE,
}


def format_answer(result) -> str:
    """
    Format the final graph state for display.

    Appends a caveat only when the graph recorded a stop reason (privacy mode
    or retry exhaustion); normal successful answers are returned unchanged.
    """

    answer = result.get("generation", "")

    note = STOP_REASON_NOTES.get(result.get("stop_reason", ""))
    if note:
        return f"{answer}\n\n{note}"

    return answer


def main():
    print("Enterprise Knowledge Assistant")
    print("Type 'exit' to quit.\n")

    # Privacy mode toggle: when WEB_SEARCH_ENABLED=false, questions are never
    # sent to an external web search service (Tavily).
    allow_web_search = web_search_enabled()
    if not allow_web_search:
        print("Web search is DISABLED (WEB_SEARCH_ENABLED=false). "
              "Answers come from the local knowledge base only.\n")

    while True:
        question = input("Enter your question:\n> ").strip()

        if question.lower() in ["exit", "quit", "q"]:
            print("Bye.")
            break

        if not question:
            continue

        # Initialize the full GraphState so nodes / conditional functions never read a missing key.
        result = app.invoke(
            {
                "question": question,
                "documents": [],
                "generation": "",
                "web_search": False,
                "web_search_enabled": allow_web_search,
                "retries": 0,
                "stop_reason": "",
                "retry_feedback": "",
                "search_query": "",
                "llm_call_count": 0,
                "web_search_count": 0,
                "web_result_grading_count": 0,
            }
        )

        print("\nAnswer:")
        print(format_answer(result))
        print("-" * 80)


if __name__ == "__main__":
    main()