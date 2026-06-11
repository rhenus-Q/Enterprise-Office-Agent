from functools import lru_cache

from langchain_core.documents import Document
from langchain_community.tools.tavily_search import TavilySearchResults

from graph.chains.retrieval_grader import get_retrieval_grader
from graph.state import GraphState


@lru_cache(maxsize=1)
def get_web_search_tool():
    """
    Lazily build and cache the Tavily search tool.
    Deferring construction keeps module import free of Tavily API-key validation,
    which also makes the web_search node easy to mock in tests.
    """

    # max_results is the correct argument for TavilySearchResults; the old k= was ignored.
    return TavilySearchResults(max_results=3)


def _extract_result_contents(search_results):
    """
    Defensively pull text contents out of a Tavily response.

    Tavily normally returns a list of dicts with a "content" key, but error
    responses can be a plain string, and entries may be malformed. Anything
    unusable is skipped instead of crashing the node.
    """

    if not isinstance(search_results, list):
        return []

    contents = []
    for result in search_results:
        if not isinstance(result, dict):
            continue
        content = result.get("content")
        if isinstance(content, str) and content.strip():
            contents.append(content)

    return contents


def web_search(state: GraphState):
    """
    Run a web search to supplement the documents.

    External web content is less trusted than the curated knowledge base, so
    each search result is graded for relevance against the question (reusing
    the same retrieval grader the internal chunks pass through) before it is
    used. Only relevant results are merged into a Document and appended; if
    nothing relevant (or nothing usable) comes back, the documents are
    returned unchanged and the workflow continues safely.
    """

    print("---WEB SEARCH---")

    question = state["question"]

    # Retry rounds rewrite the query (search_query); first-pass searches use
    # the original question. Relevance below is always graded against the
    # original question, since that is the intent the results must serve.
    search_query = state.get("search_query") or question

    # Drop any previous web supplement instead of stacking near-duplicates:
    # on retry rounds only the freshest web content should feed generation.
    # (Also copies the list, so state is never mutated in place.)
    documents = [
        doc
        for doc in state.get("documents", [])
        if doc.metadata.get("source") != "web_search"
    ]

    search_results = get_web_search_tool().invoke({"query": search_query})

    contents = _extract_result_contents(search_results)

    if not contents:
        print("---WEB SEARCH RETURNED NO USABLE RESULTS---")
        return {
            "question": question,
            "documents": documents,
        }

    grader = get_retrieval_grader()
    relevant_contents = []

    for content in contents:
        score = grader.invoke(
            {
                "question": question,
                "document": content,
            }
        )

        if score.is_relevant:
            print("---WEB RESULT RELEVANT---")
            relevant_contents.append(content)
        else:
            print("---WEB RESULT NOT RELEVANT, DROPPED---")

    if not relevant_contents:
        print("---NO RELEVANT WEB RESULTS, NOTHING APPENDED---")
        return {
            "question": question,
            "documents": documents,
        }

    web_document = Document(
        page_content="\n\n".join(relevant_contents),
        metadata={"source": "web_search"},
    )

    documents.append(web_document)

    return {
        "question": question,
        "documents": documents,
    }
