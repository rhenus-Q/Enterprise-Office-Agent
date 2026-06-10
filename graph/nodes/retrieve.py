from functools import lru_cache

from ingestion import get_retriever
from graph.state import GraphState


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
    """

    print("---RETRIEVE---")

    question = state["question"]

    documents = get_node_retriever().invoke(question)

    return {
        "question": question,
        "documents": documents,
    }