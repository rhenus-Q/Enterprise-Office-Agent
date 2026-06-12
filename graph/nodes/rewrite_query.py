from graph.chains.query_rewriter import get_query_rewriter
from graph.consts import STOP_REASON_TOOL_ERROR
from graph.state import GraphState


def rewrite_query(state: GraphState):
    """
    Pass-through node on the not_useful retry path.

    Rewrites the user's question into a more specific web search query,
    informed by the previous (not useful) answer, so the next web search has
    a real chance of fetching different, more relevant content than simply
    re-running the original question.

    A rewriter LLM failure must not crash the run: the node falls back to the
    original question (search_query="" means "use the question" downstream)
    and records stop_reason=tool_error so the final answer carries an honest
    caveat. The retry loop continues normally and stays fully gated.
    """

    print("---REWRITE SEARCH QUERY---")

    question = state["question"]
    previous_answer = state.get("generation", "")

    try:
        new_query = (
            get_query_rewriter()
            .invoke(
                {
                    "question": question,
                    "previous_answer": previous_answer,
                }
            )
            .strip()
        )
    except Exception as exc:
        # Log only the exception type: messages may carry secrets.
        print(
            f"---QUERY REWRITE FAILED ({type(exc).__name__}): FALLING BACK TO THE ORIGINAL QUESTION---"
        )
        return {
            "search_query": "",
            # The failed attempt was still a real API call; count it.
            "llm_call_count": state.get("llm_call_count", 0) + 1,
            "stop_reason": STOP_REASON_TOOL_ERROR,
        }

    print(f"---NEW SEARCH QUERY: {new_query}---")

    return {
        "search_query": new_query,
        # The rewrite is a real LLM call; count it against the run budget.
        "llm_call_count": state.get("llm_call_count", 0) + 1,
    }
