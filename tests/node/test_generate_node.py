"""
Unit tests for the generate node (graph/nodes/generate.py).

The node is tested in isolation: graph.chains.generation.generate_answer is mocked
via monkeypatch, so no real OpenAI call happens. Tests focus only on how the node
reads state and shapes the returned state.
"""

from langchain_core.documents import Document

import importlib

from graph.consts import STOP_REASON_GENERATION_ERROR
from graph.nodes.generate import GENERATION_FAILED_ANSWER, generate

# graph/nodes/__init__.py re-exports the `generate` function under the same name
# as its submodule, so `import graph.nodes.generate as ...` would bind the
# function, not the module. Resolve the real module for monkeypatching.
generate_module = importlib.import_module("graph.nodes.generate")


def _patch_generate_answer(monkeypatch):
    """Replace generate_answer with a recorder that returns a fixed answer."""

    calls = {}

    def fake_generate_answer(question, documents, retry_feedback=""):
        calls["question"] = question
        calls["documents"] = documents
        calls["retry_feedback"] = retry_feedback
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


def test_generate_passes_retry_feedback_to_generate_answer(monkeypatch):
    calls = _patch_generate_answer(monkeypatch)

    state = {"question": "Q", "documents": [], "retries": 1, "retry_feedback": "be stricter"}
    generate(state)

    assert calls["retry_feedback"] == "be stricter"


def test_generate_defaults_to_empty_retry_feedback(monkeypatch):
    calls = _patch_generate_answer(monkeypatch)

    generate({"question": "Q", "documents": [], "retries": 0})

    assert calls["retry_feedback"] == ""


def test_generate_increments_llm_call_count_when_documents_present(monkeypatch):
    _patch_generate_answer(monkeypatch)

    docs = [Document(page_content="chunk")]
    state = {"question": "Q", "documents": docs, "retries": 0, "llm_call_count": 2}
    result = generate(state)

    assert result["llm_call_count"] == 3


def test_generate_does_not_count_empty_context_short_circuit(monkeypatch):
    # With no documents, generate_answer returns the canned answer without an
    # LLM call -- the budget counter must not move.
    _patch_generate_answer(monkeypatch)

    state = {"question": "Q", "documents": [], "retries": 0, "llm_call_count": 2}
    result = generate(state)

    assert result["llm_call_count"] == 2


def test_generate_uses_safe_defaults_for_missing_keys(monkeypatch):
    calls = _patch_generate_answer(monkeypatch)

    # Only question is provided; documents / retries / web_search are missing.
    state = {"question": "Q"}
    result = generate(state)

    assert result["documents"] == []        # default []
    assert calls["documents"] == []         # default [] is what gets passed onward
    assert result["retries"] == 1           # 0 + 1
    assert result["web_search"] is False    # default False


# ---------------------------------------------------------------------------
# insufficient_context flag (drives the grading bypass in grade_generation)
# ---------------------------------------------------------------------------


def test_generate_flags_insufficient_context_when_documents_empty(monkeypatch):
    _patch_generate_answer(monkeypatch)

    result = generate({"question": "Q", "documents": [], "retries": 0})

    assert result["insufficient_context"] is True


def test_generate_does_not_flag_insufficient_context_with_documents(monkeypatch):
    _patch_generate_answer(monkeypatch)

    docs = [Document(page_content="chunk")]
    result = generate({"question": "Q", "documents": docs, "retries": 0})

    assert result["insufficient_context"] is False


# ---------------------------------------------------------------------------
# Graceful degradation: generation LLM failure
# ---------------------------------------------------------------------------


def _patch_failing_generate_answer(monkeypatch):
    def exploding_generate_answer(question, documents, retry_feedback=""):
        raise RuntimeError("openai is down")

    monkeypatch.setattr(generate_module, "generate_answer", exploding_generate_answer)


def test_generation_failure_returns_safe_answer_and_stop_reason(monkeypatch):
    _patch_failing_generate_answer(monkeypatch)

    docs = [Document(page_content="chunk")]
    result = generate({"question": "Q", "documents": docs, "retries": 0})  # must not raise

    # The failed call is never presented as a normal answer: the generation is
    # a deterministic placeholder and the stop reason routes the run to END.
    assert result["generation"] == GENERATION_FAILED_ANSWER
    assert result["stop_reason"] == STOP_REASON_GENERATION_ERROR
    # The placeholder is a failure artifact, not the deterministic decline.
    assert result["insufficient_context"] is False


def test_generation_failure_still_counts_retry_and_llm_call(monkeypatch):
    _patch_failing_generate_answer(monkeypatch)

    docs = [Document(page_content="chunk")]
    result = generate({"question": "Q", "documents": docs, "retries": 1, "llm_call_count": 4})

    assert result["retries"] == 2           # the attempt happened
    assert result["llm_call_count"] == 5    # the failed API call still counts


def test_generation_success_does_not_write_stop_reason(monkeypatch):
    _patch_generate_answer(monkeypatch)

    result = generate({"question": "Q", "documents": [], "retries": 0})

    assert "stop_reason" not in result
