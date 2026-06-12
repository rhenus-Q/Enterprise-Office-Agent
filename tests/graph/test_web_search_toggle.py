"""
Tests for the WEB_SEARCH_ENABLED toggle (privacy mode).

Covers three layers, all fully mocked -- no API keys or network required:
1. graph.config.web_search_enabled() env-var parsing.
2. The routing/decision functions in graph/graph.py, with the LLM chains
   monkeypatched at their lazy get_*() seams.
3. The compiled graph end-to-end, proving the web_search node is called when
   the toggle is on and never reached when it is off.
"""

import importlib
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

import graph.graph as graph_module
from graph.config import web_search_enabled
from graph.consts import (
    GENERATE,
    RETRIEVE,
    STOP_REASON_WEB_SEARCH_DISABLED,
    WEBSEARCH,
)
from graph.graph import (
    MAX_RETRIES,
    decide_to_generate,
    grade_generation,
    route_question,
)
from graph.nodes.web_search_disabled_notice import web_search_disabled_notice
from main import WEB_SEARCH_DISABLED_NOTE, format_answer

# ---------------------------------------------------------------------------
# graph.config.web_search_enabled -- env parsing
# ---------------------------------------------------------------------------


def test_config_defaults_to_true_when_unset(monkeypatch):
    monkeypatch.delenv("WEB_SEARCH_ENABLED", raising=False)

    assert web_search_enabled() is True


@pytest.mark.parametrize("value", ["true", "True", "TRUE", "1", "yes", "anything-else"])
def test_config_truthy_values_keep_web_search_enabled(monkeypatch, value):
    monkeypatch.setenv("WEB_SEARCH_ENABLED", value)

    assert web_search_enabled() is True


@pytest.mark.parametrize("value", ["false", "False", "FALSE", " false ", "0", "no", "off"])
def test_config_falsy_values_disable_web_search(monkeypatch, value):
    monkeypatch.setenv("WEB_SEARCH_ENABLED", value)

    assert web_search_enabled() is False


# ---------------------------------------------------------------------------
# Helpers: fake chains patched at the lazy get_*() seams in graph.graph
# ---------------------------------------------------------------------------


def _patch_router(monkeypatch, datasource):
    """Patch get_question_router to a fake recording whether it was consulted."""

    calls = {"count": 0}

    class FakeRouter:
        def invoke(self, payload):
            calls["count"] += 1
            return SimpleNamespace(datasource=datasource)

    monkeypatch.setattr(graph_module, "get_question_router", lambda: FakeRouter())
    return calls


def _patch_graders(monkeypatch, grounded, useful):
    """Patch hallucination + answer graders with fixed verdicts."""

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


def _generation_state(**overrides):
    """A full post-generation state; tests override only what they exercise."""

    state = {
        "question": "Q",
        "documents": [Document(page_content="d")],
        "generation": "A",
        "web_search": False,
        "web_search_enabled": True,
        "retries": 1,
    }
    state.update(overrides)
    return state


# ---------------------------------------------------------------------------
# route_question
# ---------------------------------------------------------------------------


def test_route_question_enabled_routes_to_websearch(monkeypatch):
    _patch_router(monkeypatch, WEBSEARCH)

    result = route_question({"question": "Q", "web_search_enabled": True})

    assert result == WEBSEARCH


def test_route_question_enabled_routes_to_retrieve(monkeypatch):
    _patch_router(monkeypatch, RETRIEVE)

    result = route_question({"question": "Q", "web_search_enabled": True})

    assert result == RETRIEVE


def test_route_question_missing_flag_defaults_to_enabled(monkeypatch):
    # Backward compatibility: callers that don't seed the flag get today's behavior.
    calls = _patch_router(monkeypatch, WEBSEARCH)

    result = route_question({"question": "Q"})

    assert result == WEBSEARCH
    assert calls["count"] == 1


def test_route_question_disabled_always_retrieves_without_calling_router(monkeypatch):
    calls = _patch_router(monkeypatch, WEBSEARCH)  # router WOULD say websearch

    result = route_question({"question": "Q", "web_search_enabled": False})

    assert result == RETRIEVE
    assert calls["count"] == 0  # the question never reaches the router LLM


# ---------------------------------------------------------------------------
# decide_to_generate
# ---------------------------------------------------------------------------


def test_decide_enabled_falls_back_to_websearch_on_irrelevant_docs():
    result = decide_to_generate({"web_search": True, "web_search_enabled": True})

    assert result == WEBSEARCH


def test_decide_missing_flag_defaults_to_enabled():
    result = decide_to_generate({"web_search": True})

    assert result == WEBSEARCH


def test_decide_disabled_generates_even_with_irrelevant_docs():
    result = decide_to_generate({"web_search": True, "web_search_enabled": False})

    assert result == GENERATE


def test_decide_generates_when_all_docs_relevant_regardless_of_toggle():
    assert decide_to_generate({"web_search": False, "web_search_enabled": True}) == GENERATE
    assert decide_to_generate({"web_search": False, "web_search_enabled": False}) == GENERATE


# ---------------------------------------------------------------------------
# grade_generation
# ---------------------------------------------------------------------------


def test_grade_useful_ends_regardless_of_toggle(monkeypatch):
    _patch_graders(monkeypatch, grounded=True, useful=True)

    assert grade_generation(_generation_state(web_search_enabled=True)) == "useful"
    assert grade_generation(_generation_state(web_search_enabled=False)) == "useful"


def test_grade_not_useful_enabled_goes_to_websearch(monkeypatch):
    _patch_graders(monkeypatch, grounded=True, useful=False)

    result = grade_generation(_generation_state(web_search_enabled=True))

    assert result == "not_useful"


def test_grade_not_useful_disabled_stops_instead_of_websearch(monkeypatch):
    _patch_graders(monkeypatch, grounded=True, useful=False)

    result = grade_generation(_generation_state(web_search_enabled=False))

    assert result == "web_search_disabled"


def test_grade_not_useful_enabled_at_retry_limit_stops(monkeypatch):
    _patch_graders(monkeypatch, grounded=True, useful=False)

    result = grade_generation(_generation_state(web_search_enabled=True, retries=MAX_RETRIES))

    assert result == "max_retries_not_useful"


def test_grade_not_grounded_regenerates_regardless_of_toggle(monkeypatch):
    # The regenerate loop doesn't involve web search; the toggle must not affect it.
    _patch_graders(monkeypatch, grounded=False, useful=True)

    assert grade_generation(_generation_state(web_search_enabled=True)) == "not_grounded"
    assert grade_generation(_generation_state(web_search_enabled=False)) == "not_grounded"


def test_grade_not_grounded_at_retry_limit_stops(monkeypatch):
    _patch_graders(monkeypatch, grounded=False, useful=True)

    result = grade_generation(_generation_state(web_search_enabled=False, retries=MAX_RETRIES))

    assert result == "max_retries_not_grounded"


# ---------------------------------------------------------------------------
# Compiled graph end-to-end (all external seams mocked)
# ---------------------------------------------------------------------------


def _patch_all_node_seams(monkeypatch, *, docs_relevant, web_relevant=True):
    """
    Mock every external seam used by the compiled graph and return the list of
    web-search invocations for assertions. `web_relevant` drives the relevance
    gate the web_search node applies to external results.
    """

    retrieve_module = importlib.import_module("graph.nodes.retrieve")
    grade_module = importlib.import_module("graph.nodes.grade_documents")
    generate_module = importlib.import_module("graph.nodes.generate")
    web_module = importlib.import_module("graph.nodes.web_search")

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
        generate_module,
        "generate_answer",
        lambda question, documents, retry_feedback="": "FINAL ANSWER",
    )

    web_calls = []

    class FakeWebTool:
        def invoke(self, payload):
            web_calls.append(payload)
            return [{"content": "web result"}]

    monkeypatch.setattr(web_module, "get_web_search_tool", lambda: FakeWebTool())
    monkeypatch.setattr(
        web_module,
        "get_retrieval_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_relevant=web_relevant)),
    )

    rewrite_module = importlib.import_module("graph.nodes.rewrite_query")
    monkeypatch.setattr(
        rewrite_module,
        "get_query_rewriter",
        lambda: SimpleNamespace(invoke=lambda p: "rewritten query"),
    )
    return web_calls


def _initial_state(enabled):
    return {
        "question": "Q",
        "documents": [],
        "generation": "",
        "web_search": False,
        "web_search_enabled": enabled,
        "retries": 0,
        "stop_reason": "",
        "retry_feedback": "",
        "search_query": "",
    }


def test_app_enabled_uses_web_search_when_routed_there(monkeypatch):
    _patch_router(monkeypatch, WEBSEARCH)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_all_node_seams(monkeypatch, docs_relevant=True)

    result = graph_module.app.invoke(_initial_state(enabled=True))

    assert web_calls == [{"query": "Q"}]
    assert result["generation"] == "FINAL ANSWER"
    assert result["stop_reason"] == ""  # normal finish, no caveat for the caller


def test_app_disabled_never_calls_web_search_and_records_stop_reason(monkeypatch):
    # Worst case for privacy mode: the router WOULD choose websearch, every
    # retrieved doc is graded irrelevant (normally triggering the fallback),
    # and the grounded answer is judged not useful (normally triggering a
    # websearch supplement). The web tool must still never be invoked, and
    # the run must end with a machine-readable stop reason for the caveat.
    _patch_router(monkeypatch, WEBSEARCH)
    _patch_graders(monkeypatch, grounded=True, useful=False)
    web_calls = _patch_all_node_seams(monkeypatch, docs_relevant=False)

    result = graph_module.app.invoke(_initial_state(enabled=False))

    assert web_calls == []
    assert result["generation"] == "FINAL ANSWER"
    assert result["documents"] == []  # irrelevant docs filtered, nothing fetched from the web
    assert result["stop_reason"] == STOP_REASON_WEB_SEARCH_DISABLED


def test_app_enabled_continues_safely_when_web_results_irrelevant(monkeypatch):
    # The router sends the question straight to web search, but every web
    # result is graded irrelevant -> nothing is appended and the run still
    # completes normally instead of crashing or polluting the context.
    _patch_router(monkeypatch, WEBSEARCH)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_all_node_seams(monkeypatch, docs_relevant=True, web_relevant=False)

    result = graph_module.app.invoke(_initial_state(enabled=True))

    assert len(web_calls) == 1
    assert result["documents"] == []  # irrelevant web content was dropped
    assert result["generation"] == "FINAL ANSWER"
    assert result["stop_reason"] == ""


def test_app_disabled_successful_answer_has_no_stop_reason(monkeypatch):
    # Privacy mode with a good local answer: the run ends through "useful",
    # never touching the notice node -- no caveat must be attached.
    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_all_node_seams(monkeypatch, docs_relevant=True)

    result = graph_module.app.invoke(_initial_state(enabled=False))

    assert web_calls == []
    assert result["generation"] == "FINAL ANSWER"
    assert result["stop_reason"] == ""


# ---------------------------------------------------------------------------
# web_search_disabled_notice node + main.format_answer (user-facing caveat)
# ---------------------------------------------------------------------------


def test_notice_node_records_stop_reason_and_leaves_generation_alone():
    result = web_search_disabled_notice(_generation_state(web_search_enabled=False))

    assert result == {"stop_reason": STOP_REASON_WEB_SEARCH_DISABLED}


def test_format_answer_appends_caveat_on_web_search_disabled_stop():
    result = {
        "generation": "Partial answer.",
        "stop_reason": STOP_REASON_WEB_SEARCH_DISABLED,
    }

    formatted = format_answer(result)

    assert formatted.startswith("Partial answer.")
    assert WEB_SEARCH_DISABLED_NOTE in formatted


def test_format_answer_returns_plain_answer_on_normal_finish():
    result = {"generation": "Full answer.", "stop_reason": ""}

    assert format_answer(result) == "Full answer."


def test_format_answer_returns_plain_answer_when_stop_reason_missing():
    # Callers that never seed stop_reason must keep today's output unchanged.
    assert format_answer({"generation": "Full answer."}) == "Full answer."
