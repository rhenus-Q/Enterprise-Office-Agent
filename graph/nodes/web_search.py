from functools import lru_cache

from langchain_core.documents import Document
from langchain_community.tools.tavily_search import TavilySearchResults

from graph.chains.retrieval_grader import get_retrieval_grader
from graph.config import max_web_results_to_grade, max_web_searches_per_run
from graph.consts import (
    STOP_REASON_TOOL_ERROR,
    STOP_REASON_WEB_SEARCH_ERROR,
    WEB_SEARCH_SOURCE,
)
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

    External failures must not crash the run:
    - A Tavily failure (timeout / API error) continues with the local
      documents only and records stop_reason=web_search_error; the attempt
      still counts against the web-search budget so a flaky API cannot
      cause unbounded retries.
    - A grader failure on an individual result drops that result ungraded
      (unvetted web content never reaches generation) and records
      stop_reason=tool_error; remaining results are still graded.
    """

    print("---WEB SEARCH---")

    question = state["question"]

    web_search_count = state.get("web_search_count", 0)
    web_result_grading_count = state.get("web_result_grading_count", 0)
    llm_call_count = state.get("llm_call_count", 0)

    # Per-run budget guard: covers every path into this node, including
    # pathological configurations. Documents (including any previous, already
    # vetted web supplement) pass through unchanged.
    if web_search_count >= max_web_searches_per_run():
        print("---WEB SEARCH BUDGET EXHAUSTED, SKIPPING SEARCH---")
        return {
            "question": question,
            "documents": list(state.get("documents", [])),
        }

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
        if doc.metadata.get("source") != WEB_SEARCH_SOURCE
    ]

    try:
        search_results = get_web_search_tool().invoke({"query": search_query})
    except Exception as exc:
        # Log only the exception type: messages may carry secrets.
        print(f"---WEB SEARCH FAILED ({type(exc).__name__}): CONTINUING WITH LOCAL DOCUMENTS ONLY---")
        return {
            "question": question,
            "documents": documents,
            # The failed attempt counts against the budget, so a persistently
            # failing search API cannot drive an unbounded retry loop.
            "web_search_count": web_search_count + 1,
            "stop_reason": STOP_REASON_WEB_SEARCH_ERROR,
        }
    web_search_count += 1

    contents = _extract_result_contents(search_results)

    if not contents:
        print("---WEB SEARCH RETURNED NO USABLE RESULTS---")
        return {
            "question": question,
            "documents": documents,
            "web_search_count": web_search_count,
        }

    grader = get_retrieval_grader()
    relevant_contents = []
    grading_budget = max_web_results_to_grade()
    grading_error = False

    for content in contents:
        # Conservative budget behavior: once the grading budget is spent,
        # remaining results are dropped — ungraded web content never reaches
        # generation. The run itself continues with what was vetted.
        if web_result_grading_count >= grading_budget:
            print("---WEB RESULT GRADING BUDGET EXHAUSTED, DROPPING REMAINING RESULTS---")
            break

        web_result_grading_count += 1
        llm_call_count += 1

        try:
            score = grader.invoke(
                {
                    "question": question,
                    "document": content,
                }
            )
        except Exception as exc:
            # Conservative: an ungraded result is never trusted. Drop it and
            # keep grading the remaining results.
            print(f"---WEB RESULT GRADING FAILED ({type(exc).__name__}): DROPPING UNGRADED RESULT---")
            grading_error = True
            continue

        if score.is_relevant:
            print("---WEB RESULT RELEVANT---")
            relevant_contents.append(content)
        else:
            print("---WEB RESULT NOT RELEVANT, DROPPED---")

    if relevant_contents:
        documents.append(
            Document(
                page_content="\n\n".join(relevant_contents),
                # Provenance metadata: source marks the doc as the web
                # supplement, search_query records the query that produced it
                # (shown in the user-facing Sources section).
                metadata={
                    "source": WEB_SEARCH_SOURCE,
                    "source_type": "web",
                    "search_query": search_query,
                },
            )
        )
    else:
        print("---NO RELEVANT WEB RESULTS, NOTHING APPENDED---")

    result = {
        "question": question,
        "documents": documents,
        "web_search_count": web_search_count,
        "web_result_grading_count": web_result_grading_count,
        "llm_call_count": llm_call_count,
    }
    # Only write stop_reason on failure: a normal pass must not clobber a
    # reason recorded by an earlier node.
    if grading_error:
        result["stop_reason"] = STOP_REASON_TOOL_ERROR
    return result
