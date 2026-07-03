import re
from functools import lru_cache
from urllib.parse import urlparse

from langchain_core.documents import Document
from langchain_tavily import TavilySearch

from enterprise_rag.graph.chains.retrieval_grader import get_retrieval_grader
from enterprise_rag.graph.config import max_web_results_to_grade, max_web_searches_per_run
from enterprise_rag.graph.consts import (
    STOP_REASON_TOOL_ERROR,
    STOP_REASON_WEB_SEARCH_ERROR,
    WEB_SEARCH_SOURCE,
)
from enterprise_rag.graph.state import GraphState

# --- Web-source metadata sanitization -------------------------------------
# Titles and URLs in web results are attacker-controlled external content. They
# are cleaned/validated here, at the single point where `web_sources` metadata is
# built, so the sanitized values flow unchanged into the Sources section, the
# engine trace source lines, and CLI output — no downstream renderer repeats this
# logic. Retrieved page_content is deliberately NOT sanitized here (only the
# citation metadata). All helpers are deterministic and side-effect-free.

# Maximum stored length of a web-source title: long enough for real page titles,
# short enough to keep one Sources line readable and to bound memory.
MAX_SOURCE_TITLE_LENGTH = 200

# Maximum accepted length of a web-source URL. Overlong URLs are rejected
# (omitted), never truncated — a truncated URL would be a broken, misleading link.
MAX_SOURCE_URL_LENGTH = 2048

# Stable fallback shown when a cited result's title sanitizes to empty.
WEB_SOURCE_FALLBACK_TITLE = "Web result"

# The only URL schemes allowed to appear in a citation.
_ALLOWED_URL_SCHEMES = ("http", "https")

# ANSI/VT CSI escape sequences (e.g. "\x1b[31m"): ESC "[" params intermediates
# final byte. Removed whole so an escape's payload never survives as visible text.
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")

# Control characters to delete outright: every C0 control EXCEPT the whitespace
# ones (\t \n \v \f \r — those are normalized to spaces by str.split() below),
# plus DEL and the C1 range. Also removes any lone ESC left by the ANSI pass.
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0e-\x1f\x7f-\x9f]")


def _strip_control_sequences(text: str) -> str:
    """Remove ANSI escape sequences, then non-whitespace control characters."""

    return _CONTROL_CHARS_RE.sub("", _ANSI_ESCAPE_RE.sub("", text))


def _sanitize_source_title(value) -> str:
    """Clean an external web-result title for safe citation.

    Strips ANSI escapes and control characters, normalizes tabs/newlines/repeated
    whitespace to single spaces, trims, caps the length deterministically, and
    falls back to a stable label when nothing usable remains. Normal Unicode text
    is preserved. Because all newlines are collapsed to spaces, a title can never
    inject an additional Sources line.
    """

    cleaned = _strip_control_sequences(str(value or ""))
    # split()/join collapses any remaining whitespace (incl. the tabs/newlines
    # kept above) into single spaces and trims leading/trailing runs.
    cleaned = " ".join(cleaned.split())
    if len(cleaned) > MAX_SOURCE_TITLE_LENGTH:
        cleaned = cleaned[:MAX_SOURCE_TITLE_LENGTH].rstrip()
    return cleaned or WEB_SOURCE_FALLBACK_TITLE


def _sanitize_source_url(value) -> str:
    """Validate an external web-result URL for safe citation.

    Returns a clean http(s) URL, or "" when the value is unusable: an unsafe
    scheme (only http/https accepted), a missing host, embedded whitespace or
    control characters, over length, or unparseable. Uses stdlib parsing only —
    it never resolves, fetches, or normalizes over the network. Valid query
    strings and fragments are preserved.
    """

    cleaned = _strip_control_sequences(str(value or "")).strip()
    # A well-formed URL has no internal whitespace; any remaining whitespace is
    # malformed/hostile (e.g. "java\tscript:"), so reject rather than repair.
    if not cleaned or any(ch.isspace() for ch in cleaned):
        return ""
    if len(cleaned) > MAX_SOURCE_URL_LENGTH:
        return ""
    try:
        parsed = urlparse(cleaned)
    except ValueError:
        return ""
    if parsed.scheme.lower() not in _ALLOWED_URL_SCHEMES:
        return ""
    if not parsed.netloc:
        return ""
    return cleaned


@lru_cache(maxsize=1)
def get_web_search_tool():
    """
    Lazily build and cache the Tavily search tool (langchain-tavily).
    Deferring construction keeps module import free of Tavily API-key validation,
    which also makes the web_search node easy to mock in tests.

    Timeout limitation (documented, not worked around): langchain-tavily 0.2.18
    issues its search via `requests.post(...)` with no timeout and exposes no
    public parameter to configure one — extra `.invoke()` kwargs become Tavily
    API request-body fields, not `requests` client options — so a request
    timeout cannot be wired here without patching library internals (avoided by
    design; no thread/signal/watchdog workaround). The per-run web-search budget
    still bounds the NUMBER of calls; the OpenAI embeddings path IS timed out via
    `external_request_timeout_seconds()` (see enterprise_rag/ingestion.py).
    """

    return TavilySearch(max_results=3)


def _extract_results(search_results):
    """
    Defensively pull usable results out of a Tavily response.

    langchain-tavily's TavilySearch returns a dict with a "results" list; the
    legacy community tool returned the list directly, and error responses can
    be a plain string or an {"error": ...} dict. Accept both shapes, skip
    anything malformed, and keep only entries with non-empty text content.
    Each usable entry is reduced to {"content", "url", "title"} ("" when a
    field is missing) so page-level provenance survives alongside the text.
    """

    if isinstance(search_results, dict):
        search_results = search_results.get("results")

    if not isinstance(search_results, list):
        return []

    results = []
    for result in search_results:
        if not isinstance(result, dict):
            continue
        content = result.get("content")
        if not (isinstance(content, str) and content.strip()):
            continue
        url = result.get("url")
        title = result.get("title")
        results.append(
            {
                "content": content,
                "url": url.strip() if isinstance(url, str) else "",
                "title": title.strip() if isinstance(title, str) else "",
            }
        )

    return results


def web_search(state: GraphState):
    """
    Run a web search to supplement the documents.

    External web content is less trusted than the curated knowledge base, so
    each search result is graded for relevance against the question (reusing
    the same retrieval grader the internal chunks pass through) before it is
    used. Only relevant results are merged into a Document and appended, with
    each contributing page's title/URL preserved in web_sources metadata for
    page-level provenance; if nothing relevant (or nothing usable) comes back,
    the documents are returned unchanged and the workflow continues safely.

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
        doc for doc in state.get("documents", []) if doc.metadata.get("source") != WEB_SEARCH_SOURCE
    ]

    try:
        search_results = get_web_search_tool().invoke({"query": search_query})
    except Exception as exc:
        # Log only the exception type: messages may carry secrets.
        print(
            f"---WEB SEARCH FAILED ({type(exc).__name__}): CONTINUING WITH LOCAL DOCUMENTS ONLY---"
        )
        return {
            "question": question,
            "documents": documents,
            # The failed attempt counts against the budget, so a persistently
            # failing search API cannot drive an unbounded retry loop.
            "web_search_count": web_search_count + 1,
            "stop_reason": STOP_REASON_WEB_SEARCH_ERROR,
        }
    web_search_count += 1

    results = _extract_results(search_results)

    if not results:
        print("---WEB SEARCH RETURNED NO USABLE RESULTS---")
        return {
            "question": question,
            "documents": documents,
            "web_search_count": web_search_count,
        }

    grader = get_retrieval_grader()
    relevant_results = []
    grading_budget = max_web_results_to_grade()
    grading_error = False

    for result in results:
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
                    "document": result["content"],
                }
            )
        except Exception as exc:
            # Conservative: an ungraded result is never trusted. Drop it and
            # keep grading the remaining results.
            print(
                f"---WEB RESULT GRADING FAILED ({type(exc).__name__}): DROPPING UNGRADED RESULT---"
            )
            grading_error = True
            continue

        if score.is_relevant:
            print("---WEB RESULT RELEVANT---")
            relevant_results.append(result)
        else:
            print("---WEB RESULT NOT RELEVANT, DROPPED---")

    if relevant_results:
        # Page-level provenance: one {"title", "url"} entry per relevant
        # result with a usable URL, deduplicated by URL order-preservingly.
        # Only vetted (relevant) results are cited — the Sources section must
        # never name a page whose content was dropped.
        web_sources = []
        seen_urls = set()
        for result in relevant_results:
            # Sanitize/validate at this single boundary: an entry is cited only
            # when its URL passes validation (safe http/https). The title is
            # cleaned; page_content and relevance are unaffected.
            safe_url = _sanitize_source_url(result["url"])
            if safe_url and safe_url not in seen_urls:
                seen_urls.add(safe_url)
                web_sources.append(
                    {"title": _sanitize_source_title(result["title"]), "url": safe_url}
                )

        documents.append(
            Document(
                page_content="\n\n".join(r["content"] for r in relevant_results),
                # Provenance metadata: source marks the doc as the web
                # supplement, search_query records the query that produced it,
                # web_sources lists the actual pages used (both shown in the
                # user-facing Sources section; the query is the fallback when
                # no result carried a URL).
                metadata={
                    "source": WEB_SEARCH_SOURCE,
                    "source_type": "web",
                    "search_query": search_query,
                    "web_sources": web_sources,
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
    # Record the transient tool_error only when no earlier reason is set: a
    # normal pass must not clobber a reason recorded by an earlier node, and a
    # transient per-result grading failure must not overwrite a persistent
    # whole-source degradation (e.g. retrieval_error) that the user should
    # still see in the final caveat.
    if grading_error and not state.get("stop_reason"):
        result["stop_reason"] = STOP_REASON_TOOL_ERROR
    return result
