from enterprise_rag.graph.consts import STOP_REASON_TOOL_ERROR
from enterprise_rag.graph.state import GraphState


def tool_error_notice(state: GraphState):
    """
    Terminal node: an internal tool call (hallucination or answer grader)
    failed, so the answer could not be fully verified. Records a
    machine-readable stop reason so the caller (main.py) can warn the user
    instead of presenting the answer as verified. The generation itself is
    left untouched.
    """

    print("---TOOL ERROR: STOPPING RUN WITH AN UNVERIFIED ANSWER---")

    return {"stop_reason": STOP_REASON_TOOL_ERROR}
