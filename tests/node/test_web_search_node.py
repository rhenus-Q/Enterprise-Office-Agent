"""
Unit tests for the web_search node (graph/nodes/web_search.py).

The Tavily tool is mocked via monkeypatch (patching get_web_search_tool), so no real
web search happens. Tests focus on node state input/output.
"""

from langchain_core.documents import Document

import importlib

from graph.nodes.web_search import web_search

# graph/nodes/__init__.py re-exports the `web_search` function under the same name
# as its submodule, so `import graph.nodes.web_search as ...` would bind the
# function, not the module. Resolve the real module for monkeypatching.
web_search_module = importlib.import_module("graph.nodes.web_search")


def _patch_tool(monkeypatch, results):
    """Patch get_web_search_tool to return a fake tool recording the payload."""

    calls = {}

    class FakeTool:
        def invoke(self, payload):
            calls["payload"] = payload
            return results

    monkeypatch.setattr(web_search_module, "get_web_search_tool", lambda: FakeTool())
    return calls


def test_web_search_reads_question_from_state(monkeypatch):
    calls = _patch_tool(monkeypatch, [{"content": "result"}])

    web_search({"question": "What is RAG?", "documents": []})

    assert calls["payload"] == {"query": "What is RAG?"}


def test_web_search_appends_document_built_from_results(monkeypatch):
    _patch_tool(monkeypatch, [{"content": "alpha"}, {"content": "beta"}])

    result = web_search({"question": "Q", "documents": []})

    assert len(result["documents"]) == 1
    web_doc = result["documents"][0]
    assert isinstance(web_doc, Document)
    assert "alpha" in web_doc.page_content
    assert "beta" in web_doc.page_content
    assert web_doc.metadata["source"] == "web_search"


def test_web_search_preserves_existing_documents_and_appends(monkeypatch):
    _patch_tool(monkeypatch, [{"content": "web"}])

    existing = Document(page_content="existing")
    result = web_search({"question": "Q", "documents": [existing]})

    assert len(result["documents"]) == 2
    assert result["documents"][0] is existing               # existing kept, first
    assert result["documents"][-1].metadata["source"] == "web_search"  # web result appended last


def test_web_search_preserves_question(monkeypatch):
    _patch_tool(monkeypatch, [{"content": "web"}])

    result = web_search({"question": "keep me", "documents": []})

    assert result["question"] == "keep me"
