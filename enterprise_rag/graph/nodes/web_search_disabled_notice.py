from enterprise_rag.graph.consts import STOP_REASON_WEB_SEARCH_DISABLED
from enterprise_rag.graph.state import GraphState


def web_search_disabled_notice(state: GraphState):
    """
    Terminal node for privacy mode.

    Reached when web search is disabled and no more information can be added:
    either the answer is grounded but does not fully answer the question, or
    generation produced the deterministic insufficient-context answer (no
    usable documents, no earlier failure recorded). Records a machine-readable
    stop reason so the caller (main.py) can attach a user-facing caveat to the
    final answer. The generation itself is left untouched.
    """

    print("---WEB SEARCH DISABLED: ANSWER LIMITED TO LOCAL KNOWLEDGE BASE---")

    return {"stop_reason": STOP_REASON_WEB_SEARCH_DISABLED}
