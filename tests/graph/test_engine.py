"""
Tests for the canonical engine API (graph/engine.py): answer_question /
AnswerOptions / AnswerResult, the centralized state seeding (seed_state),
and the per-run resolution of WEB_FALLBACK_POLICY into GraphState.

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
    normalize_web_fallback_policy,
)
from graph.consts import GENERATE, RETRIEVE, WEBSEARCH
from graph.engine import AnswerOptions, AnswerResult, answer_question, seed_state
from graph.graph import decide_to_generate, grade_generation
from graph.state import GraphState

# ---------------------------------------------------------------------------
# normalize_web_fallback_policy
# ---------------------------------------------------------------------------


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
def test_normalize_accepts_known_policies(value, expected):
    assert normalize_web_fallback_policy(value) == expected


@pytest.mark.parametrize("value", [None, "", "bogus", "true", "0"])
def test_normalize_invalid_or_missing_falls_back_to_conservative(value):
    assert normalize_web_fallback_policy(value) == WEB_FALLBACK_CONSERVATIVE


# ---------------------------------------------------------------------------
# seed_state -- the single state-seeding helper
# ---------------------------------------------------------------------------


def test_seed_state_covers_every_graphstate_field(monkeypatch):
    monkeypatch.delenv("WEB_SEARCH_ENABLED", raising=False)
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)

    state = seed_state("Q")

    # Centralization guarantee: every GraphState field is seeded, so nodes
    # and conditional functions never read a missing key, and a new field
    # only needs one update site.
    assert set(state) == set(GraphState.__annotations__)
    assert state["question"] == "Q"
    assert state["documents"] == []
    assert state["generation"] == ""
    assert state["web_search"] is False
    assert state["web_search_enabled"] is True
    assert state["web_fallback_policy"] == WEB_FALLBACK_CONSERVATIVE
    assert state["retries"] == 0
    assert state["stop_reason"] == ""
    assert state["insufficient_context"] is False
    assert state["llm_call_count"] == 0
    assert state["web_search_count"] == 0
    assert state["web_result_grading_count"] == 0


def test_seed_state_reads_environment_defaults(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "false")
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "aggressive")

    state = seed_state("Q")

    assert state["web_search_enabled"] is False
    assert state["web_fallback_policy"] == WEB_FALLBACK_AGGRESSIVE


def test_seed_state_explicit_options_win_over_environment(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "false")
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "aggressive")

    state = seed_state("Q", web_search_enabled=True, web_fallback_policy="disabled")

    assert state["web_search_enabled"] is True
    assert state["web_fallback_policy"] == WEB_FALLBACK_DISABLED


def test_seed_state_normalizes_invalid_explicit_policy(monkeypatch):
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)

    state = seed_state("Q", web_fallback_policy="bogus")

    assert state["web_fallback_policy"] == WEB_FALLBACK_CONSERVATIVE


# ---------------------------------------------------------------------------
# answer_question -- structured result (fake compiled app)
# ---------------------------------------------------------------------------


class _FakeApp:
    """Stands in for the compiled graph; records the seeded state it got."""

    def __init__(self, final_state):
        self.final_state = final_state
        self.invoked_with = None

    def invoke(self, state):
        self.invoked_with = state
        return {**state, **self.final_state}

    def stream(self, state, stream_mode="updates"):
        # Mirrors LangGraph's update stream: one chunk per completed node,
        # holding that node's partial state update.
        self.invoked_with = state
        yield {"retrieve": {}}
        yield {"generate": dict(self.final_state)}


def _install_fake_app(monkeypatch, final_state):
    fake = _FakeApp(final_state)
    monkeypatch.setattr(graph_module, "app", fake)
    return fake


def test_answer_question_returns_structured_answer_result(monkeypatch):
    monkeypatch.delenv("WEB_SEARCH_ENABLED", raising=False)
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)
    _install_fake_app(
        monkeypatch,
        {
            "generation": "The answer.",
            "stop_reason": "",
            "documents": [
                Document(
                    page_content="chunk",
                    metadata={"source": "data/vpn_policy.md", "title": "VPN Policy"},
                )
            ],
            "retries": 2,
            "llm_call_count": 3,
            "web_search_count": 1,
            "web_result_grading_count": 2,
        },
    )

    result = answer_question("Q", AnswerOptions(run_id="run-1"))

    assert isinstance(result, AnswerResult)
    assert result.question == "Q"
    assert result.answer == "The answer."
    assert result.stop_reason == ""
    assert result.sources == ["- Local corpus: VPN Policy"]
    assert result.retries == 2
    assert result.tracked_llm_calls == 3
    assert result.web_search_count == 1
    assert result.web_result_grading_count == 2
    assert result.web_search_enabled is True
    assert result.web_fallback_policy == WEB_FALLBACK_CONSERVATIVE
    assert result.run_id == "run-1"
    # Raw final state stays available for internal callers/tests.
    assert result.raw_state["generation"] == "The answer."
    assert result.raw_state["question"] == "Q"


def test_answer_question_invokes_graph_with_centralized_seed(monkeypatch):
    fake = _install_fake_app(monkeypatch, {"generation": "A"})

    answer_question("Q", AnswerOptions(web_search_enabled=False, web_fallback_policy="disabled"))

    assert fake.invoked_with == seed_state(
        "Q", web_search_enabled=False, web_fallback_policy="disabled"
    )


def test_answer_question_accepts_plain_dict_options(monkeypatch):
    fake = _install_fake_app(monkeypatch, {"generation": "A"})

    result = answer_question("Q", {"web_fallback_policy": "aggressive", "run_id": "r"})

    assert fake.invoked_with["web_fallback_policy"] == WEB_FALLBACK_AGGRESSIVE
    assert result.web_fallback_policy == WEB_FALLBACK_AGGRESSIVE
    assert result.run_id == "r"


def test_answer_question_without_options_uses_environment_defaults(monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "false")
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "disabled")
    fake = _install_fake_app(monkeypatch, {"generation": "A"})

    result = answer_question("Q")

    assert fake.invoked_with["web_search_enabled"] is False
    assert result.web_search_enabled is False
    assert result.web_fallback_policy == WEB_FALLBACK_DISABLED
    # No caller-provided run_id: the engine generates one (observability).
    assert isinstance(result.run_id, str) and result.run_id


# ---------------------------------------------------------------------------
# Graph decisions read the policy from state, not os.environ
# ---------------------------------------------------------------------------


def _graded_state(*, relevant_docs, policy=None, web_search=True, enabled=True):
    state = {
        "question": "Q",
        "documents": [Document(page_content=f"d{i}") for i in range(relevant_docs)],
        "web_search": web_search,
        "web_search_enabled": enabled,
    }
    if policy is not None:
        state["web_fallback_policy"] = policy
    return state


def test_decide_to_generate_reads_policy_from_state_without_env(monkeypatch):
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)

    assert decide_to_generate(_graded_state(relevant_docs=2, policy="aggressive")) == WEBSEARCH
    assert decide_to_generate(_graded_state(relevant_docs=0, policy="disabled")) == GENERATE
    assert decide_to_generate(_graded_state(relevant_docs=2, policy="conservative")) == GENERATE
    assert decide_to_generate(_graded_state(relevant_docs=0, policy="conservative")) == WEBSEARCH


def test_state_policy_wins_over_environment(monkeypatch):
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "aggressive")

    assert decide_to_generate(_graded_state(relevant_docs=2, policy="conservative")) == GENERATE


def test_missing_state_policy_falls_back_to_environment(monkeypatch):
    # Legacy callers that seed state without the field keep the env-driven
    # behavior.
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "aggressive")

    assert decide_to_generate(_graded_state(relevant_docs=2)) == WEBSEARCH


def test_invalid_state_policy_normalizes_to_conservative(monkeypatch):
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)

    assert decide_to_generate(_graded_state(relevant_docs=2, policy="bogus")) == GENERATE
    assert decide_to_generate(_graded_state(relevant_docs=0, policy="bogus")) == WEBSEARCH


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
        "web_fallback_policy": WEB_FALLBACK_CONSERVATIVE,
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


def test_grade_generation_reads_disabled_policy_from_state(monkeypatch):
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)
    _patch_graders(monkeypatch, grounded=True, useful=False)

    state = _generation_state(web_fallback_policy="disabled", web_search_count=0)

    assert grade_generation(state) == "web_fallback_disabled"


def test_grade_generation_state_policy_wins_over_environment(monkeypatch):
    monkeypatch.setenv("WEB_FALLBACK_POLICY", "disabled")
    _patch_graders(monkeypatch, grounded=True, useful=False)

    state = _generation_state(web_fallback_policy="conservative", web_search_count=0)

    assert grade_generation(state) == "not_useful"


# ---------------------------------------------------------------------------
# answer_question end-to-end through the compiled graph (mocked seams)
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


def test_answer_question_per_run_aggressive_uses_web_without_env(monkeypatch):
    # The environment never specifies a policy; only the per-run option does.
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)
    monkeypatch.delenv("WEB_SEARCH_ENABLED", raising=False)
    _patch_router(monkeypatch)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_node_seams(monkeypatch, relevance_by_content={"irrel": False})

    result = answer_question("Q", AnswerOptions(web_fallback_policy="aggressive"))

    assert len(web_calls) == 1
    assert result.answer == "FINAL ANSWER"
    assert result.web_fallback_policy == WEB_FALLBACK_AGGRESSIVE
    assert result.web_search_count == 1


def test_answer_question_per_run_disabled_stays_local_without_env(monkeypatch):
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)
    monkeypatch.delenv("WEB_SEARCH_ENABLED", raising=False)
    _patch_router(monkeypatch)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_node_seams(
        monkeypatch,
        relevance_by_content={"rel-1": False, "rel-2": False, "irrel": False},
    )

    result = answer_question("Q", AnswerOptions(web_fallback_policy="disabled"))

    assert web_calls == []
    assert result.answer == INSUFFICIENT_CONTEXT_ANSWER
    assert result.stop_reason == ""  # clean honest decline
    assert result.web_fallback_policy == WEB_FALLBACK_DISABLED


def test_answer_question_privacy_option_overrides_aggressive_policy(monkeypatch):
    # The hard privacy guarantee: web_search_enabled=False (per run) means
    # zero external searches even under the most web-eager policy.
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)
    monkeypatch.delenv("WEB_SEARCH_ENABLED", raising=False)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_node_seams(
        monkeypatch,
        relevance_by_content={"rel-1": False, "rel-2": False, "irrel": False},
    )

    result = answer_question(
        "Q", AnswerOptions(web_search_enabled=False, web_fallback_policy="aggressive")
    )

    assert web_calls == []
    assert result.web_search_count == 0
    assert result.web_search_enabled is False
    assert result.answer == INSUFFICIENT_CONTEXT_ANSWER


# ---------------------------------------------------------------------------
# GraphState channel-type invariant (guards _run_graph_with_trace merge)
# ---------------------------------------------------------------------------


def test_graphstate_has_no_reducer_channels():
    import typing

    # _run_graph_with_trace merges streamed node updates with dict.update(),
    # which reproduces app.invoke() only when every GraphState channel is a
    # plain last-value overwrite. A LangGraph reducer channel is declared as
    # typing.Annotated[type, reducer_fn]; dict.update() would overwrite rather
    # than accumulate, silently diverging from invoke(). This test fails loudly
    # if any field gains a reducer annotation.
    for field_name, annotation in GraphState.__annotations__.items():
        assert typing.get_origin(annotation) is not typing.Annotated, (
            f"GraphState.{field_name!r} is typing.Annotated — potential reducer channel. "
            "_run_graph_with_trace merges streamed updates with dict.update(); "
            "an accumulating reducer would silently diverge from app.invoke()."
        )


def test_answer_question_privacy_env_overrides_aggressive_policy(monkeypatch):
    # WEB_SEARCH_ENABLED=false in the environment guarantees zero web
    # searches as well, with no per-run override needed.
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "false")
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)
    _patch_graders(monkeypatch, grounded=True, useful=True)
    web_calls = _patch_node_seams(
        monkeypatch,
        relevance_by_content={"rel-1": False, "rel-2": False, "irrel": False},
    )

    result = answer_question("Q", AnswerOptions(web_fallback_policy="aggressive"))

    assert web_calls == []
    assert result.web_search_count == 0
    assert result.web_search_enabled is False
