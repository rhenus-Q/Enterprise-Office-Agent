from graph.consts import STOP_REASON_GENERATION_ERROR
from graph.state import GraphState
from graph.chains.generation import generate_answer


# Safe replacement answer when the generation LLM call itself fails.
# Deliberately deterministic and content-free: a failed call must never be
# presented as (or mistaken for) a real grounded answer.
GENERATION_FAILED_ANSWER = (
    "I could not generate an answer because the language model request failed. "
    "Please try again."
)


def generate(state: GraphState):
    """
    Generate an answer from the question + documents.

    A generation LLM failure must not crash the run: the node returns a safe
    deterministic answer and records stop_reason=generation_error, which
    grade_generation routes straight to END — the failed generation is never
    graded or presented as a normal successful answer.
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

    # Budget accounting: generate_answer only calls the LLM when context
    # exists; the empty-context short-circuit costs nothing.
    llm_call_count = state.get("llm_call_count", 0)
    if documents:
        llm_call_count += 1

    try:
        generation = generate_answer(question, documents, retry_feedback)
    except Exception as exc:
        # Log only the exception type: messages may carry secrets.
        print(f"---GENERATION FAILED ({type(exc).__name__}): STOPPING WITH A SAFE ANSWER---")
        return {
            "question": question,
            "documents": documents,
            "generation": GENERATION_FAILED_ANSWER,
            "web_search": state.get("web_search", False),
            "retries": retries,
            # The failed attempt was still a real API call; count it.
            "llm_call_count": llm_call_count,
            "stop_reason": STOP_REASON_GENERATION_ERROR,
        }

    return {
        "question": question,
        "documents": documents,
        "generation": generation,
        "web_search": state.get("web_search", False),
        "retries": retries,
        "llm_call_count": llm_call_count,
    }