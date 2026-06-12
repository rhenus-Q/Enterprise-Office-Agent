"""
Tests for graceful degradation when external dependencies fail.

External failures (Chroma retriever, Tavily, the generation LLM, the graders,
the query rewriter) must never crash the graph: nodes degrade or stop safely,
record a stop_reason (retrieval_error / web_search_error / generation_error /
tool_error), and main.py appends an honest user-facing caveat.

All external seams are mocked -- no API keys or network required.
"""

import importlib
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

import graph.graph as graph_module
from graph.consts import (
    RETRIEVE,
    STOP_REASON_GENERATION_ERROR,
    STOP_REASON_RETRIEVAL_ERROR,
    STOP_REASON_TOOL_ERROR,
    STOP_REASON_WEB_SEARCH_ERROR,
)
from graph.graph import grade_generation
from graph.nodes.clear_transient_tool_error import clear_transient_tool_error
from graph.nodes.generate import GENERATION_FAILED_ANSWER
from graph.nodes.tool_error_notice import tool_error_notice
from main import (
    GENERATION_ERROR_NOTE,
    RETRIEVAL_ERROR_NOTE,
    TOOL_ERROR_NOTE,
    WEB_SEARCH_ERROR_NOTE,
    format_answer,
)

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
    """Graders that raise at construction: prove no grading of a failed generation."""

    def explode():
        raise AssertionError("grader must not be invoked for a failed generation")

    monkeypatch.setattr(graph_module, "get_hallucination_grader", explode)
    monkeypatch.setattr(graph_module, "get_answer_grader", explode)


def _patch_raising_hallucination_grader(monkeypatch):
    monkeypatch.setattr(
        graph_module,
        "get_hallucination_grader",
        lambda: SimpleNamespace(invoke=lambda p: (_ for _ in ()).throw(RuntimeError("down"))),
    )


def _patch_raising_answer_grader(monkeypatch):
    monkeypatch.setattr(
        graph_module,
        "get_hallucination_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_grounded=True)),
    )
    monkeypatch.setattr(
        graph_module,
        "get_answer_grader",
        lambda: SimpleNamespace(invoke=lambda p: (_ for _ in ()).throw(RuntimeError("down"))),
    )


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


def _patch_all_node_seams(
    monkeypatch,
    *,
    docs_relevant=True,
    retriever_raises=False,
    web_tool_raises=False,
    generation_raises=False,
):
    """Mock every external seam; returns the recorded web-search payloads."""

    retrieve_module = importlib.import_module("graph.nodes.retrieve")
    grade_module = importlib.import_module("graph.nodes.grade_documents")
    generate_module = importlib.import_module("graph.nodes.generate")
    web_module = importlib.import_module("graph.nodes.web_search")
    rewrite_module = importlib.import_module("graph.nodes.rewrite_query")

    def fake_retrieve(q):
        if retriever_raises:
            raise RuntimeError("chroma is down")
        return [Document(page_content="chunk")]

    monkeypatch.setattr(
        retrieve_module,
        "get_node_retriever",
        lambda: SimpleNamespace(invoke=fake_retrieve),
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

    def fake_generate_answer(question, documents, retry_feedback=""):
        if generation_raises:
            raise RuntimeError("openai is down")
        return "FINAL ANSWER"

    monkeypatch.setattr(generate_module, "generate_answer", fake_generate_answer)
    monkeypatch.setattr(
        rewrite_module,
        "get_query_rewriter",
        lambda: SimpleNamespace(invoke=lambda p: "rewritten query"),
    )

    web_calls = []

    class FakeWebTool:
        def invoke(self, payload):
            web_calls.append(payload)
            if web_tool_raises:
                raise TimeoutError("tavily timed out")
            return [{"content": "web result"}]

    monkeypatch.setattr(web_module, "get_web_search_tool", lambda: FakeWebTool())
    return web_calls


def _initial_state(**overrides):
    state = {
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
    state.update(overrides)
    return state


# ---------------------------------------------------------------------------
# grade_generation error routing (pure reads)
# ---------------------------------------------------------------------------


def test_generation_error_routes_to_end_without_grading(monkeypatch):
    _patch_graders_to_fail_if_called(monkeypatch)

    result = grade_generation(_generation_state(stop_reason=STOP_REASON_GENERATION_ERROR))

    assert result == "generation_error"


def test_generation_error_takes_precedence_over_budget_check(monkeypatch):
    # A failed generation must end the run regardless of remaining budget.
    monkeypatch.setenv("MAX_LLM_CALLS_PER_RUN", "1")
    _patch_graders_to_fail_if_called(monkeypatch)

    result = grade_generation(
        _generation_state(stop_reason=STOP_REASON_GENERATION_ERROR, llm_call_count=5)
    )

    assert result == "generation_error"


def test_degraded_stop_reasons_do_not_skip_grading(monkeypatch):
    # Earlier degradations (retrieval_error / web_search_error / tool_error)
    # still get a fully graded answer; only generation_error skips grading.
    _patch_graders(monkeypatch, grounded=True, useful=True)

    for reason in (
        STOP_REASON_RETRIEVAL_ERROR,
        STOP_REASON_WEB_SEARCH_ERROR,
        STOP_REASON_TOOL_ERROR,
    ):
        assert grade_generation(_generation_state(stop_reason=reason)) == "useful"


def test_hallucination_grader_failure_returns_tool_error(monkeypatch):
    _patch_raising_hallucination_grader(monkeypatch)

    result = grade_generation(_generation_state())  # must not raise

    assert result == "tool_error"


def test_answer_grader_failure_returns_tool_error(monkeypatch):
    _patch_raising_answer_grader(monkeypatch)

    result = grade_generation(_generation_state())  # must not raise

    assert result == "tool_error"


# ---------------------------------------------------------------------------
# Notice node + caveat formatting
# ---------------------------------------------------------------------------


def test_tool_error_notice_records_stop_reason_only():
    result = tool_error_notice(_generation_state())

    assert result == {"stop_reason": STOP_REASON_TOOL_ERROR}


@pytest.mark.parametrize(
    "stop_reason, note",
    [
        (STOP_REASON_RETRIEVAL_ERROR, RETRIEVAL_ERROR_NOTE),
        (STOP_REASON_WEB_SEARCH_ERROR, WEB_SEARCH_ERROR_NOTE),
        (STOP_REASON_GENERATION_ERROR, GENERATION_ERROR_NOTE),
        (STOP_REASON_TOOL_ERROR, TOOL_ERROR_NOTE),
    ],
)
def test_format_answer_appends_error_caveats(stop_reason, note):
    result = {"generation": "Partial answer.", "stop_reason": stop_reason}

    formatted = format_answer(result)

    assert formatted.startswith("Partial answer.")
    assert note in formatted


def test_format_answer_no_caveat_on_success():
    assert format_answer({"generation": "Clean answer.", "stop_reason": ""}) == "Clean answer."


# ---------------------------------------------------------------------------
# Compiled graph end-to-end
# ---------------------------------------------------------------------------


def test_app_survives_retriever_failure_and_falls_back_to_web(monkeypatch):
    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_all_node_seams(monkeypatch, retriever_raises=True)

    result = graph_module.app.invoke(_initial_state())  # must not raise

    assert result["stop_reason"] == STOP_REASON_RETRIEVAL_ERROR
    assert len(web_calls) == 1  # degraded to web search
    assert result["generation"] == "FINAL ANSWER"  # web context still produced an answer


def test_app_survives_retriever_failure_in_privacy_mode_without_web_calls(monkeypatch):
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_all_node_seams(monkeypatch, retriever_raises=True)

    result = graph_module.app.invoke(_initial_state(web_search_enabled=False))

    assert result["stop_reason"] == STOP_REASON_RETRIEVAL_ERROR
    assert web_calls == []  # privacy guarantee survives the failure
    assert result["documents"] == []  # empty context -> safe deterministic answer


def test_app_survives_tavily_failure_and_answers_from_local_documents(monkeypatch):
    # One retrieved chunk is irrelevant -> web fallback -> Tavily fails ->
    # the run continues with the (empty after filtering) local context.
    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_all_node_seams(monkeypatch, docs_relevant=False, web_tool_raises=True)

    result = graph_module.app.invoke(_initial_state())  # must not raise

    assert result["stop_reason"] == STOP_REASON_WEB_SEARCH_ERROR
    assert len(web_calls) == 1
    assert all(d.metadata.get("source") != "web_search" for d in result["documents"])
    assert result["web_search_count"] == 1  # the failed attempt is budgeted


def test_app_stops_safely_when_generation_fails(monkeypatch):
    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders_to_fail_if_called(monkeypatch)  # a failed generation is never graded
    _patch_all_node_seams(monkeypatch, generation_raises=True)

    result = graph_module.app.invoke(_initial_state())  # must not raise

    assert result["stop_reason"] == STOP_REASON_GENERATION_ERROR
    assert result["generation"] == GENERATION_FAILED_ANSWER
    assert result["retries"] == 1  # stopped on the first failure, no retry loop


def test_app_stops_with_tool_error_when_hallucination_grader_fails(monkeypatch):
    _patch_router(monkeypatch, RETRIEVE)
    _patch_raising_hallucination_grader(monkeypatch)
    _patch_all_node_seams(monkeypatch)

    result = graph_module.app.invoke(_initial_state())  # must not raise

    assert result["stop_reason"] == STOP_REASON_TOOL_ERROR
    assert result["generation"] == "FINAL ANSWER"  # answer delivered, flagged unverified


# ---------------------------------------------------------------------------
# Transient tool_error is cleared on a fully successful answer
# ---------------------------------------------------------------------------


def test_clear_node_clears_only_transient_tool_error():
    assert clear_transient_tool_error(_generation_state(stop_reason=STOP_REASON_TOOL_ERROR)) == {
        "stop_reason": ""
    }

    # Clean runs and source-unavailable degradations pass through untouched.
    assert clear_transient_tool_error(_generation_state(stop_reason="")) == {}
    assert (
        clear_transient_tool_error(_generation_state(stop_reason=STOP_REASON_RETRIEVAL_ERROR)) == {}
    )
    assert (
        clear_transient_tool_error(_generation_state(stop_reason=STOP_REASON_WEB_SEARCH_ERROR))
        == {}
    )


def test_app_successful_web_answer_clears_transient_grading_tool_error(monkeypatch):
    # The web-cyber-news eval case: one web result's relevance-grading call
    # fails transiently (the result is dropped), the vetted remainder
    # produces an answer that passes both gates -- the final stop_reason
    # must be empty, not a stale tool_error.
    monkeypatch.setattr(
        graph_module,
        "get_question_router",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(datasource="websearch")),
    )
    _patch_graders(monkeypatch, grounded=True, useful=True)
    _patch_all_node_seams(monkeypatch)

    web_module = importlib.import_module("graph.nodes.web_search")
    monkeypatch.setattr(
        web_module,
        "get_web_search_tool",
        lambda: SimpleNamespace(invoke=lambda p: [{"content": "boom"}, {"content": "good"}]),
    )

    class FlakyGrader:
        def invoke(self, payload):
            if payload["document"] == "boom":
                raise RuntimeError("grader hiccup")
            return SimpleNamespace(is_relevant=True)

    monkeypatch.setattr(web_module, "get_retrieval_grader", lambda: FlakyGrader())

    result = graph_module.app.invoke(_initial_state())

    assert result["generation"] == "FINAL ANSWER"
    assert result["stop_reason"] == ""  # stale transient warning cleared
    assert any(
        d.metadata.get("source") == "web_search" for d in result["documents"]
    )  # the vetted result was used


def test_app_unrecovered_tool_error_still_ends_with_tool_error(monkeypatch):
    # A true unrecovered tool failure must keep its stop_reason: here the
    # verification (hallucination) grader itself fails, so the run ends
    # through the terminal tool_error notice — never through the cleanup
    # node, which sits only on the fully-successful "useful" path.
    _patch_router(monkeypatch, RETRIEVE)
    _patch_raising_hallucination_grader(monkeypatch)
    _patch_all_node_seams(monkeypatch, docs_relevant=False, web_tool_raises=False)

    result = graph_module.app.invoke(_initial_state())

    assert result["stop_reason"] == STOP_REASON_TOOL_ERROR


def test_app_successful_answer_keeps_retrieval_error(monkeypatch):
    # Guard the deliberate asymmetry: a whole-source degradation
    # (retrieval_error) persists even when the final answer passes both
    # gates -- only the transient tool_error is cleared.
    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    _patch_all_node_seams(monkeypatch, retriever_raises=True)

    result = graph_module.app.invoke(_initial_state())

    assert result["generation"] == "FINAL ANSWER"
    assert result["stop_reason"] == STOP_REASON_RETRIEVAL_ERROR
