from functools import lru_cache

from graph.consts import STOP_REASON_RETRIEVAL_ERROR
from graph.state import GraphState
from ingestion import get_retriever


@lru_cache(maxsize=1)
def get_node_retriever():
    """
    Lazily build and cache the retriever.
    Deferring construction keeps module import free of Chroma / embeddings side
    effects, which also makes the retrieve node easy to mock in tests.
    """

    return get_retriever()


def retrieve(state: GraphState):
    """
    Retrieve documents relevant to the user question from the vector store.

    A retriever / Chroma failure must not crash the run: it degrades to the
    existing web-search fallback (web_search=True, same mechanism as
    irrelevant documents) and records stop_reason so main.py can warn the
    user that local retrieval failed. In privacy mode the fallback is ignored
    and generation returns the deterministic insufficient-context answer.
    """

    print("---RETRIEVE---")

    question = state["question"]

    try:
        documents = get_node_retriever().invoke(question)
    except Exception as exc:
        # Log only the exception type: messages may carry paths or secrets.
        print(
            f"---RETRIEVAL FAILED ({type(exc).__name__}): FALLING BACK WITHOUT LOCAL DOCUMENTS---"
        )
        return {
            "question": question,
            "documents": [],
            "web_search": True,
            "stop_reason": STOP_REASON_RETRIEVAL_ERROR,
        }

    return {
        "question": question,
        "documents": documents,
    }
