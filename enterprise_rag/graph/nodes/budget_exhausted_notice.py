from enterprise_rag.graph.consts import STOP_REASON_BUDGET_EXHAUSTED
from enterprise_rag.graph.state import GraphState


def budget_exhausted_notice(state: GraphState):
    """
    Terminal node: the per-run cost/latency budget was reached before the
    answer passed (or finished) the quality gates. Records a machine-readable
    stop reason so the caller (main.py) can warn the user that the answer may
    be incomplete or not fully verified. The generation itself is left
    untouched.
    """

    print("---BUDGET EXHAUSTED: STOPPING RUN---")

    return {"stop_reason": STOP_REASON_BUDGET_EXHAUSTED}
