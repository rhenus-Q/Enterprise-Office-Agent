"""
Tests for the per-run cost/latency budget mechanism.

Counters (llm_call_count / web_search_count / web_result_grading_count) are
incremented in nodes; budgets are checked as pure reads in grade_generation
(plus a defensive guard inside web_search). An exhausted budget ends the run
through the budget_exhausted notice node, and main.py appends a caveat.

All external seams are mocked -- no API keys or network required.
"""

import importlib
from types import SimpleNamespace

import pytest

from langchain_core.documents import Document

import graph.graph as graph_module
from graph.config import (
    DEFAULT_MAX_LLM_CALLS_PER_RUN,
    DEFAULT_MAX_WEB_RESULTS_TO_GRADE,
    DEFAULT_MAX_WEB_SEARCHES_PER_RUN,
    max_llm_calls_per_run,
    max_web_results_to_grade,
    max_web_searches_per_run,
)
from graph.consts import RETRIEVE, STOP_REASON_BUDGET_EXHAUSTED
from graph.graph import grade_generation
from graph.nodes.budget_exhausted_notice import budget_exhausted_notice
from main import BUDGET_EXHAUSTED_NOTE, format_answer


# ---------------------------------------------------------------------------
# Config parsing
# ---------------------------------------------------------------------------


def test_budget_defaults_when_env_unset(monkeypatch):
    for name in ("MAX_LLM_CALLS_PER_RUN", "MAX_WEB_SEARCHES_PER_RUN", "MAX_WEB_RESULTS_TO_GRADE"):
        monkeypatch.delenv(name, raising=False)

    assert max_llm_calls_per_run() == DEFAULT_MAX_LLM_CALLS_PER_RUN
    assert max_web_searches_per_run() == DEFAULT_MAX_WEB_SEARCHES_PER_RUN
    assert max_web_results_to_grade() == DEFAULT_MAX_WEB_RESULTS_TO_GRADE


def test_budget_env_overrides(monkeypatch):
    monkeypatch.setenv("MAX_LLM_CALLS_PER_RUN", "7")
    monkeypatch.setenv("MAX_WEB_SEARCHES_PER_RUN", " 2 ")
    monkeypatch.setenv("MAX_WEB_RESULTS_TO_GRADE", "4")

    assert max_llm_calls_per_run() == 7
    assert max_web_searches_per_run() == 2
    assert max_web_results_to_grade() == 4


@pytest.mark.parametrize("value", ["not-a-number", "", "0", "-3"])
def test_budget_invalid_or_nonpositive_values_fall_back_to_default(monkeypatch, value):
    monkeypatch.setenv("MAX_LLM_CALLS_PER_RUN", value)

    assert max_llm_calls_per_run() == DEFAULT_MAX_LLM_CALLS_PER_RUN


# ---------------------------------------------------------------------------
# Helpers (mirrors the other graph test files)
# ---------------------------------------------------------------------------


def _patch_router(monkeypatch, datasource):
    monkeypatch.setattr(
        graph_module,
        "get_question_router",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(datasource=datasource)),
    )


def _patch_graders(monkeypatch, grounded, useful):
    monkeypatch.setattr(
        graph_module,
        "get_hallucination_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_grounded=grounded)),
    )
    monkeypatch.setattr(
        graph_module,
        "get_answer_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(answers_question=useful)),
    )


def _patch_graders_to_fail_if_called(monkeypatch):
    """Graders that raise: prove the budget pre-check fires before any grading."""

    def explode():
        raise AssertionError("grader must not be invoked once the budget is exhausted")

    monkeypatch.setattr(graph_module, "get_hallucination_grader", explode)
    monkeypatch.setattr(graph_module, "get_answer_grader", explode)


def _generation_state(**overrides):
    state = {
        "question": "Q",
        "documents": [Document(page_content="d")],
        "generation": "A",
        "web_search": False,
        "web_search_enabled": True,
        "retries": 1,
        "stop_reason": "",
        "retry_feedback": "",
        "search_query": "",
        "llm_call_count": 0,
        "web_search_count": 0,
        "web_result_grading_count": 0,
    }
    state.update(overrides)
    return state


def _patch_all_node_seams(monkeypatch, *, docs_relevant=True):
    """Mock every external seam; returns the recorded web-search payloads."""

    retrieve_module = importlib.import_module("graph.nodes.retrieve")
    grade_module = importlib.import_module("graph.nodes.grade_documents")
    generate_module = importlib.import_module("graph.nodes.generate")
    web_module = importlib.import_module("graph.nodes.web_search")
    rewrite_module = importlib.import_module("graph.nodes.rewrite_query")

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
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_relevant=True)),
    )
    monkeypatch.setattr(
        generate_module,
        "generate_answer",
        lambda question, documents, retry_feedback="": "FINAL ANSWER",
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


def _initial_state():
    return {
        "question": "Q",
        "documents": [],
        "generation": "",
        "web_search": False,
        "web_search_enabled": True,
        "retries": 0,
        "stop_reason": "",
        "retry_feedback": "",
        "search_query": "",
        "llm_call_count": 0,
        "web_search_count": 0,
        "web_result_grading_count": 0,
    }


# ---------------------------------------------------------------------------
# grade_generation budget checks (pure reads)
# ---------------------------------------------------------------------------


def test_llm_budget_check_fires_before_any_grader_call(monkeypatch):
    monkeypatch.setenv("MAX_LLM_CALLS_PER_RUN", "3")
    _patch_graders_to_fail_if_called(monkeypatch)

    result = grade_generation(_generation_state(llm_call_count=3))

    assert result == "budget_exhausted"


def test_llm_budget_not_binding_below_limit(monkeypatch):
    monkeypatch.setenv("MAX_LLM_CALLS_PER_RUN", "3")
    _patch_graders(monkeypatch, grounded=True, useful=True)

    result = grade_generation(_generation_state(llm_call_count=2))

    assert result == "useful"


def test_web_budget_stops_not_useful_loop(monkeypatch):
    # Improving a not-useful answer needs another search; with the search
    # budget spent, the run must stop instead of looping toward a skip.
    monkeypatch.setenv("MAX_WEB_SEARCHES_PER_RUN", "1")
    _patch_graders(monkeypatch, grounded=True, useful=False)

    result = grade_generation(_generation_state(web_search_count=1))

    assert result == "budget_exhausted"


def test_existing_stop_reasons_take_their_usual_precedence(monkeypatch):
    # Privacy mode and the retry cap are checked before the web budget.
    monkeypatch.setenv("MAX_WEB_SEARCHES_PER_RUN", "1")
    _patch_graders(monkeypatch, grounded=True, useful=False)

    assert (
        grade_generation(
            _generation_state(web_search_enabled=False, web_search_count=1)
        )
        == "web_search_disabled"
    )
    assert (
        grade_generation(_generation_state(retries=5, web_search_count=1))
        == "max_retries_not_useful"
    )


# ---------------------------------------------------------------------------
# Notice node + caveat formatting
# ---------------------------------------------------------------------------


def test_budget_notice_records_stop_reason_only():
    result = budget_exhausted_notice(_generation_state())

    assert result == {"stop_reason": STOP_REASON_BUDGET_EXHAUSTED}


def test_format_answer_warns_on_budget_exhaustion():
    result = {"generation": "Partial answer.", "stop_reason": STOP_REASON_BUDGET_EXHAUSTED}

    formatted = format_answer(result)

    assert formatted.startswith("Partial answer.")
    assert BUDGET_EXHAUSTED_NOTE in formatted


# ---------------------------------------------------------------------------
# Compiled graph end-to-end
# ---------------------------------------------------------------------------


def test_app_stops_with_budget_exhausted_when_llm_budget_spent(monkeypatch):
    # Budget of 2 counted LLM calls; every generation fails grounding.
    # gen1 (llm=1) -> regenerate -> gen2 (llm=2) -> budget pre-check stops.
    monkeypatch.setenv("MAX_LLM_CALLS_PER_RUN", "2")
    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders(monkeypatch, grounded=False, useful=True)
    web_calls = _patch_all_node_seams(monkeypatch)

    result = graph_module.app.invoke(_initial_state())

    assert result["stop_reason"] == STOP_REASON_BUDGET_EXHAUSTED
    assert result["llm_call_count"] == 2
    assert result["retries"] == 2  # stopped well before MAX_RETRIES
    assert web_calls == []


def test_app_stops_with_budget_exhausted_when_web_budget_spent(monkeypatch):
    # One search allowed; every answer is grounded but not useful. After the
    # single search round the web budget stops the loop.
    monkeypatch.setenv("MAX_WEB_SEARCHES_PER_RUN", "1")
    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders(monkeypatch, grounded=True, useful=False)
    web_calls = _patch_all_node_seams(monkeypatch)

    result = graph_module.app.invoke(_initial_state())

    assert result["stop_reason"] == STOP_REASON_BUDGET_EXHAUSTED
    assert result["web_search_count"] == 1
    assert len(web_calls) == 1  # exactly one search ever ran


def test_app_normal_success_tracks_counters_without_warnings(monkeypatch):
    for name in ("MAX_LLM_CALLS_PER_RUN", "MAX_WEB_SEARCHES_PER_RUN", "MAX_WEB_RESULTS_TO_GRADE"):
        monkeypatch.delenv(name, raising=False)
    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_all_node_seams(monkeypatch)

    result = graph_module.app.invoke(_initial_state())

    assert result["stop_reason"] == ""             # no caveat of any kind
    assert result["llm_call_count"] == 1           # one generation, nothing else
    assert result["web_search_count"] == 0
    assert result["web_result_grading_count"] == 0
    assert web_calls == []
    assert format_answer(result) == "FINAL ANSWER"
