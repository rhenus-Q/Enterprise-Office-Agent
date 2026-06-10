from graph.state import GraphState
from graph.chains.retrieval_grader import get_retrieval_grader


def grade_documents(state: GraphState):
    """
    Grade the relevance of documents returned by retrieve.
    Keep relevant documents; if any document is not relevant, set
    web_search=True so the workflow falls back to web search.
    """

    print("---GRADE DOCUMENTS---")

    question = state["question"]
    documents = state["documents"]

    filtered_docs = []
    web_search = False

    for doc in documents:
        score = get_retrieval_grader().invoke(
            {
                "question": question,
                "document": doc.page_content,
            }
        )

        grade = score.is_relevant

        if grade:
            print("---DOCUMENT RELEVANT---")
            filtered_docs.append(doc)
        else:
            print("---DOCUMENT NOT RELEVANT---")
            web_search = True

    return {
        "question": question,
        "documents": filtered_docs,
        "web_search": web_search,
    }