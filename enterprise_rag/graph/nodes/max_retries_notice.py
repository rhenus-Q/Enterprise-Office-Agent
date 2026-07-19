from enterprise_rag.graph.consts import (
    STOP_REASON_MAX_RETRIES_NOT_GROUNDED,
    STOP_REASON_MAX_RETRIES_NOT_USEFUL,
)
from enterprise_rag.graph.state import GraphState


def max_retries_not_grounded_notice(state: GraphState):
    """
    Terminal node: the retry limit was reached and the latest answer still
    failed the grounding (anti-hallucination) check. Records a machine-readable
    stop reason so the caller (e.g. the CLI) can warn the user that the answer may
    contain unsupported content. The generation itself is left untouched.
    """

    print("---MAX RETRIES: ANSWER STILL NOT GROUNDED---")

    return {"stop_reason": STOP_REASON_MAX_RETRIES_NOT_GROUNDED}


def max_retries_not_useful_notice(state: GraphState):
    """
    Terminal node: the retry limit was reached and the latest answer is
    grounded but still failed the usefulness check. Records a machine-readable
    stop reason so the caller (e.g. the CLI) can warn the user that the answer may
    not fully address the question. The generation itself is left untouched.
    """

    print("---MAX RETRIES: ANSWER STILL NOT USEFUL---")

    return {"stop_reason": STOP_REASON_MAX_RETRIES_NOT_USEFUL}
