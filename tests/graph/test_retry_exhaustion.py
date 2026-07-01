"""
Tests for explicit max-retries exhaustion handling.

When the answer still fails a quality gate at the retry limit, the graph must
end through a terminal notice node that records which gate failed, and main.py
must append a clear warning instead of presenting the answer as successful.

All external seams are mocked -- no API keys or network required.
"""

import importlib
from types import SimpleNamespace

from langchain_core.documents import Document

import enterprise_rag.graph.graph as graph_module
from enterprise_rag.graph.consts import (
    RETRIEVE,
    STOP_REASON_MAX_RETRIES_NOT_GROUNDED,
    STOP_REASON_MAX_RETRIES_NOT_USEFUL,
)
from enterprise_rag.graph.graph import MAX_RETRIES, grade_generation
from enterprise_rag.graph.nodes.max_retries_notice import (
    max_retries_not_grounded_notice,
    max_retries_not_useful_notice,
)
from main import (
    MAX_RETRIES_NOT_GROUNDED_NOTE,
    MAX_RETRIES_NOT_USEFUL_NOTE,
    format_answer,
)

# ---------------------------------------------------------------------------
# Helpers (mirrors test_web_search_toggle.py)
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


def _generation_state(**overrides):
    state = {
        "question": "Q",
        "documents": [Document(page_content="d")],
        "generation": "A",
        "web_search": False,
        "web_search_enabled": True,
        "retries": 1,
        "stop_reason": "",
    }
    state.update(overrides)
    return state


def _patch_all_node_seams(monkeypatch, *, docs_relevant, web_relevant=True):
    """Mock every external seam; returns the recorded web-search invocations."""

    retrieve_module = importlib.import_module("enterprise_rag.graph.nodes.retrieve")
    grade_module = importlib.import_module("enterprise_rag.graph.nodes.grade_documents")
    generate_module = importlib.import_module("enterprise_rag.graph.nodes.generate")
    web_module = importlib.import_module("enterprise_rag.graph.nodes.web_search")

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

    rewrite_module = importlib.import_module("enterprise_rag.graph.nodes.rewrite_query")
    monkeypatch.setattr(
        rewrite_module,
        "get_query_rewriter",
        lambda: SimpleNamespace(invoke=lambda p: "rewritten query"),
    )
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
        "retry_feedback": "",
        "search_query": "",
    }


# ---------------------------------------------------------------------------
# grade_generation outcomes at the retry limit
# ---------------------------------------------------------------------------


def test_not_grounded_at_limit_returns_max_retries_not_grounded(monkeypatch):
    _patch_graders(monkeypatch, grounded=False, useful=True)

    result = grade_generation(_generation_state(retries=MAX_RETRIES))

    assert result == "max_retries_not_grounded"


def test_not_grounded_at_limit_same_outcome_in_privacy_mode(monkeypatch):
    # The regenerate loop doesn't involve web search; the toggle must not change this.
    _patch_graders(monkeypatch, grounded=False, useful=True)

    result = grade_generation(_generation_state(retries=MAX_RETRIES, web_search_enabled=False))

    assert result == "max_retries_not_grounded"


def test_not_useful_at_limit_returns_max_retries_not_useful(monkeypatch):
    _patch_graders(monkeypatch, grounded=True, useful=False)

    result = grade_generation(_generation_state(retries=MAX_RETRIES))

    assert result == "max_retries_not_useful"


def test_not_useful_at_limit_in_privacy_mode_keeps_web_search_disabled_reason(monkeypatch):
    # Precedence: with web search disabled, improvement was impossible regardless
    # of retries, so the privacy-mode outcome (and its caveat) wins.
    _patch_graders(monkeypatch, grounded=True, useful=False)

    result = grade_generation(_generation_state(retries=MAX_RETRIES, web_search_enabled=False))

    assert result == "web_search_disabled"


def test_below_limit_outcomes_are_unchanged(monkeypatch):
    _patch_graders(monkeypatch, grounded=False, useful=True)
    assert grade_generation(_generation_state(retries=MAX_RETRIES - 1)) == "not_grounded"

    _patch_graders(monkeypatch, grounded=True, useful=False)
    assert grade_generation(_generation_state(retries=MAX_RETRIES - 1)) == "not_useful"


# ---------------------------------------------------------------------------
# Notice nodes
# ---------------------------------------------------------------------------


def test_not_grounded_notice_records_stop_reason_only():
    result = max_retries_not_grounded_notice(_generation_state())

    assert result == {"stop_reason": STOP_REASON_MAX_RETRIES_NOT_GROUNDED}


def test_not_useful_notice_records_stop_reason_only():
    result = max_retries_not_useful_notice(_generation_state())

    assert result == {"stop_reason": STOP_REASON_MAX_RETRIES_NOT_USEFUL}


# ---------------------------------------------------------------------------
# main.format_answer caveats
# ---------------------------------------------------------------------------


def test_format_answer_warns_on_not_grounded_exhaustion():
    result = {
        "generation": "Possibly hallucinated answer.",
        "stop_reason": STOP_REASON_MAX_RETRIES_NOT_GROUNDED,
    }

    formatted = format_answer(result)

    assert formatted.startswith("Possibly hallucinated answer.")
    assert MAX_RETRIES_NOT_GROUNDED_NOTE in formatted


def test_format_answer_warns_on_not_useful_exhaustion():
    result = {
        "generation": "Grounded but off-target answer.",
        "stop_reason": STOP_REASON_MAX_RETRIES_NOT_USEFUL,
    }

    formatted = format_answer(result)

    assert formatted.startswith("Grounded but off-target answer.")
    assert MAX_RETRIES_NOT_USEFUL_NOTE in formatted


def test_format_answer_keeps_successful_answers_warning_free():
    assert format_answer({"generation": "Good answer.", "stop_reason": ""}) == "Good answer."


# ---------------------------------------------------------------------------
# Compiled graph end-to-end: drive the loop to actual exhaustion
# ---------------------------------------------------------------------------


def test_app_records_not_grounded_exhaustion(monkeypatch):
    # Every generation fails grounding -> regenerate until the cap, then the
    # notice node must record the stop reason. No web search is involved.
    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders(monkeypatch, grounded=False, useful=True)
    web_calls = _patch_all_node_seams(monkeypatch, docs_relevant=True)

    result = graph_module.app.invoke(_initial_state())

    assert result["stop_reason"] == STOP_REASON_MAX_RETRIES_NOT_GROUNDED
    assert result["retries"] == MAX_RETRIES  # the cap was actually exhausted
    assert result["generation"] == "FINAL ANSWER"
    assert web_calls == []


def test_app_records_not_useful_exhaustion_after_web_search_rounds(monkeypatch):
    # Every answer is grounded but off-target -> websearch + regenerate until
    # the cap. The web tool runs once per failed round before the cap.
    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders(monkeypatch, grounded=True, useful=False)
    web_calls = _patch_all_node_seams(monkeypatch, docs_relevant=True)

    result = graph_module.app.invoke(_initial_state())

    assert result["stop_reason"] == STOP_REASON_MAX_RETRIES_NOT_USEFUL
    assert result["retries"] == MAX_RETRIES
    assert len(web_calls) == MAX_RETRIES - 1  # one supplement between each generation
