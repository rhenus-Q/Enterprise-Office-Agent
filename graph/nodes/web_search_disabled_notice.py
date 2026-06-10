from graph.consts import STOP_REASON_WEB_SEARCH_DISABLED
from graph.state import GraphState


def web_search_disabled_notice(state: GraphState):
    """
    Terminal node for privacy mode.

    Reached only when the answer is grounded but does not fully answer the
    question, and web search is disabled so no more information can be added.
    Records a machine-readable stop reason so the caller (main.py) can attach
    a user-facing caveat to the final answer. The generation itself is left
    untouched.
    """

    print("---WEB SEARCH DISABLED: ANSWER LIMITED TO LOCAL KNOWLEDGE BASE---")

    return {"stop_reason": STOP_REASON_WEB_SEARCH_DISABLED}
