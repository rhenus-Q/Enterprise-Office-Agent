"""
Unit tests for the grade_documents node (graph/nodes/grade_documents.py).

retrieval_grader.invoke is mocked via monkeypatch, so no real OpenAI call happens.
Relevance is driven by a content -> bool mapping for deterministic results.
"""

from langchain_core.documents import Document

import graph.nodes.grade_documents as grade_module
from graph.nodes.grade_documents import grade_documents


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
