from enterprise_rag.graph.consts import STOP_REASON_TOOL_ERROR
from enterprise_rag.graph.state import GraphState


def clear_transient_tool_error(state: GraphState):
    """
    Terminal pass-through on the successful ("useful") path.

    A tool_error written mid-run is transient by design: a relevance-grader
    failure dropped one chunk/result, or a query rewrite fell back to the
    original question — and the run continued. When the final answer then
    passes BOTH quality gates, that stale warning no longer describes the
    terminal outcome, so it is cleared: stop_reason stays a terminal reason,
    and a fully successful answer never ships with an error caveat.

    Deliberately narrow:
    - retrieval_error / web_search_error persist even on success — they mean
      an entire evidence source was unavailable, which the user should see.
    - The terminal tool_error (hallucination/answer grader failed, recorded
      by tool_error_notice) is unaffected: that path ends through its own
      notice node, never through this one.
    """

    if state.get("stop_reason") == STOP_REASON_TOOL_ERROR:
        print("---SUCCESSFUL ANSWER: CLEARING TRANSIENT TOOL ERROR---")
        return {"stop_reason": ""}

    return {}
