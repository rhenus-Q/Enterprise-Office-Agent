"""
Unit tests for the rewrite_query node (enterprise_rag/graph/nodes/rewrite_query.py).

The query rewriter chain is mocked via monkeypatch (patching
get_query_rewriter), so no real OpenAI call happens. Tests focus on node
state input/output and on graceful degradation when the rewriter fails.
"""

import importlib

from enterprise_rag.graph.consts import STOP_REASON_RETRIEVAL_ERROR, STOP_REASON_TOOL_ERROR
from enterprise_rag.graph.nodes.rewrite_query import rewrite_query

# enterprise_rag/graph/nodes/__init__.py re-exports the `rewrite_query` function under the same
# name as its submodule, so `import enterprise_rag.graph.nodes.rewrite_query as ...` would bind
# the function, not the module. Resolve the real module for monkeypatching.
rewrite_module = importlib.import_module("enterprise_rag.graph.nodes.rewrite_query")


def _patch_rewriter(monkeypatch, new_query="rewritten query"):
    """Patch get_query_rewriter to return a fake chain recording the payload."""

    calls = {}

    class FakeRewriter:
        def invoke(self, payload):
            calls["payload"] = payload
            return new_query

    monkeypatch.setattr(rewrite_module, "get_query_rewriter", lambda: FakeRewriter())
    return calls


def _patch_failing_rewriter(monkeypatch):
    class ExplodingRewriter:
        def invoke(self, payload):
            raise RuntimeError("openai is down")

    monkeypatch.setattr(rewrite_module, "get_query_rewriter", lambda: ExplodingRewriter())


# ---------------------------------------------------------------------------
# Baseline behavior
# ---------------------------------------------------------------------------


def test_rewrite_query_passes_question_and_previous_answer(monkeypatch):
    calls = _patch_rewriter(monkeypatch)

    rewrite_query({"question": "Q", "generation": "previous answer"})

    assert calls["payload"] == {"question": "Q", "previous_answer": "previous answer"}


def test_rewrite_query_writes_stripped_search_query_and_counts_the_call(monkeypatch):
    _patch_rewriter(monkeypatch, new_query="  better query  ")

    result = rewrite_query({"question": "Q", "generation": "A", "llm_call_count": 3})

    assert result["search_query"] == "better query"
    assert result["llm_call_count"] == 4


def test_rewrite_query_success_does_not_write_stop_reason(monkeypatch):
    _patch_rewriter(monkeypatch)

    result = rewrite_query({"question": "Q", "generation": "A"})

    assert "stop_reason" not in result


def test_rewrite_query_does_not_log_query_or_input_content(monkeypatch, capsys):
    """The success banner is metadata-only: the rewritten query, the original
    question, and the previous answer must never reach stdout (console logs may
    be aggregated in production), while the query is still returned in state."""

    sensitive_query = "CONFIRMED-SENSITIVE-REWRITE-sk-live-0123456789"
    _patch_rewriter(monkeypatch, new_query=sensitive_query)

    result = rewrite_query(
        {
            "question": "CONFIRMED-SENSITIVE-QUESTION",
            "generation": "CONFIRMED-SENSITIVE-PREVIOUS-ANSWER",
        }
    )

    out = capsys.readouterr().out
    # A fixed, metadata-only banner is emitted...
    assert "---SEARCH QUERY REWRITTEN---" in out
    # ...but no content-bearing value leaks into stdout.
    assert sensitive_query not in out
    assert "CONFIRMED-SENSITIVE-QUESTION" not in out
    assert "CONFIRMED-SENSITIVE-PREVIOUS-ANSWER" not in out
    # The rewritten query is still returned in state for the next web search.
    assert result["search_query"] == sensitive_query


# ---------------------------------------------------------------------------
# Graceful degradation: rewriter failure
# ---------------------------------------------------------------------------


def test_rewriter_failure_falls_back_to_the_original_question(monkeypatch):
    _patch_failing_rewriter(monkeypatch)

    result = rewrite_query({"question": "Q", "generation": "A"})  # must not raise

    # search_query="" means the web_search node uses the original question.
    assert result["search_query"] == ""
    assert result["stop_reason"] == STOP_REASON_TOOL_ERROR


def test_rewriter_failure_still_counts_the_llm_call(monkeypatch):
    _patch_failing_rewriter(monkeypatch)

    result = rewrite_query({"question": "Q", "generation": "A", "llm_call_count": 3})

    assert result["llm_call_count"] == 4


def test_rewriter_failure_preserves_existing_persistent_stop_reason(monkeypatch):
    # A transient rewrite failure must not overwrite a persistent whole-source
    # degradation (retrieval_error) recorded upstream — that reason must
    # survive to the final caveat.
    _patch_failing_rewriter(monkeypatch)

    result = rewrite_query(
        {"question": "Q", "generation": "A", "stop_reason": STOP_REASON_RETRIEVAL_ERROR}
    )

    assert result["search_query"] == ""  # still falls back to the original question
    assert result["llm_call_count"] == 1  # the failed attempt is still counted
    # The transient tool_error must not clobber the persistent reason.
    assert "stop_reason" not in result
