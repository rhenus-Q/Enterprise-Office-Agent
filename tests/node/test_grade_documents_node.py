"""
Unit tests for the grade_documents node (graph/nodes/grade_documents.py).

retrieval_grader.invoke is mocked via monkeypatch, so no real OpenAI call happens.
Relevance is driven by a content -> bool mapping for deterministic results.
"""

from langchain_core.documents import Document

import importlib

from graph.consts import STOP_REASON_TOOL_ERROR
from graph.nodes.grade_documents import grade_documents

# graph/nodes/__init__.py re-exports the `grade_documents` function under the same
# name as its submodule, so `import graph.nodes.grade_documents as ...` would bind
# the function, not the module. Resolve the real module for monkeypatching.
grade_module = importlib.import_module("graph.nodes.grade_documents")


class _FakeGrade:
    """Stand-in for RetrievalGrade with just the .is_relevant field the node reads."""

    def __init__(self, is_relevant):
        self.is_relevant = is_relevant


def _patch_grader(monkeypatch, relevance_by_content):
    """Patch the grader seam so each document's grade comes from a content -> bool map."""

    class FakeGrader:
        def invoke(self, payload):
            content = payload["document"]
            return _FakeGrade(relevance_by_content[content])

    # grade_documents now calls get_retrieval_grader().invoke(...), so patch the getter.
    monkeypatch.setattr(grade_module, "get_retrieval_grader", lambda: FakeGrader())


def test_keeps_relevant_documents(monkeypatch):
    docs = [Document(page_content="relevant")]
    _patch_grader(monkeypatch, {"relevant": True})

    result = grade_documents({"question": "Q", "documents": docs})

    assert result["documents"] == docs
    assert result["web_search"] is False


def test_filters_out_irrelevant_documents(monkeypatch):
    keep = Document(page_content="relevant")
    drop = Document(page_content="irrelevant")
    _patch_grader(monkeypatch, {"relevant": True, "irrelevant": False})

    result = grade_documents({"question": "Q", "documents": [keep, drop]})

    assert result["documents"] == [keep]
    assert drop not in result["documents"]


def test_web_search_true_when_any_document_irrelevant(monkeypatch):
    keep = Document(page_content="relevant")
    drop = Document(page_content="irrelevant")
    _patch_grader(monkeypatch, {"relevant": True, "irrelevant": False})

    result = grade_documents({"question": "Q", "documents": [keep, drop]})

    assert result["web_search"] is True


def test_web_search_false_when_all_documents_relevant(monkeypatch):
    docs = [Document(page_content="a"), Document(page_content="b")]
    _patch_grader(monkeypatch, {"a": True, "b": True})

    result = grade_documents({"question": "Q", "documents": docs})

    assert result["web_search"] is False
    assert result["documents"] == docs


def test_preserves_question_and_filtered_documents(monkeypatch):
    keep = Document(page_content="a")
    drop = Document(page_content="b")
    _patch_grader(monkeypatch, {"a": True, "b": False})

    result = grade_documents({"question": "my question", "documents": [keep, drop]})

    assert result["question"] == "my question"
    assert result["documents"] == [keep]


# ---------------------------------------------------------------------------
# Graceful degradation: grader failures and incoming fallback flags
# ---------------------------------------------------------------------------


def _patch_grader_with_failures(monkeypatch, relevance_by_content):
    """Like _patch_grader, but a content mapped to 'raise' makes the grader explode."""

    class FlakyGrader:
        def invoke(self, payload):
            outcome = relevance_by_content[payload["document"]]
            if outcome == "raise":
                raise RuntimeError("grader is down")
            return _FakeGrade(outcome)

    monkeypatch.setattr(grade_module, "get_retrieval_grader", lambda: FlakyGrader())


def test_grader_failure_drops_ungraded_document_and_requests_web_search(monkeypatch):
    keep = Document(page_content="good")
    ungraded = Document(page_content="boom")
    _patch_grader_with_failures(monkeypatch, {"good": True, "boom": "raise"})

    result = grade_documents({"question": "Q", "documents": [keep, ungraded]})  # must not raise

    assert result["documents"] == [keep]            # ungraded content is never trusted
    assert result["web_search"] is True
    assert result["stop_reason"] == STOP_REASON_TOOL_ERROR


def test_grader_failure_keeps_grading_remaining_documents(monkeypatch):
    first = Document(page_content="boom")
    second = Document(page_content="good")
    _patch_grader_with_failures(monkeypatch, {"boom": "raise", "good": True})

    result = grade_documents({"question": "Q", "documents": [first, second]})

    assert result["documents"] == [second]


def test_success_does_not_write_stop_reason(monkeypatch):
    docs = [Document(page_content="a")]
    _patch_grader(monkeypatch, {"a": True})

    result = grade_documents({"question": "Q", "documents": docs})

    assert "stop_reason" not in result


def test_preserves_incoming_web_search_fallback_request(monkeypatch):
    # retrieve sets web_search=True when the retriever failed; grading all
    # remaining documents as relevant must not cancel that fallback.
    _patch_grader(monkeypatch, {"a": True})

    result = grade_documents(
        {"question": "Q", "documents": [Document(page_content="a")], "web_search": True}
    )

    assert result["web_search"] is True
