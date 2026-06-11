from graph.state import GraphState
from graph.chains.generation import generate_answer


def generate(state: GraphState):
    """
    Generate an answer from the question + documents.
    """

    print("---GENERATE---")

    question = state["question"]
    documents = state.get("documents", [])

    # Increment on every generation. The quality-check loop (regenerate / web search)
    # returns here repeatedly, so this counter caps the loop. On the first pass
    # state has no retries yet, so fall back to 0 via get.
    retries = state.get("retries", 0) + 1

    # Corrective feedback from a failed grounding check (empty on first pass)
    # makes the retry input meaningfully different from the previous attempt.
    retry_feedback = state.get("retry_feedback", "")

    generation = generate_answer(question, documents, retry_feedback)

    return {
        "question": question,
        "documents": documents,
        "generation": generation,
        "web_search": state.get("web_search", False),
        "retries": retries,
    }