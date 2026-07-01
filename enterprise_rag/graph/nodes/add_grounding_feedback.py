from enterprise_rag.graph.state import GraphState

# Corrective instruction injected into the next generation attempt after a
# failed grounding check. Folding this into the generation input makes the
# retry meaningfully different from the previous attempt (temperature=0 would
# otherwise mostly reproduce the same ungrounded answer).
GROUNDING_FEEDBACK = (
    "The previous answer was not grounded in the provided documents. "
    "Regenerate the answer using only facts that are explicitly supported by "
    "the documents. If the documents do not contain enough information to "
    "answer, say so instead of guessing."
)


def add_grounding_feedback(state: GraphState):
    """
    Pass-through node on the not_grounded retry path.

    Records corrective feedback in state so the next generate call receives a
    different, stricter input. Kept as a node (not done inside the routing
    function) so conditional edges stay pure.
    """

    print("---ADD GROUNDING FEEDBACK FOR RETRY---")

    return {"retry_feedback": GROUNDING_FEEDBACK}
