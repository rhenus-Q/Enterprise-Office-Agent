from graph.chains.query_rewriter import get_query_rewriter
from graph.state import GraphState


def rewrite_query(state: GraphState):
    """
    Pass-through node on the not_useful retry path.

    Rewrites the user's question into a more specific web search query,
    informed by the previous (not useful) answer, so the next web search has
    a real chance of fetching different, more relevant content than simply
    re-running the original question.
    """

    print("---REWRITE SEARCH QUERY---")

    question = state["question"]
    previous_answer = state.get("generation", "")

    new_query = get_query_rewriter().invoke(
        {
            "question": question,
            "previous_answer": previous_answer,
        }
    ).strip()

    print(f"---NEW SEARCH QUERY: {new_query}---")

    return {
        "search_query": new_query,
        # The rewrite is a real LLM call; count it against the run budget.
        "llm_call_count": state.get("llm_call_count", 0) + 1,
    }
