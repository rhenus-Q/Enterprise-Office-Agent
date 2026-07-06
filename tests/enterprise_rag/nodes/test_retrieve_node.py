"""
Unit tests for the retrieve node (enterprise_rag/graph/nodes/retrieve.py).

The retriever is mocked via monkeypatch (patching get_node_retriever), so no real
Chroma / embeddings call happens. Tests focus on node state input/output.
"""

import importlib

from langchain_core.documents import Document

from enterprise_rag.graph.consts import STOP_REASON_RETRIEVAL_ERROR
from enterprise_rag.graph.nodes.retrieve import retrieve

# enterprise_rag/graph/nodes/__init__.py re-exports the `retrieve` function under the same name
# as its submodule, so `import enterprise_rag.graph.nodes.retrieve as ...` would bind the
# function, not the module. Resolve the real module for monkeypatching.
retrieve_module = importlib.import_module("enterprise_rag.graph.nodes.retrieve")


def _patch_retriever(monkeypatch, returned_docs):
    """Patch get_node_retriever to return a fake retriever recording the query."""

    calls = {}

    class FakeRetriever:
        def invoke(self, question):
            calls["question"] = question
            return returned_docs

    monkeypatch.setattr(retrieve_module, "get_node_retriever", lambda: FakeRetriever())
    return calls


def test_retrieve_reads_question_from_state(monkeypatch):
    calls = _patch_retriever(monkeypatch, [])

    retrieve({"question": "What is RAG?"})

    assert calls["question"] == "What is RAG?"


def test_retrieve_returns_retrieved_documents(monkeypatch):
    docs = [Document(page_content="d1"), Document(page_content="d2")]
    _patch_retriever(monkeypatch, docs)

    result = retrieve({"question": "Q"})

    assert result["documents"] == docs


def test_retrieve_preserves_question(monkeypatch):
    _patch_retriever(monkeypatch, [])

    result = retrieve({"question": "keep me"})

    assert result["question"] == "keep me"


# ---------------------------------------------------------------------------
# Graceful degradation: retriever / Chroma failure
# ---------------------------------------------------------------------------


def _patch_failing_retriever(monkeypatch):
    class ExplodingRetriever:
        def invoke(self, question):
            raise RuntimeError("chroma is down")

    monkeypatch.setattr(retrieve_module, "get_node_retriever", lambda: ExplodingRetriever())


def test_retrieve_handles_retriever_failure_without_crashing(monkeypatch):
    _patch_failing_retriever(monkeypatch)

    result = retrieve({"question": "Q"})  # must not raise

    assert result["documents"] == []
    assert result["stop_reason"] == STOP_REASON_RETRIEVAL_ERROR


def test_retrieve_failure_requests_web_search_fallback(monkeypatch):
    # Degradation mirrors the "irrelevant documents" path: ask for web search
    # (privacy mode downstream ignores the flag and generates locally).
    _patch_failing_retriever(monkeypatch)

    result = retrieve({"question": "Q"})

    assert result["web_search"] is True


def test_retrieve_success_does_not_write_stop_reason(monkeypatch):
    # A normal pass must not clobber stop reasons recorded by other nodes.
    _patch_retriever(monkeypatch, [Document(page_content="d")])

    result = retrieve({"question": "Q"})

    assert "stop_reason" not in result
