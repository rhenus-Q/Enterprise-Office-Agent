"""
Tests for meaningful retry behavior.

Retries must change something between attempts:
- A failed grounding check routes through add_grounding_feedback, so the next
  generation receives a corrective instruction.
- A failed usefulness check routes through rewrite_query, so the next web
  search runs a more specific rewritten query (and the web supplement is
  replaced, not stacked).

All external seams are mocked -- no API keys or network required.
"""

import importlib
from types import SimpleNamespace

from langchain_core.documents import Document

import graph.graph as graph_module
from graph.consts import RETRIEVE, WEBSEARCH
from graph.nodes.add_grounding_feedback import GROUNDING_FEEDBACK, add_grounding_feedback
from graph.nodes.rewrite_query import rewrite_query

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_router(monkeypatch, datasource):
    monkeypatch.setattr(
        graph_module,
        "get_question_router",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(datasource=datasource)),
    )


def _patch_graders_sequence(monkeypatch, grounded_seq, useful_seq):
    """Graders whose verdicts change per call, to drive retry-then-succeed flows."""

    grounded_iter = iter(grounded_seq)
    useful_iter = iter(useful_seq)

    monkeypatch.setattr(
        graph_module,
        "get_hallucination_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_grounded=next(grounded_iter))),
    )
    monkeypatch.setattr(
        graph_module,
        "get_answer_grader",
        lambda: SimpleNamespace(
            invoke=lambda p: SimpleNamespace(answers_question=next(useful_iter))
        ),
    )


def _patch_all_node_seams(
    monkeypatch, *, docs_relevant=True, rewritten_query="more specific query"
):
    """
    Mock every external seam. Returns recorders:
    - web_calls: payloads sent to the web search tool
    - rewrite_calls: payloads sent to the query rewriter chain
    - feedbacks: retry_feedback received by each generate_answer call
    """

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

    feedbacks = []

    def fake_generate_answer(question, documents, retry_feedback=""):
        feedbacks.append(retry_feedback)
        return f"ANSWER {len(feedbacks)}"

    monkeypatch.setattr(generate_module, "generate_answer", fake_generate_answer)

    web_calls = []

    class FakeWebTool:
        def invoke(self, payload):
            web_calls.append(payload)
            return [{"content": f"web result {len(web_calls)}"}]

    monkeypatch.setattr(web_module, "get_web_search_tool", lambda: FakeWebTool())

    rewrite_calls = []

    class FakeRewriter:
        def invoke(self, payload):
            rewrite_calls.append(payload)
            return rewritten_query

    monkeypatch.setattr(rewrite_module, "get_query_rewriter", lambda: FakeRewriter())

    return web_calls, rewrite_calls, feedbacks


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
# Node units
# ---------------------------------------------------------------------------


def test_add_grounding_feedback_records_feedback_only():
    result = add_grounding_feedback({"question": "Q"})

    assert result == {"retry_feedback": GROUNDING_FEEDBACK}


def test_rewrite_query_calls_rewriter_with_question_and_previous_answer(monkeypatch):
    rewrite_module = importlib.import_module("graph.nodes.rewrite_query")

    calls = []
    monkeypatch.setattr(
        rewrite_module,
        "get_query_rewriter",
        lambda: SimpleNamespace(invoke=lambda p: calls.append(p) or "  new query  "),
    )

    result = rewrite_query({"question": "Q", "generation": "bad answer"})

    assert calls == [{"question": "Q", "previous_answer": "bad answer"}]
    assert result["search_query"] == "new query"  # output is stripped
    assert result["llm_call_count"] == 1  # the rewrite is a counted LLM call


# ---------------------------------------------------------------------------
# generate_answer folds retry feedback into the chain input
# ---------------------------------------------------------------------------


def test_generate_answer_folds_feedback_into_question_input(monkeypatch):
    generation_module = importlib.import_module("graph.chains.generation")

    payloads = []
    monkeypatch.setattr(
        generation_module,
        "get_generation_chain",
        lambda: SimpleNamespace(invoke=lambda p: payloads.append(p) or "ok"),
    )

    docs = [Document(page_content="d")]
    generation_module.generate_answer("Q", docs, "use only supported facts")

    assert "Q" in payloads[0]["question"]
    assert "use only supported facts" in payloads[0]["question"]


def test_generate_answer_without_feedback_keeps_question_unchanged(monkeypatch):
    generation_module = importlib.import_module("graph.chains.generation")

    payloads = []
    monkeypatch.setattr(
        generation_module,
        "get_generation_chain",
        lambda: SimpleNamespace(invoke=lambda p: payloads.append(p) or "ok"),
    )

    generation_module.generate_answer("Q", [Document(page_content="d")])

    assert payloads[0]["question"] == "Q"


def test_generate_answer_with_feedback_still_short_circuits_on_empty_docs(monkeypatch):
    generation_module = importlib.import_module("graph.chains.generation")

    def explode():
        raise AssertionError("chain must not be built for empty documents")

    monkeypatch.setattr(generation_module, "get_generation_chain", explode)

    result = generation_module.generate_answer("Q", [], "feedback")

    assert result == generation_module.INSUFFICIENT_CONTEXT_ANSWER


# ---------------------------------------------------------------------------
# Compiled graph end-to-end
# ---------------------------------------------------------------------------


def test_app_not_grounded_retry_receives_grounding_feedback(monkeypatch):
    # Attempt 1 fails grounding -> feedback node -> attempt 2 grounded+useful.
    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders_sequence(monkeypatch, grounded_seq=[False, True], useful_seq=[True])
    web_calls, rewrite_calls, feedbacks = _patch_all_node_seams(monkeypatch)

    result = graph_module.app.invoke(_initial_state())

    assert feedbacks == ["", GROUNDING_FEEDBACK]  # retry input differs from attempt 1
    assert result["generation"] == "ANSWER 2"
    assert result["stop_reason"] == ""
    assert web_calls == []
    assert rewrite_calls == []


def test_app_not_useful_retry_searches_with_rewritten_query(monkeypatch):
    # Attempt 1 is grounded but not useful -> rewrite -> websearch -> attempt 2 passes.
    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders_sequence(monkeypatch, grounded_seq=[True, True], useful_seq=[False, True])
    web_calls, rewrite_calls, feedbacks = _patch_all_node_seams(monkeypatch)

    result = graph_module.app.invoke(_initial_state())

    assert rewrite_calls == [{"question": "Q", "previous_answer": "ANSWER 1"}]
    assert web_calls == [{"query": "more specific query"}]  # not the original question
    assert result["search_query"] == "more specific query"
    assert result["generation"] == "ANSWER 2"
    assert result["stop_reason"] == ""


def test_app_first_pass_web_search_still_uses_original_question(monkeypatch):
    # Entry routing to websearch (no retry yet) must search with the question.
    _patch_router(monkeypatch, WEBSEARCH)
    _patch_graders_sequence(monkeypatch, grounded_seq=[True], useful_seq=[True])
    web_calls, rewrite_calls, _ = _patch_all_node_seams(monkeypatch)

    result = graph_module.app.invoke(_initial_state())

    assert web_calls == [{"query": "Q"}]
    assert rewrite_calls == []
    assert result["stop_reason"] == ""


def test_app_disabled_mode_never_rewrites_or_searches(monkeypatch):
    # Privacy mode + not useful: ends via web_search_disabled BEFORE any
    # rewrite, so neither the rewriter chain nor the web tool is ever called.
    _patch_router(monkeypatch, RETRIEVE)
    _patch_graders_sequence(monkeypatch, grounded_seq=[True], useful_seq=[False])
    web_calls, rewrite_calls, _ = _patch_all_node_seams(monkeypatch)

    result = graph_module.app.invoke(_initial_state(enabled=False))

    assert web_calls == []
    assert rewrite_calls == []
    assert result["stop_reason"] == "web_search_disabled"
