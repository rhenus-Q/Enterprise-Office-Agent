from enterprise_rag.graph.consts import STOP_REASON_WEB_FALLBACK_DISABLED
from enterprise_rag.graph.state import GraphState


def web_fallback_disabled_notice(state: GraphState):
    """
    Terminal node for WEB_FALLBACK_POLICY=disabled.

    Reached when a run that stayed on the local retrieval path produced a
    grounded but not-useful answer, and the fallback policy forbids escalating
    a local run to web search (web search itself may be enabled — this is the
    policy, not the privacy switch). Records a machine-readable stop reason so
    the caller (main.py) can attach a user-facing caveat to the final answer.
    The generation itself is left untouched.
    """

    print("---WEB FALLBACK DISABLED BY POLICY: ANSWER LIMITED TO LOCAL KNOWLEDGE BASE---")

    return {"stop_reason": STOP_REASON_WEB_FALLBACK_DISABLED}
