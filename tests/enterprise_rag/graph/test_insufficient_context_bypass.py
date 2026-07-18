"""
Tests for the insufficient-context grading bypass.

When generation produced the deterministic insufficient-context answer (no
usable documents; flagged by the generate node via insufficient_context=True),
grade_generation must skip both graders — there is nothing to verify, and
regenerating from the same empty context cannot improve the answer. The run
ends honestly on the first pass instead of looping toward a misleading
max-retries warning.

All external seams are mocked -- no API keys or network required.
"""

import importlib
from types import SimpleNamespace

from langchain_core.documents import Document

import enterprise_rag.graph.graph as graph_module
from enterprise_rag.graph.chains.generation import INSUFFICIENT_CONTEXT_ANSWER
from enterprise_rag.graph.consts import (
    RETRIEVE,
    STOP_REASON_GENERATION_ERROR,
    STOP_REASON_RETRIEVAL_ERROR,
    STOP_REASON_WEB_SEARCH_DISABLED,
)
from enterprise_rag.graph.formatting import WEB_SEARCH_DISABLED_NOTE, format_answer
from enterprise_rag.graph.graph import grade_generation

# ---------------------------------------------------------------------------
# Helpers (mirrors the other graph test files)
# ---------------------------------------------------------------------------


def _patch_router(monkeypatch, datasource):
    monkeypatch.setattr(
        graph_module,
        "get_question_router",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(datasource=datasource)),
    )


def _patch_counting_graders(monkeypatch, grounded=True, useful=True):
    """Graders with fixed verdicts that record how often they were invoked."""

    calls = {"hallucination": 0, "answer": 0}

    def hallucination():
        def invoke(payload):
            calls["hallucination"] += 1
            return SimpleNamespace(is_grounded=grounded)

        return SimpleNamespace(invoke=invoke)

    def answer():
        def invoke(payload):
            calls["answer"] += 1
            return SimpleNamespace(answers_question=useful)

        return SimpleNamespace(invoke=invoke)

    monkeypatch.setattr(graph_module, "get_hallucination_grader", hallucination)
    monkeypatch.setattr(graph_module, "get_answer_grader", answer)
    return calls


def _patch_graders_to_fail_if_called(monkeypatch):
    """Graders that raise at construction: prove the bypass skips grading."""

    def explode():
        raise AssertionError("grader must not be invoked for an insufficient-context answer")

    monkeypatch.setattr(graph_module, "get_hallucination_grader", explode)
    monkeypatch.setattr(graph_module, "get_answer_grader", explode)


def _generation_state(**overrides):
    state = {
        "question": "Q",
        "documents": [],
        "generation": INSUFFICIENT_CONTEXT_ANSWER,
        "web_search": False,
        "web_search_enabled": True,
        "retries": 1,
        "stop_reason": "",
        "insufficient_context": True,
        "retry_feedback": "",
        "search_query": "",
        "llm_call_count": 0,
        "web_search_count": 0,
        "web_result_grading_count": 0,
    }
    state.update(overrides)
    return state


def _patch_all_node_seams(monkeypatch, *, docs_relevant, web_relevant=True):
    """
    Mock every external seam except generate_answer: with empty documents the
    real generate_answer short-circuits to the deterministic insufficient-
    context answer without building a chain, so the end-to-end tests exercise
    the genuine production short-circuit. Returns the web-search payloads.
    """

    retrieve_module = importlib.import_module("enterprise_rag.graph.nodes.retrieve")
    grade_module = importlib.import_module("enterprise_rag.graph.nodes.grade_documents")
    web_module = importlib.import_module("enterprise_rag.graph.nodes.web_search")
    rewrite_module = importlib.import_module("enterprise_rag.graph.nodes.rewrite_query")

    monkeypatch.setattr(
        retrieve_module,
        "get_node_retriever",
        lambda: SimpleNamespace(invoke=lambda q: [Document(page_content="chunk")]),
    )
    monkeypatch.setattr(
        grade_module,
        "get_retrieval_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_relevant=docs_relevant)),
    )
    monkeypatch.setattr(
        web_module,
        "get_retrieval_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_relevant=web_relevant)),
    )
    monkeypatch.setattr(
        rewrite_module,
        "get_query_rewriter",
        lambda: SimpleNamespace(invoke=lambda p: "rewritten query"),
    )

    web_calls = []

    class FakeWebTool:
        def invoke(self, payload):
            web_calls.append(payload)
            return [{"content": "web result"}]

    monkeypatch.setattr(web_module, "get_web_search_tool", lambda: FakeWebTool())
    return web_calls


def _initial_state(enabled=True):
    return {
        "question": "Q",
        "documents": [],
        "generation": "",
        "web_search": False,
        "web_search_enabled": enabled,
        "retries": 0,
        "stop_reason": "",
        "insufficient_context": False,
        "retry_feedback": "",
        "search_query": "",
        "llm_call_count": 0,
        "web_search_count": 0,
        "web_result_grading_count": 0,
    }


# ---------------------------------------------------------------------------
# grade_generation bypass routing (pure reads)
# ---------------------------------------------------------------------------


def test_insufficient_context_routes_to_end_without_grading(monkeypatch):
    _patch_graders_to_fail_if_called(monkeypatch)

    result = grade_generation(_generation_state())

    assert result == "insufficient_context"


def test_insufficient_context_in_privacy_mode_records_web_search_disabled(monkeypatch):
    # With web search disabled and no earlier failure recorded, the run ends
    # through the notice node so the existing caveat explains the limitation.
    _patch_graders_to_fail_if_called(monkeypatch)

    result = grade_generation(_generation_state(web_search_enabled=False))

    assert result == "web_search_disabled"


def test_insufficient_context_preserves_earlier_stop_reason(monkeypatch):
    # An earlier, more specific failure reason (e.g. retrieval_error) must
    # survive: route straight to END instead of overwriting it via a notice.
    _patch_graders_to_fail_if_called(monkeypatch)

    for enabled in (True, False):
        result = grade_generation(
            _generation_state(
                web_search_enabled=enabled,
                stop_reason=STOP_REASON_RETRIEVAL_ERROR,
            )
        )
        assert result == "insufficient_context"


def test_generation_error_takes_precedence_over_insufficient_context(monkeypatch):
    _patch_graders_to_fail_if_called(monkeypatch)

    result = grade_generation(_generation_state(stop_reason=STOP_REASON_GENERATION_ERROR))

    assert result == "generation_error"


def test_insufficient_context_skips_the_budget_check(monkeypatch):
    # A clean honest decline must not be tagged budget_exhausted: the bypass
    # fires before the LLM-call budget check.
    monkeypatch.setenv("MAX_LLM_CALLS_PER_RUN", "1")
    _patch_graders_to_fail_if_called(monkeypatch)

    result = grade_generation(_generation_state(llm_call_count=5))

    assert result == "insufficient_context"


def test_normal_answer_with_documents_is_still_fully_graded(monkeypatch):
    calls = _patch_counting_graders(monkeypatch, grounded=True, useful=True)

    result = grade_generation(
        _generation_state(
            documents=[Document(page_content="d")],
            generation="A real answer.",
            insufficient_context=False,
        )
    )

    assert result == "useful"
    assert calls == {"hallucination": 1, "answer": 1}


def test_missing_flag_defaults_to_grading_as_before(monkeypatch):
    # Callers that never seed insufficient_context get today's behavior.
    calls = _patch_counting_graders(monkeypatch, grounded=True, useful=True)

    state = _generation_state(documents=[Document(page_content="d")], generation="A")
    del state["insufficient_context"]

    assert grade_generation(state) == "useful"
    assert calls["hallucination"] == 1


# ---------------------------------------------------------------------------
# Compiled graph end-to-end (real generate_answer short-circuit, no LLM)
# ---------------------------------------------------------------------------


def test_app_privacy_mode_decline_ends_with_caveat_and_no_grader_calls(monkeypatch):
    # Privacy mode, every retrieved chunk irrelevant: generation short-circuits
    # to the deterministic decline, the graders are never constructed, and the
    # run ends with the web_search_disabled caveat on the first pass.
    _patch_graders_to_fail_if_called(monkeypatch)
    web_calls = _patch_all_node_seams(monkeypatch, docs_relevant=False)

    result = graph_module.app.invoke(_initial_state(enabled=False))

    assert result["generation"] == INSUFFICIENT_CONTEXT_ANSWER
    assert result["stop_reason"] == STOP_REASON_WEB_SEARCH_DISABLED
    assert result["retries"] == 1  # no retry loop on the decline
    assert result["llm_call_count"] == 0  # the short-circuit costs nothing
    assert web_calls == []  # privacy guarantee holds

    formatted = format_answer(result)
    assert formatted.startswith(INSUFFICIENT_CONTEXT_ANSWER)
    assert WEB_SEARCH_DISABLED_NOTE in formatted


def test_app_web_enabled_decline_ends_cleanly_without_grading(monkeypatch):
    # Web search enabled but useless: chunks irrelevant, web results all
    # graded irrelevant -> empty context -> deterministic decline -> END on
    # the first pass, no caveat (the answer is self-explanatory), no second
    # rewritten search.
    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders_to_fail_if_called(monkeypatch)
    web_calls = _patch_all_node_seams(monkeypatch, docs_relevant=False, web_relevant=False)

    result = graph_module.app.invoke(_initial_state(enabled=True))

    assert result["generation"] == INSUFFICIENT_CONTEXT_ANSWER
    assert result["stop_reason"] == ""  # clean honest decline
    assert result["retries"] == 1
    assert len(web_calls) == 1  # the one fallback search, no rewrite round
    assert format_answer(result) == INSUFFICIENT_CONTEXT_ANSWER  # no Sources, no caveat
