"""
formatting.py

Deterministic presentation of a final graph state: stop-reason caveats and
the "Sources:" provenance section. Shared by the CLI (main.py), the eval
harness (evals/run_eval.py), and the engine API (graph/engine.py), so none
of them duplicate formatting logic and evals never import CLI-only code.

Pure module: no clients, no env reads, no LLM — only string building from
state and Document metadata.
"""

from graph.consts import (
    STOP_REASON_BUDGET_EXHAUSTED,
    STOP_REASON_GENERATION_ERROR,
    STOP_REASON_MAX_RETRIES_NOT_GROUNDED,
    STOP_REASON_MAX_RETRIES_NOT_USEFUL,
    STOP_REASON_RETRIEVAL_ERROR,
    STOP_REASON_TOOL_ERROR,
    STOP_REASON_WEB_FALLBACK_DISABLED,
    STOP_REASON_WEB_SEARCH_DISABLED,
    STOP_REASON_WEB_SEARCH_ERROR,
    WEB_SEARCH_SOURCE,
)


# Caveat shown when the workflow stopped because it would have needed web
# search, but web search is disabled (privacy mode).
WEB_SEARCH_DISABLED_NOTE = (
    "Note: Web search is disabled, so I could only use the local knowledge base. "
    "I may not have enough information to fully answer this question."
)

# Caveat shown when WEB_FALLBACK_POLICY=disabled stopped a local-only run
# from escalating to web search after its answer was judged not useful.
# Distinct from the privacy caveat: web search itself may be enabled.
WEB_FALLBACK_DISABLED_NOTE = (
    "Note: Web fallback is disabled by policy, so I answered only from the "
    "local knowledge base. The answer may not fully address your question."
)

# Caveat shown when the retry limit was reached and the final answer still
# failed the grounding (anti-hallucination) check.
MAX_RETRIES_NOT_GROUNDED_NOTE = (
    "Warning: This answer did not pass the grounding (anti-hallucination) check "
    "after the retry limit was reached. It may contain information that is not "
    "supported by the source documents, so do not treat it as fully reliable."
)

# Caveat shown when the retry limit was reached and the final answer is
# grounded but still failed the usefulness check.
MAX_RETRIES_NOT_USEFUL_NOTE = (
    "Warning: This answer did not pass the usefulness check after the retry "
    "limit was reached. It is grounded in the source documents but may not "
    "fully answer your question."
)

# Caveat shown when the per-run cost/latency budget stopped the run before
# the answer passed (or finished) the quality gates.
BUDGET_EXHAUSTED_NOTE = (
    "Note: This answer stopped because the per-run cost/latency budget was "
    "reached. The answer may be incomplete or not fully verified."
)

# Caveat shown when the local retriever (Chroma) failed; the run degraded to
# web search (or the insufficient-context answer in privacy mode).
RETRIEVAL_ERROR_NOTE = (
    "Note: Local document retrieval failed, so the answer may be incomplete "
    "or unavailable."
)

# Caveat shown when the web search call (Tavily) failed; the run continued
# with the local knowledge base only.
WEB_SEARCH_ERROR_NOTE = (
    "Note: Web search failed, so I answered only from the local knowledge "
    "base. The answer may be incomplete."
)

# Caveat shown when the generation LLM call itself failed; the answer above
# is a safe placeholder, not a real generated answer.
GENERATION_ERROR_NOTE = (
    "Note: The language model call failed before a reliable answer could be "
    "generated. Please try again."
)

# Caveat shown when an internal tool call (a grader or the query rewriter)
# failed; the answer may be missing dropped content or skipped verification.
TOOL_ERROR_NOTE = (
    "Note: An internal step failed during processing, so this answer may be "
    "incomplete or not fully verified."
)

# Maps a recorded stop reason to the caveat appended to the final answer.
STOP_REASON_NOTES = {
    STOP_REASON_WEB_SEARCH_DISABLED: WEB_SEARCH_DISABLED_NOTE,
    STOP_REASON_WEB_FALLBACK_DISABLED: WEB_FALLBACK_DISABLED_NOTE,
    STOP_REASON_MAX_RETRIES_NOT_GROUNDED: MAX_RETRIES_NOT_GROUNDED_NOTE,
    STOP_REASON_MAX_RETRIES_NOT_USEFUL: MAX_RETRIES_NOT_USEFUL_NOTE,
    STOP_REASON_BUDGET_EXHAUSTED: BUDGET_EXHAUSTED_NOTE,
    STOP_REASON_RETRIEVAL_ERROR: RETRIEVAL_ERROR_NOTE,
    STOP_REASON_WEB_SEARCH_ERROR: WEB_SEARCH_ERROR_NOTE,
    STOP_REASON_GENERATION_ERROR: GENERATION_ERROR_NOTE,
    STOP_REASON_TOOL_ERROR: TOOL_ERROR_NOTE,
}


# Sources section formatting. Deterministic, metadata-only (no LLM, no
# document content): keeps provenance testable and the prompts untouched.
SOURCES_HEADER = "Sources:"
LOCAL_SOURCE_FALLBACK_LABEL = "Local corpus document"
WEB_SOURCE_FALLBACK_LABEL = "Web search result"


def _web_source_lines(metadata) -> list:
    """
    Citation lines for the web supplement, best provenance first.

    Page-level when the websearch node recorded result URLs (web_sources):
    one line per page, "title — url" or the bare URL without a title. Falls
    back to the query-level citation ('Web search: "<query>"'), then to the
    generic safe label. Only metadata is read — never page content.
    """

    lines = []
    for entry in metadata.get("web_sources") or []:
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("url") or "").strip()
        if not url:
            continue
        title = str(entry.get("title") or "").strip()
        lines.append(f"- Web search: {title} — {url}" if title else f"- Web search: {url}")

    if lines:
        return lines

    query = str(metadata.get("search_query") or "").strip()
    if query:
        return [f'- Web search: "{query}"']

    return [f"- {WEB_SOURCE_FALLBACK_LABEL}"]


def source_lines(documents) -> list:
    """
    Deduplicated citation lines for the final working documents.

    Local corpus documents are labeled by their ingestion metadata (title,
    falling back to the source URL); the web supplement by the actual pages
    used (title — URL, recorded by the websearch node), falling back to the
    search query that produced it. Missing metadata falls back to safe
    generic labels, duplicate lines are collapsed (several chunks of one page
    cite it once), and document content is never exposed.
    """

    lines = []
    seen = set()

    for doc in documents or []:
        metadata = getattr(doc, "metadata", None) or {}

        if metadata.get("source") == WEB_SEARCH_SOURCE:
            doc_lines = _web_source_lines(metadata)
        else:
            label = str(metadata.get("title") or metadata.get("source") or "").strip()
            doc_lines = [f"- Local corpus: {label}" if label else f"- {LOCAL_SOURCE_FALLBACK_LABEL}"]

        for line in doc_lines:
            if line not in seen:
                seen.add(line)
                lines.append(line)

    return lines


def format_sources(documents) -> str:
    """
    Build the "Sources:" section from the final working documents.

    Returns "" when there is nothing to cite, so no misleading Sources
    section is shown.
    """

    lines = source_lines(documents)
    if not lines:
        return ""

    return SOURCES_HEADER + "\n" + "\n".join(lines)


def format_answer(result) -> str:
    """
    Format the final graph state for display.

    Appends a caveat when the graph recorded a stop reason, then a "Sources"
    section listing the provenance of the documents the answer was built
    from. The caveat is printed first, directly under the answer, so sources
    shown next to an error never imply the answer was fully verified. With
    no recorded stop reason and no documents the answer is returned
    unchanged.
    """

    answer = result.get("generation", "")

    parts = [answer]

    note = STOP_REASON_NOTES.get(result.get("stop_reason", ""))
    if note:
        parts.append(note)

    sources = format_sources(result.get("documents", []))
    if sources:
        parts.append(sources)

    return "\n\n".join(part for part in parts if part)
