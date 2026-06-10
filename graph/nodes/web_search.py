from functools import lru_cache

from langchain_core.documents import Document
from langchain_community.tools.tavily_search import TavilySearchResults

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


def web_search(state: GraphState):
    """
    Run a web search to supplement the documents.
    Search results are converted into a Document and appended to documents.
    """

    print("---WEB SEARCH---")

    question = state["question"]
    # Copy the list to avoid mutating state in place (prefer value updates for LangGraph state).
    documents = list(state.get("documents", []))

    search_results = get_web_search_tool().invoke({"query": question})

    web_content = "\n\n".join(
        result["content"] for result in search_results
    )

    web_document = Document(
        page_content=web_content,
        metadata={"source": "web_search"},
    )

    documents.append(web_document)

    return {
        "question": question,
        "documents": documents,
    }