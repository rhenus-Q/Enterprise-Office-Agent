"""
Unit tests for the Knowledge Q&A adapter (office_agent/tools/knowledge.py).

The enterprise_rag engine is mocked at the adapter's seam
(`office_agent.tools.knowledge.answer_question`) — no OpenAI / Tavily / Chroma
and no real graph run. `format_answer` is exercised for real (it is pure) so
the test proves caveats and the Sources section survive the adapter.
"""

from types import SimpleNamespace

from langchain_core.documents import Document

from enterprise_rag.graph.consts import STOP_REASON_WEB_SEARCH_DISABLED
from enterprise_rag.graph.formatting import WEB_SEARCH_DISABLED_NOTE
from office_agent.schemas import INTENT_KNOWLEDGE_QA, NodeTiming
from office_agent.tools import knowledge


def _fake_answer_result():
    """A stand-in for enterprise_rag.graph.engine.AnswerResult."""

    raw_state = {
        "generation": "Submit the VPN Access Request form in the IT Service Portal.",
        "stop_reason": STOP_REASON_WEB_SEARCH_DISABLED,
        "documents": [
            Document(
                page_content="(chunk text — never surfaced by format_answer)",
                metadata={
                    "source": "enterprise_rag/data/acmecorp_internal_docs/vpn_policy.md",
                    "title": "AcmeCorp VPN Access Policy",
                },
            )
        ],
    }
    return SimpleNamespace(
        raw_state=raw_state,
        stop_reason=STOP_REASON_WEB_SEARCH_DISABLED,
        sources=["- Local corpus: AcmeCorp VPN Access Policy"],
        run_id="run-123",
        # The execution metadata the adapter carries through (Phase 4). The
        # engine emits timings as plain dicts; the adapter re-types them.
        node_path=["retrieve", "grade_documents", "generate"],
        node_timings_ms=[
            {"node": "retrieve", "duration_ms": 12.5},
            {"node": "grade_documents", "duration_ms": 340.0},
            {"node": "generate", "duration_ms": 1180.75},
        ],
        total_duration_ms=1533.25,
        retries=1,
        tracked_llm_calls=4,
        web_search_count=0,
        web_result_grading_count=0,
        web_search_enabled=False,
        web_fallback_policy="conservative",
    )


def test_run_knowledge_qa_calls_enterprise_rag_engine(monkeypatch):
    calls = []

    def fake_answer_question(question):
        calls.append(question)
        return _fake_answer_result()

    monkeypatch.setattr(knowledge, "answer_question", fake_answer_question)

    result = knowledge.run_knowledge_qa("How do I request VPN access?")

    assert calls == ["How do I request VPN access?"]
    assert result.tool == INTENT_KNOWLEDGE_QA
    assert result.run_id == "run-123"
    assert result.stop_reason == STOP_REASON_WEB_SEARCH_DISABLED
    assert result.sources == ["- Local corpus: AcmeCorp VPN Access Policy"]


def test_run_knowledge_qa_preserves_caveat_and_sources(monkeypatch):
    monkeypatch.setattr(knowledge, "answer_question", lambda question: _fake_answer_result())

    result = knowledge.run_knowledge_qa("How do I request VPN access?")

    # The raw generation, the stop-reason caveat, and the Sources section must
    # all survive the adapter unchanged (format_answer output is not altered).
    assert "Submit the VPN Access Request form" in result.content
    assert WEB_SEARCH_DISABLED_NOTE in result.content
    assert "Sources:" in result.content
    assert "AcmeCorp VPN Access Policy" in result.content


def test_run_knowledge_qa_carries_engine_observability(monkeypatch):
    """Every AnswerResult metadata field survives the adapter unchanged."""

    monkeypatch.setattr(knowledge, "answer_question", lambda question: _fake_answer_result())

    observability = knowledge.run_knowledge_qa("How do I request VPN access?").observability

    assert observability is not None
    assert observability.run_id == "run-123"
    assert observability.node_path == ["retrieve", "grade_documents", "generate"]
    assert observability.total_duration_ms == 1533.25
    assert observability.retries == 1
    assert observability.tracked_llm_calls == 4
    assert observability.web_search_count == 0
    assert observability.web_result_grading_count == 0
    assert observability.web_search_enabled is False
    assert observability.web_fallback_policy == "conservative"


def test_run_knowledge_qa_retypes_every_timing_entry(monkeypatch):
    """The engine's dict entries become typed NodeTiming values, in order."""

    monkeypatch.setattr(knowledge, "answer_question", lambda question: _fake_answer_result())

    observability = knowledge.run_knowledge_qa("How do I request VPN access?").observability

    assert observability is not None
    timings = observability.node_timings_ms
    assert all(isinstance(timing, NodeTiming) for timing in timings)
    assert [timing.node for timing in timings] == [
        "retrieve",
        "grade_documents",
        "generate",
    ]
    assert [timing.duration_ms for timing in timings] == [12.5, 340.0, 1180.75]


def test_run_knowledge_qa_caveat_reuses_stop_reason_notes(monkeypatch):
    """The caveat is the engine's own STOP_REASON_NOTES text, not a rewrite."""

    monkeypatch.setattr(knowledge, "answer_question", lambda question: _fake_answer_result())

    observability = knowledge.run_knowledge_qa("How do I request VPN access?").observability

    assert observability is not None
    assert observability.caveat == WEB_SEARCH_DISABLED_NOTE


def test_run_knowledge_qa_caveat_is_empty_on_a_normal_run(monkeypatch):
    """A run with no stop reason has no caveat — nothing is invented."""

    result = _fake_answer_result()
    result.stop_reason = ""
    result.raw_state["stop_reason"] = ""
    monkeypatch.setattr(knowledge, "answer_question", lambda question: result)

    observability = knowledge.run_knowledge_qa("How do I request VPN access?").observability

    assert observability is not None
    assert observability.caveat == ""
