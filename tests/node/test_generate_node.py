"""
Unit tests for the generate node (graph/nodes/generate.py).

The node is tested in isolation: graph.chains.generation.generate_answer is mocked
via monkeypatch, so no real OpenAI call happens. Tests focus only on how the node
reads state and shapes the returned state.
"""

from langchain_core.documents import Document

import importlib

from graph.nodes.generate import generate

# graph/nodes/__init__.py re-exports the `generate` function under the same name
# as its submodule, so `import graph.nodes.generate as ...` would bind the
# function, not the module. Resolve the real module for monkeypatching.
generate_module = importlib.import_module("graph.nodes.generate")


def _patch_generate_answer(monkeypatch):
    """Replace generate_answer with a recorder that returns a fixed answer."""

    calls = {}

    def fake_generate_answer(question, documents):
        calls["question"] = question
        calls["documents"] = documents
        calls["called"] = True
        return "FAKE ANSWER"

    monkeypatch.setattr(generate_module, "generate_answer", fake_generate_answer)
    return calls


def test_generate_calls_generate_answer_with_question_and_documents(monkeypatch):
    # The node must go through generate_answer(...), not generation_chain.invoke(...).
    # generate.py no longer imports generation_chain, and this confirms the seam is used.
    calls = _patch_generate_answer(monkeypatch)

    docs = [Document(page_content="chunk")]
    state = {"question": "What is RAG?", "documents": docs, "retries": 0, "web_search": False}

    generate(state)

    assert calls["called"] is True
    assert calls["question"] == "What is RAG?"
    assert calls["documents"] == docs


def test_generate_returns_generation(monkeypatch):
    _patch_generate_answer(monkeypatch)

    state = {"question": "Q", "documents": [], "retries": 0, "web_search": False}
    result = generate(state)

    assert result["generation"] == "FAKE ANSWER"


def test_generate_increments_retries_by_one(monkeypatch):
    _patch_generate_answer(monkeypatch)

    state = {"question": "Q", "documents": [], "retries": 2, "web_search": False}
    result = generate(state)

    assert result["retries"] == 3


def test_generate_preserves_documents_and_web_search(monkeypatch):
    _patch_generate_answer(monkeypatch)

    docs = [Document(page_content="a"), Document(page_content="b")]
    state = {"question": "Q", "documents": docs, "retries": 0, "web_search": True}
    result = generate(state)

    assert result["documents"] == docs
    assert result["web_search"] is True


def test_generate_uses_safe_defaults_for_missing_keys(monkeypatch):
    calls = _patch_generate_answer(monkeypatch)

    # Only question is provided; documents / retries / web_search are missing.
    state = {"question": "Q"}
    result = generate(state)

    assert result["documents"] == []        # default []
    assert calls["documents"] == []         # default [] is what gets passed onward
    assert result["retries"] == 1           # 0 + 1
    assert result["web_search"] is False    # default False
