"""
Unit tests for the web_search node (enterprise_rag/graph/nodes/web_search.py).

The Tavily tool AND the retrieval grader are mocked via monkeypatch (patching
get_web_search_tool / get_retrieval_grader), so no real web search or OpenAI
call happens. Tests focus on node state input/output and on the relevance
gate applied to external web results before they are appended.
"""

import importlib

from langchain_core.documents import Document

from enterprise_rag.graph.consts import (
    STOP_REASON_RETRIEVAL_ERROR,
    STOP_REASON_TOOL_ERROR,
    STOP_REASON_WEB_SEARCH_ERROR,
)
from enterprise_rag.graph.formatting import format_sources
from enterprise_rag.graph.nodes.web_search import web_search

# enterprise_rag/graph/nodes/__init__.py re-exports the `web_search` function under the same name
# as its submodule, so `import enterprise_rag.graph.nodes.web_search as ...` would bind the
# function, not the module. Resolve the real module for monkeypatching.
web_search_module = importlib.import_module("enterprise_rag.graph.nodes.web_search")


def _patch_tool(monkeypatch, results):
    """Patch get_web_search_tool to return a fake tool recording the payload."""

    calls = {}

    class FakeTool:
        def invoke(self, payload):
            calls["payload"] = payload
            return results

    monkeypatch.setattr(web_search_module, "get_web_search_tool", lambda: FakeTool())
    return calls


class _FakeGrade:
    """Stand-in for RetrievalGrade with just the .is_relevant field the node reads."""

    def __init__(self, is_relevant):
        self.is_relevant = is_relevant


def _patch_grader(monkeypatch, relevance_by_content=None, default=True):
    """
    Patch the grader seam. Relevance comes from a content -> bool map (falling
    back to `default`), and every grading payload is recorded for assertions.
    """

    grader_calls = []

    class FakeGrader:
        def invoke(self, payload):
            grader_calls.append(payload)
            content = payload["document"]
            if relevance_by_content and content in relevance_by_content:
                return _FakeGrade(relevance_by_content[content])
            return _FakeGrade(default)

    monkeypatch.setattr(web_search_module, "get_retrieval_grader", lambda: FakeGrader())
    return grader_calls


# ---------------------------------------------------------------------------
# Baseline behavior (relevant results)
# ---------------------------------------------------------------------------


def test_web_search_reads_question_from_state(monkeypatch):
    calls = _patch_tool(monkeypatch, [{"content": "result"}])
    _patch_grader(monkeypatch)

    web_search({"question": "What is RAG?", "documents": []})

    assert calls["payload"] == {"query": "What is RAG?"}


def test_web_search_appends_document_built_from_relevant_results(monkeypatch):
    _patch_tool(monkeypatch, [{"content": "alpha"}, {"content": "beta"}])
    _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    assert len(result["documents"]) == 1
    web_doc = result["documents"][0]
    assert isinstance(web_doc, Document)
    assert "alpha" in web_doc.page_content
    assert "beta" in web_doc.page_content
    assert web_doc.metadata["source"] == "web_search"


def test_web_search_preserves_existing_documents_and_appends(monkeypatch):
    _patch_tool(monkeypatch, [{"content": "web"}])
    _patch_grader(monkeypatch)

    existing = Document(page_content="existing")
    result = web_search({"question": "Q", "documents": [existing]})

    assert len(result["documents"]) == 2
    assert result["documents"][0] is existing  # existing kept, first
    assert result["documents"][-1].metadata["source"] == "web_search"  # web result appended last


def test_web_search_preserves_question(monkeypatch):
    _patch_tool(monkeypatch, [{"content": "web"}])
    _patch_grader(monkeypatch)

    result = web_search({"question": "keep me", "documents": []})

    assert result["question"] == "keep me"


def test_web_search_document_carries_provenance_metadata(monkeypatch):
    # The web supplement records which query produced it, so main.py can show
    # it in the user-facing Sources section.
    _patch_tool(monkeypatch, [{"content": "web"}])
    _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "search_query": "rewritten query", "documents": []})

    metadata = result["documents"][0].metadata
    assert metadata["source"] == "web_search"
    assert metadata["source_type"] == "web"
    assert metadata["search_query"] == "rewritten query"


def test_web_search_metadata_records_question_when_no_rewrite(monkeypatch):
    _patch_tool(monkeypatch, [{"content": "web"}])
    _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    assert result["documents"][0].metadata["search_query"] == "Q"


# ---------------------------------------------------------------------------
# Rewritten search query + replacement of stale web supplements
# ---------------------------------------------------------------------------


def test_web_search_uses_search_query_when_present(monkeypatch):
    calls = _patch_tool(monkeypatch, [{"content": "web"}])
    grader_calls = _patch_grader(monkeypatch)

    web_search({"question": "Q", "search_query": "rewritten query", "documents": []})

    assert calls["payload"] == {"query": "rewritten query"}
    # Relevance is still graded against the ORIGINAL question (the intent).
    assert grader_calls[0]["question"] == "Q"


def test_web_search_falls_back_to_question_when_search_query_empty(monkeypatch):
    calls = _patch_tool(monkeypatch, [{"content": "web"}])
    _patch_grader(monkeypatch)

    web_search({"question": "Q", "search_query": "", "documents": []})

    assert calls["payload"] == {"query": "Q"}


def test_web_search_replaces_previous_web_supplement(monkeypatch):
    # Retry rounds must not stack near-duplicate web documents: the stale
    # web_search-sourced doc is dropped, other documents are preserved.
    _patch_tool(monkeypatch, [{"content": "fresh web content"}])
    _patch_grader(monkeypatch)

    stale_web = Document(page_content="old web", metadata={"source": "web_search"})
    internal = Document(page_content="internal chunk")

    result = web_search({"question": "Q", "documents": [internal, stale_web]})

    assert len(result["documents"]) == 2
    assert result["documents"][0] is internal
    assert result["documents"][1].page_content == "fresh web content"
    assert "old web" not in [d.page_content for d in result["documents"]]


# ---------------------------------------------------------------------------
# Relevance gate on web results
# ---------------------------------------------------------------------------


def test_web_search_grades_each_result_against_the_question(monkeypatch):
    _patch_tool(monkeypatch, [{"content": "alpha"}, {"content": "beta"}])
    grader_calls = _patch_grader(monkeypatch)

    web_search({"question": "What is RAG?", "documents": []})

    assert [c["document"] for c in grader_calls] == ["alpha", "beta"]
    assert all(c["question"] == "What is RAG?" for c in grader_calls)


def test_web_search_drops_irrelevant_results(monkeypatch):
    _patch_tool(monkeypatch, [{"content": "spam"}, {"content": "ads"}])
    _patch_grader(monkeypatch, {"spam": False, "ads": False})

    existing = Document(page_content="existing")
    result = web_search({"question": "Q", "documents": [existing]})

    assert result["documents"] == [existing]  # nothing appended


def test_web_search_mixed_results_appends_only_relevant_content(monkeypatch):
    _patch_tool(monkeypatch, [{"content": "useful"}, {"content": "noise"}])
    _patch_grader(monkeypatch, {"useful": True, "noise": False})

    result = web_search({"question": "Q", "documents": []})

    assert len(result["documents"]) == 1
    web_doc = result["documents"][0]
    assert "useful" in web_doc.page_content
    assert "noise" not in web_doc.page_content
    assert web_doc.metadata["source"] == "web_search"


# ---------------------------------------------------------------------------
# Page-level provenance (web_sources metadata) + dict-shaped Tavily responses
# ---------------------------------------------------------------------------


def test_web_search_stores_url_and_title_for_relevant_results(monkeypatch):
    _patch_tool(
        monkeypatch,
        [
            {"content": "alpha", "url": "https://a.example", "title": "Page A"},
            {"content": "beta", "url": "https://b.example", "title": "Page B"},
        ],
    )
    _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    assert result["documents"][0].metadata["web_sources"] == [
        {"title": "Page A", "url": "https://a.example"},
        {"title": "Page B", "url": "https://b.example"},
    ]


def test_web_search_excludes_irrelevant_results_from_web_sources(monkeypatch):
    _patch_tool(
        monkeypatch,
        [
            {"content": "useful", "url": "https://keep.example", "title": "Keep"},
            {"content": "noise", "url": "https://drop.example", "title": "Drop"},
        ],
    )
    _patch_grader(monkeypatch, {"useful": True, "noise": False})

    result = web_search({"question": "Q", "documents": []})

    assert result["documents"][0].metadata["web_sources"] == [
        {"title": "Keep", "url": "https://keep.example"}
    ]


def test_web_search_deduplicates_web_source_urls(monkeypatch):
    _patch_tool(
        monkeypatch,
        [
            {"content": "part one", "url": "https://same.example", "title": "Same Page"},
            {"content": "part two", "url": "https://same.example", "title": "Same Page (cached)"},
        ],
    )
    _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    web_doc = result["documents"][0]
    # Both relevant contents are kept; the page is cited once (first title wins).
    assert "part one" in web_doc.page_content
    assert "part two" in web_doc.page_content
    assert web_doc.metadata["web_sources"] == [
        {"title": "Same Page", "url": "https://same.example"}
    ]


def test_web_search_results_without_urls_yield_empty_web_sources(monkeypatch):
    # Provenance falls back to the query-level citation downstream.
    _patch_tool(monkeypatch, [{"content": "no url here"}])
    _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    assert result["documents"][0].metadata["web_sources"] == []
    assert result["documents"][0].metadata["search_query"] == "Q"


def test_web_search_parses_dict_shaped_tavily_response(monkeypatch):
    # langchain-tavily's TavilySearch returns {"results": [...]} rather than a
    # bare list; both shapes must work.
    _patch_tool(
        monkeypatch,
        {
            "query": "Q",
            "results": [{"content": "alpha", "url": "https://a.example", "title": "Page A"}],
            "response_time": 0.5,
        },
    )
    _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    assert len(result["documents"]) == 1
    assert result["documents"][0].page_content == "alpha"
    assert result["documents"][0].metadata["web_sources"] == [
        {"title": "Page A", "url": "https://a.example"}
    ]


def test_web_search_handles_error_dict_response_without_crashing(monkeypatch):
    # langchain-tavily returns {"error": ...} on wrapped failures.
    _patch_tool(monkeypatch, {"error": "rate limited"})
    grader_calls = _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    assert result["documents"] == []
    assert grader_calls == []


# ---------------------------------------------------------------------------
# Per-run budgets: search guard, search counter, grading cap
# ---------------------------------------------------------------------------


def test_web_search_increments_counters(monkeypatch):
    _patch_tool(monkeypatch, [{"content": "alpha"}, {"content": "beta"}])
    _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    assert result["web_search_count"] == 1
    assert result["web_result_grading_count"] == 2  # one per graded result
    assert result["llm_call_count"] == 2  # grading calls are LLM calls


def test_web_search_skipped_when_search_budget_exhausted(monkeypatch):
    # web_search_count already at the default budget (5): the tool must not be
    # invoked, and existing documents (incl. a vetted web supplement) survive.
    monkeypatch.delenv("MAX_WEB_SEARCHES_PER_RUN", raising=False)
    calls = _patch_tool(monkeypatch, [{"content": "web"}])
    grader_calls = _patch_grader(monkeypatch)

    old_web = Document(page_content="old web", metadata={"source": "web_search"})
    result = web_search({"question": "Q", "documents": [old_web], "web_search_count": 5})

    assert "payload" not in calls  # Tavily never called
    assert grader_calls == []  # no grading either
    assert result["documents"] == [old_web]


def test_web_search_grading_cap_drops_remaining_results(monkeypatch):
    # With a grading budget of 1, only the first result is graded; the rest
    # are dropped without reaching the grader or the context.
    monkeypatch.setenv("MAX_WEB_RESULTS_TO_GRADE", "1")
    _patch_tool(monkeypatch, [{"content": "first"}, {"content": "second"}, {"content": "third"}])
    grader_calls = _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    assert [c["document"] for c in grader_calls] == ["first"]
    assert result["web_result_grading_count"] == 1
    assert len(result["documents"]) == 1
    assert result["documents"][0].page_content == "first"
    assert "second" not in result["documents"][0].page_content


# ---------------------------------------------------------------------------
# Defensive handling of empty / malformed Tavily responses
# ---------------------------------------------------------------------------


def test_web_search_handles_string_error_response_without_crashing(monkeypatch):
    # Tavily error responses can be a plain string instead of a result list.
    _patch_tool(monkeypatch, "HTTPError: 502 Bad Gateway")
    grader_calls = _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    assert result["documents"] == []
    assert grader_calls == []  # nothing usable, the grader LLM is never invoked


def test_web_search_handles_empty_result_list(monkeypatch):
    _patch_tool(monkeypatch, [])
    grader_calls = _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    assert result["documents"] == []
    assert grader_calls == []


def test_web_search_skips_malformed_entries_and_keeps_usable_ones(monkeypatch):
    _patch_tool(
        monkeypatch,
        [
            "not-a-dict",
            {"url": "https://example.com"},  # missing "content"
            {"content": ""},  # empty content
            {"content": "   "},  # whitespace-only content
            {"content": 42},  # non-string content
            {"content": "good result"},
        ],
    )
    grader_calls = _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    assert [c["document"] for c in grader_calls] == ["good result"]
    assert len(result["documents"]) == 1
    assert result["documents"][0].page_content == "good result"


# ---------------------------------------------------------------------------
# Graceful degradation: Tavily failures and grader failures
# ---------------------------------------------------------------------------


def _patch_failing_tool(monkeypatch):
    class ExplodingTool:
        def invoke(self, payload):
            raise TimeoutError("tavily timed out")

    monkeypatch.setattr(web_search_module, "get_web_search_tool", lambda: ExplodingTool())


def test_tavily_failure_preserves_local_documents(monkeypatch):
    _patch_failing_tool(monkeypatch)
    grader_calls = _patch_grader(monkeypatch)

    local = Document(page_content="local chunk")
    result = web_search({"question": "Q", "documents": [local]})  # must not raise

    assert result["documents"] == [local]  # local docs survive, nothing appended
    assert result["stop_reason"] == STOP_REASON_WEB_SEARCH_ERROR
    assert grader_calls == []  # nothing to grade


def test_tavily_failure_with_no_documents_returns_empty_context(monkeypatch):
    # Downstream, generate's empty-context short-circuit produces the safe
    # insufficient-context answer; the node just degrades cleanly.
    _patch_failing_tool(monkeypatch)
    _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    assert result["documents"] == []
    assert result["stop_reason"] == STOP_REASON_WEB_SEARCH_ERROR


def test_tavily_failure_counts_the_attempt_against_the_budget(monkeypatch):
    # A persistently failing search API must not enable unbounded retries.
    _patch_failing_tool(monkeypatch)
    _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": [], "web_search_count": 2})

    assert result["web_search_count"] == 3


def test_grader_failure_drops_only_the_ungraded_result(monkeypatch):
    _patch_tool(monkeypatch, [{"content": "boom"}, {"content": "good"}])

    class FlakyGrader:
        def invoke(self, payload):
            if payload["document"] == "boom":
                raise RuntimeError("grader is down")
            return _FakeGrade(True)

    monkeypatch.setattr(web_search_module, "get_retrieval_grader", lambda: FlakyGrader())

    result = web_search({"question": "Q", "documents": []})  # must not raise

    assert len(result["documents"]) == 1
    assert result["documents"][0].page_content == "good"  # ungraded content never appended
    assert result["stop_reason"] == STOP_REASON_TOOL_ERROR


def test_grader_failure_on_all_results_appends_nothing(monkeypatch):
    _patch_tool(monkeypatch, [{"content": "a"}, {"content": "b"}])

    class ExplodingGrader:
        def invoke(self, payload):
            raise RuntimeError("grader is down")

    monkeypatch.setattr(web_search_module, "get_retrieval_grader", lambda: ExplodingGrader())

    local = Document(page_content="local chunk")
    result = web_search({"question": "Q", "documents": [local]})

    assert result["documents"] == [local]
    assert result["stop_reason"] == STOP_REASON_TOOL_ERROR


def test_web_search_success_does_not_write_stop_reason(monkeypatch):
    # A normal pass must not clobber stop reasons recorded by other nodes.
    _patch_tool(monkeypatch, [{"content": "web"}])
    _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    assert "stop_reason" not in result


def test_grader_failure_preserves_existing_persistent_stop_reason(monkeypatch):
    # A transient per-result grading failure inside web_search must not
    # overwrite a persistent whole-source degradation (retrieval_error)
    # recorded upstream — that reason must survive to the final caveat.
    _patch_tool(monkeypatch, [{"content": "boom"}, {"content": "good"}])

    class FlakyGrader:
        def invoke(self, payload):
            if payload["document"] == "boom":
                raise RuntimeError("grader is down")
            return _FakeGrade(True)

    monkeypatch.setattr(web_search_module, "get_retrieval_grader", lambda: FlakyGrader())

    result = web_search(
        {"question": "Q", "documents": [], "stop_reason": STOP_REASON_RETRIEVAL_ERROR}
    )

    assert len(result["documents"]) == 1  # the ungraded result is still dropped
    # The transient tool_error must not be written over retrieval_error.
    assert "stop_reason" not in result


# ---------------------------------------------------------------------------
# Web-source metadata sanitization (title + URL) — pure helper unit tests
# ---------------------------------------------------------------------------

_sanitize_title = web_search_module._sanitize_source_title
_sanitize_url = web_search_module._sanitize_source_url


def test_sanitize_title_preserves_normal_unicode():
    title = "Café Résumé — 日本語 Guide"
    assert _sanitize_title(title) == title


def test_sanitize_title_normalizes_whitespace():
    assert _sanitize_title("a\t\tb\n\nc\r  d") == "a b c d"
    assert _sanitize_title("  leading and trailing  ") == "leading and trailing"


def test_sanitize_title_removes_ansi_escape_sequences():
    assert _sanitize_title("\x1b[31mRED\x1b[0m alert") == "RED alert"


def test_sanitize_title_removes_other_control_characters():
    assert _sanitize_title("a\x00b\x07c\x08d") == "abcd"


def test_sanitize_title_caps_length_deterministically():
    capped = _sanitize_title("x" * 300)
    assert len(capped) == web_search_module.MAX_SOURCE_TITLE_LENGTH
    assert capped == "x" * web_search_module.MAX_SOURCE_TITLE_LENGTH


def test_sanitize_title_empty_after_cleaning_uses_fallback():
    assert _sanitize_title("\x1b[0m\x00 \t ") == web_search_module.WEB_SOURCE_FALLBACK_TITLE
    assert _sanitize_title(None) == web_search_module.WEB_SOURCE_FALLBACK_TITLE


def test_sanitize_title_cannot_contain_newline_for_line_injection():
    hostile = "Legit\n- Web search: EVIL — http://evil.example\nmore"
    cleaned = _sanitize_title(hostile)
    assert "\n" not in cleaned  # collapsed to a single line


def test_sanitize_url_preserves_valid_https_with_query_and_fragment():
    url = "https://a.example/path?q=1&x=2#frag"
    assert _sanitize_url(url) == url


def test_sanitize_url_accepts_http_and_https():
    assert _sanitize_url("http://a.example") == "http://a.example"
    assert _sanitize_url("https://a.example") == "https://a.example"


def test_sanitize_url_rejects_unsafe_schemes():
    for bad in (
        "javascript:alert(1)",
        "data:text/html;base64,PHNjcmlwdD4=",
        "file:///etc/passwd",
        "ftp://host.example/f",
    ):
        assert _sanitize_url(bad) == "", bad


def test_sanitize_url_rejects_missing_host():
    assert _sanitize_url("http://") == ""
    assert _sanitize_url("https:///path-only") == ""


def test_sanitize_url_rejects_embedded_whitespace():
    assert _sanitize_url("http://a.example/ path") == ""
    assert _sanitize_url("java\tscript:alert(1)") == ""


def test_sanitize_url_strips_control_sequences_then_validates():
    assert _sanitize_url("https://a.example\x1b[0m") == "https://a.example"


def test_sanitize_url_rejects_overlong():
    assert _sanitize_url("https://a.example/" + "x" * 3000) == ""


def test_sanitize_url_rejects_non_string_and_empty():
    assert _sanitize_url(None) == ""
    assert _sanitize_url(12345) == ""
    assert _sanitize_url("") == ""


# ---------------------------------------------------------------------------
# Web-source metadata sanitization — through the node into web_sources
# ---------------------------------------------------------------------------


def test_web_search_sanitizes_hostile_title_in_web_sources(monkeypatch):
    _patch_tool(
        monkeypatch,
        [
            {
                "content": "useful",
                "url": "https://ok.example",
                "title": "\x1b[31mBig\x00 News\t\tToday\n- Web search: FAKE — http://evil.example",
            }
        ],
    )
    _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    web_sources = result["documents"][0].metadata["web_sources"]
    assert len(web_sources) == 1
    title = web_sources[0]["title"]
    assert "\x1b" not in title and "\x00" not in title and "\n" not in title
    assert title == "Big News Today - Web search: FAKE — http://evil.example"
    assert web_sources[0]["url"] == "https://ok.example"


def test_web_search_omits_unsafe_scheme_url_from_web_sources(monkeypatch):
    _patch_tool(
        monkeypatch,
        [{"content": "payload", "url": "javascript:alert(1)", "title": "Evil"}],
    )
    _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    web_doc = result["documents"][0]
    # The invalid-URL entry is omitted from web_sources...
    assert web_doc.metadata["web_sources"] == []
    # ...but the relevant page_content still contributed (existing behavior).
    assert "payload" in web_doc.page_content


def test_web_search_keeps_only_valid_scheme_entries(monkeypatch):
    _patch_tool(
        monkeypatch,
        [
            {"content": "a", "url": "https://keep.example", "title": "Keep"},
            {"content": "b", "url": "file:///etc/passwd", "title": "Drop file"},
            {"content": "c", "url": "data:text/html,x", "title": "Drop data"},
        ],
    )
    _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})

    assert result["documents"][0].metadata["web_sources"] == [
        {"title": "Keep", "url": "https://keep.example"}
    ]


def test_web_search_sanitized_metadata_reaches_formatted_sources(monkeypatch):
    _patch_tool(
        monkeypatch,
        [
            {
                "content": "useful",
                "url": "https://ok.example/a",
                "title": "Real\nTitle\x1b[0m",
            },
            {"content": "payload", "url": "javascript:alert(1)", "title": "Evil"},
        ],
    )
    _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})
    rendered = format_sources(result["documents"])

    # Exactly one web citation line (the hostile newline did not inject a second).
    web_lines = [ln for ln in rendered.splitlines() if ln.startswith("- Web search:")]
    assert web_lines == ["- Web search: Real Title — https://ok.example/a"]
    # The unsafe scheme and control bytes never reach the rendered output.
    assert "javascript:" not in rendered
    assert "\x1b" not in rendered


def test_web_search_hostile_title_cannot_inject_extra_source_line(monkeypatch):
    _patch_tool(
        monkeypatch,
        [
            {
                "content": "useful",
                "url": "https://ok.example",
                "title": "Title\n- Web search: INJECTED — https://evil.example",
            }
        ],
    )
    _patch_grader(monkeypatch)

    result = web_search({"question": "Q", "documents": []})
    web_lines = [
        ln
        for ln in format_sources(result["documents"]).splitlines()
        if ln.startswith("- Web search:")
    ]

    # One relevant result → exactly one citation line, despite the injected
    # newline+text in the title. The injected text survives only as inert title
    # text on that single line; the citation's actual URL is the safe one.
    assert len(web_lines) == 1
    assert web_lines[0].endswith("— https://ok.example")
