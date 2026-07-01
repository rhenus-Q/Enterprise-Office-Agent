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
from office_agent.schemas import INTENT_KNOWLEDGE_QA
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
