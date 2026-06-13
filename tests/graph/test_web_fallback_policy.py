"""
Tests for the configurable web-fallback policy (WEB_FALLBACK_POLICY, ADR 011).

The policy tunes when document grading triggers web fallback while web search
is otherwise allowed:
- conservative (default): generate when at least one relevant local doc
  remains; web only when none remain.
- aggressive: legacy CRAG behavior — any irrelevant doc triggers web fallback.
- disabled: local retrieval paths never escalate to the web, including the
  post-generation not-useful retry on local-only runs.

WEB_SEARCH_ENABLED=false (privacy mode) overrides every policy value.

All external seams are mocked -- no API keys or network required.
"""

import importlib
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

import graph.graph as graph_module
from graph.chains.generation import INSUFFICIENT_CONTEXT_ANSWER
from graph.config import (
    WEB_FALLBACK_AGGRESSIVE,
    WEB_FALLBACK_CONSERVATIVE,
    WEB_FALLBACK_DISABLED,
    web_fallback_policy,
)
from graph.consts import (
    GENERATE,
    RETRIEVE,
    STOP_REASON_WEB_FALLBACK_DISABLED,
    WEBSEARCH,
)
from graph.graph import decide_to_generate, grade_generation
from graph.nodes.web_fallback_disabled_notice import web_fallback_disabled_notice
from main import WEB_FALLBACK_DISABLED_NOTE, format_answer

# ---------------------------------------------------------------------------
# graph.config.web_fallback_policy -- env parsing
# ---------------------------------------------------------------------------


def test_config_defaults_to_conservative_when_unset(monkeypatch):
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)

    assert web_fallback_policy() == WEB_FALLBACK_CONSERVATIVE


@pytest.mark.parametrize(
    "value, expected",
    [
        ("conservative", WEB_FALLBACK_CONSERVATIVE),
        ("aggressive", WEB_FALLBACK_AGGRESSIVE),
        ("disabled", WEB_FALLBACK_DISABLED),
        (" Aggressive ", WEB_FALLBACK_AGGRESSIVE),  # case/whitespace tolerant
        ("DISABLED", WEB_FALLBACK_DISABLED),
    ],
)
def test_config_accepts_known_policies(monkeypatch, value, expected):
    monkeypatch.setenv("WEB_FALLBACK_POLICY", value)

    assert web_fallback_policy() == expected


@pytest.mark.parametrize("value", ["", "bogus", "true", "0"])
def test_config_invalid_values_fall_back_to_conservative(monkeypatch, value):
    monkeypatch.setenv("WEB_FALLBACK_POLICY", value)

    assert web_fallback_policy() == WEB_FALLBACK_CONSERVATIVE


# ---------------------------------------------------------------------------
# decide_to_generate under each policy (pure reads)
# ---------------------------------------------------------------------------


def _graded_state(*, relevant_docs, web_search=True, enabled=True):
    return {
        "question": "Q",
        "documents": [Document(page_content=f"d{i}") for i in range(relevant_docs)],
        "web_search": web_search,
        "web_search_enabled": enabled,
    }


def test_conservative_generates_when_relevant_docs_remain(monkeypatch):
    # Case A: 2 relevant docs survived grading, 1 was filtered out.
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)

    assert decide_to_generate(_graded_state(relevant_docs=2)) == GENERATE


def test_conservative_falls_back_to_web_when_no_relevant_docs_remain(monkeypatch):
    # Case B: every retrieved doc was graded irrelevant.
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)

    assert decide_to_generate(_graded_state(relevant_docs=0)) == WEBSEARCH


def test_aggressive_preserves_legacy_fallback(monkeypatch):
    # Case C: any irrelevant doc triggers web search even with relevant docs left.
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "aggressive")

    assert decide_to_generate(_graded_state(relevant_docs=2)) == WEBSEARCH
    assert decide_to_generate(_graded_state(relevant_docs=0)) == WEBSEARCH


def test_disabled_blocks_retrieval_triggered_fallback(monkeypatch):
    # Case D: never web search from the grading decision, even with zero docs.
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "disabled")

    assert decide_to_generate(_graded_state(relevant_docs=2)) == GENERATE
    assert decide_to_generate(_graded_state(relevant_docs=0)) == GENERATE


@pytest.mark.parametrize("policy", ["conservative", "aggressive", "disabled"])
def test_privacy_mode_overrides_every_policy(monkeypatch, policy):
    # Case E: WEB_SEARCH_ENABLED=false wins over any fallback policy.
    monkeypatch.setenv("WEB_FALLBACK_POLICY", policy)

    assert decide_to_generate(_graded_state(relevant_docs=0, enabled=False)) == GENERATE


def test_all_docs_relevant_generates_under_every_policy(monkeypatch):
    for policy in ("conservative", "aggressive", "disabled"):
        monkeypatch.setenv("WEB_FALLBACK_POLICY", policy)
        assert decide_to_generate(_graded_state(relevant_docs=3, web_search=False)) == GENERATE


# ---------------------------------------------------------------------------
# grade_generation: disabled policy blocks the not-useful web retry on
# local-only runs (web_search_count == 0)
# ---------------------------------------------------------------------------


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


def _generation_state(**overrides):
    state = {
        "question": "Q",
        "documents": [Document(page_content="d")],
        "generation": "A",
        "web_search": False,
        "web_search_enabled": True,
        "retries": 1,
        "stop_reason": "",
        "insufficient_context": False,
        "retry_feedback": "",
        "search_query": "",
        "llm_call_count": 0,
        "web_search_count": 0,
        "web_result_grading_count": 0,
    }
    state.update(overrides)
    return state


def test_disabled_policy_stops_not_useful_local_run(monkeypatch):
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "disabled")
    _patch_graders(monkeypatch, grounded=True, useful=False)

    result = grade_generation(_generation_state(web_search_count=0))

    assert result == "web_fallback_disabled"


def test_disabled_policy_lets_web_originated_runs_retry_their_search(monkeypatch):
    # A run that already used web search (router-initiated) was never a
    # local-path fallback; its not-useful retry stays allowed.
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "disabled")
    _patch_graders(monkeypatch, grounded=True, useful=False)

    result = grade_generation(_generation_state(web_search_count=1))

    assert result == "not_useful"


def test_conservative_policy_keeps_not_useful_web_retry(monkeypatch):
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)
    _patch_graders(monkeypatch, grounded=True, useful=False)

    assert grade_generation(_generation_state()) == "not_useful"


def test_privacy_mode_wins_over_disabled_policy_in_grading(monkeypatch):
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "disabled")
    _patch_graders(monkeypatch, grounded=True, useful=False)

    result = grade_generation(_generation_state(web_search_enabled=False))

    assert result == "web_search_disabled"


def test_useful_answers_are_unaffected_by_the_policy(monkeypatch):
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "disabled")
    _patch_graders(monkeypatch, grounded=True, useful=True)

    assert grade_generation(_generation_state()) == "useful"


def test_direct_graph_caller_without_policy_field_falls_back_to_env_in_grade_generation(
    monkeypatch,
):
    # Compatibility: a direct app.invoke() caller that seeds state without
    # web_fallback_policy gets the env-driven default from
    # _resolve_web_fallback_policy(), exactly as callers that predate the
    # engine did. Engine-driven runs (answer_question / seed_state) always
    # have the field pre-populated so this path is a no-op for them.
    # The parallel decide_to_generate case is in test_engine.py::
    # test_missing_state_policy_falls_back_to_environment.
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "disabled")
    _patch_graders(monkeypatch, grounded=True, useful=False)

    state = _generation_state(web_search_count=0)
    assert "web_fallback_policy" not in state  # direct-caller state, field absent

    assert grade_generation(state) == "web_fallback_disabled"


# ---------------------------------------------------------------------------
# Notice node + caveat formatting
# ---------------------------------------------------------------------------


def test_fallback_notice_records_stop_reason_only():
    result = web_fallback_disabled_notice(_generation_state())

    assert result == {"stop_reason": STOP_REASON_WEB_FALLBACK_DISABLED}


def test_format_answer_appends_fallback_policy_caveat():
    result = {
        "generation": "Local-only answer.",
        "stop_reason": STOP_REASON_WEB_FALLBACK_DISABLED,
    }

    formatted = format_answer(result)

    assert formatted.startswith("Local-only answer.")
    assert WEB_FALLBACK_DISABLED_NOTE in formatted


# ---------------------------------------------------------------------------
# Compiled graph end-to-end
# ---------------------------------------------------------------------------


def _patch_node_seams(monkeypatch, *, relevance_by_content, retrieved=("rel-1", "rel-2", "irrel")):
    """Mock every external seam; per-chunk relevance comes from a content map."""

    retrieve_module = importlib.import_module("graph.nodes.retrieve")
    grade_module = importlib.import_module("graph.nodes.grade_documents")
    generate_module = importlib.import_module("graph.nodes.generate")
    web_module = importlib.import_module("graph.nodes.web_search")
    rewrite_module = importlib.import_module("graph.nodes.rewrite_query")

    monkeypatch.setattr(
        retrieve_module,
        "get_node_retriever",
        lambda: SimpleNamespace(invoke=lambda q: [Document(page_content=c) for c in retrieved]),
    )
    monkeypatch.setattr(
        grade_module,
        "get_retrieval_grader",
        lambda: SimpleNamespace(
            invoke=lambda p: SimpleNamespace(
                is_relevant=relevance_by_content.get(p["document"], True)
            )
        ),
    )
    monkeypatch.setattr(
        web_module,
        "get_retrieval_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_relevant=True)),
    )
    monkeypatch.setattr(
        generate_module,
        "generate_answer",
        lambda question, documents, retry_feedback="": (
            "FINAL ANSWER" if documents else INSUFFICIENT_CONTEXT_ANSWER
        ),
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


def _patch_router(monkeypatch, datasource=RETRIEVE):
    monkeypatch.setattr(
        graph_module,
        "get_question_router",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(datasource=datasource)),
    )


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


def test_app_conservative_mixed_relevance_stays_local(monkeypatch):
    # Case A end-to-end: 2 relevant + 1 irrelevant chunk -> generate locally,
    # zero web calls, clean finish.
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)
    _patch_router(monkeypatch)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_node_seams(monkeypatch, relevance_by_content={"irrel": False})

    result = graph_module.app.invoke(_initial_state())

    assert web_calls == []
    assert result["generation"] == "FINAL ANSWER"
    assert len(result["documents"]) == 2  # the irrelevant chunk was filtered
    assert result["stop_reason"] == ""


def test_app_conservative_all_irrelevant_falls_back_to_web(monkeypatch):
    # Case B end-to-end: nothing relevant locally -> one web fallback search.
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)
    _patch_router(monkeypatch)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_node_seams(
        monkeypatch,
        relevance_by_content={"rel-1": False, "rel-2": False, "irrel": False},
    )

    result = graph_module.app.invoke(_initial_state())

    assert len(web_calls) == 1
    assert result["generation"] == "FINAL ANSWER"
    assert result["web_search_count"] == 1


def test_app_aggressive_mixed_relevance_uses_web(monkeypatch):
    # Case C end-to-end: legacy behavior restored by the env var.
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "aggressive")
    _patch_router(monkeypatch)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_node_seams(monkeypatch, relevance_by_content={"irrel": False})

    result = graph_module.app.invoke(_initial_state())

    assert len(web_calls) == 1
    assert result["generation"] == "FINAL ANSWER"


def test_app_disabled_all_irrelevant_declines_without_web(monkeypatch):
    # Case D end-to-end: no retrieval-triggered fallback; the run declines
    # honestly through the insufficient-context bypass.
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "disabled")
    _patch_router(monkeypatch)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_node_seams(
        monkeypatch,
        relevance_by_content={"rel-1": False, "rel-2": False, "irrel": False},
    )

    result = graph_module.app.invoke(_initial_state())

    assert web_calls == []
    assert result["generation"] == INSUFFICIENT_CONTEXT_ANSWER
    assert result["retries"] == 1  # bypass: no retry loop
    assert result["stop_reason"] == ""  # clean honest decline


def test_app_disabled_not_useful_local_run_stops_with_policy_caveat(monkeypatch):
    # disabled also blocks the post-generation not-useful web retry on a
    # local-only run; the answer ships with the policy caveat.
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "disabled")
    _patch_router(monkeypatch)
    _patch_graders(monkeypatch, grounded=True, useful=False)
    web_calls = _patch_node_seams(monkeypatch, relevance_by_content={})

    result = graph_module.app.invoke(_initial_state())

    assert web_calls == []
    assert result["stop_reason"] == STOP_REASON_WEB_FALLBACK_DISABLED
    assert WEB_FALLBACK_DISABLED_NOTE in format_answer(result)


@pytest.mark.parametrize("policy", ["conservative", "aggressive", "disabled"])
def test_app_privacy_mode_blocks_web_under_every_policy(monkeypatch, policy):
    # Case E end-to-end: the hard privacy switch wins over any policy value.
    monkeypatch.setenv("WEB_FALLBACK_POLICY", policy)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_node_seams(
        monkeypatch,
        relevance_by_content={"rel-1": False, "rel-2": False, "irrel": False},
    )

    result = graph_module.app.invoke(_initial_state(enabled=False))

    assert web_calls == []
    assert result["generation"] == INSUFFICIENT_CONTEXT_ANSWER
