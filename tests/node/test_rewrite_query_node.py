"""
Unit tests for the rewrite_query node (graph/nodes/rewrite_query.py).

The query rewriter chain is mocked via monkeypatch (patching
get_query_rewriter), so no real OpenAI call happens. Tests focus on node
state input/output and on graceful degradation when the rewriter fails.
"""

import importlib

from graph.consts import STOP_REASON_TOOL_ERROR
from graph.nodes.rewrite_query import rewrite_query

# graph/nodes/__init__.py re-exports the `rewrite_query` function under the same
# name as its submodule, so `import graph.nodes.rewrite_query as ...` would bind
# the function, not the module. Resolve the real module for monkeypatching.
rewrite_module = importlib.import_module("graph.nodes.rewrite_query")


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
