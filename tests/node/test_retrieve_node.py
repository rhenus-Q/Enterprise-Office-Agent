"""
Unit tests for the retrieve node (graph/nodes/retrieve.py).

The retriever is mocked via monkeypatch (patching get_node_retriever), so no real
Chroma / embeddings call happens. Tests focus on node state input/output.
"""

from langchain_core.documents import Document

import importlib

from graph.nodes.retrieve import retrieve

# graph/nodes/__init__.py re-exports the `retrieve` function under the same name
# as its submodule, so `import graph.nodes.retrieve as ...` would bind the
# function, not the module. Resolve the real module for monkeypatching.
retrieve_module = importlib.import_module("graph.nodes.retrieve")


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
