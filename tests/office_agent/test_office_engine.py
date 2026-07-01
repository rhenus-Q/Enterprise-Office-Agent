"""
Unit tests for the Office Agent entry point (office_agent/engine.py).

The knowledge tool is mocked at the engine's seam
(`office_agent.tools.knowledge.run_knowledge_qa`), so these tests never touch
enterprise_rag, OpenAI, Tavily, or Chroma. They verify dispatch, not RAG.
"""

from office_agent import engine
from office_agent.formatting import UNSUPPORTED_INTENT_NOTE
from office_agent.schemas import INTENT_KNOWLEDGE_QA, INTENT_UNKNOWN, ToolResult
from office_agent.tools import knowledge


def test_knowledge_qa_request_dispatches_to_knowledge_tool(monkeypatch):
    calls = []

    def fake_tool(question):
        calls.append(question)
        return ToolResult(
            tool=INTENT_KNOWLEDGE_QA,
            content="FORMATTED ANSWER",
            stop_reason="",
            sources=["- Local corpus: AcmeCorp VPN Access Policy"],
            run_id="run-xyz",
        )

    monkeypatch.setattr(knowledge, "run_knowledge_qa", fake_tool)

    response = engine.answer_office_request("What is the VPN access policy?")

    assert calls == ["What is the VPN access policy?"]
    assert response.intent == INTENT_KNOWLEDGE_QA
    assert response.tool == INTENT_KNOWLEDGE_QA
    assert response.content == "FORMATTED ANSWER"
    assert response.sources == ["- Local corpus: AcmeCorp VPN Access Policy"]
    assert response.run_id == "run-xyz"


def test_unknown_request_returns_unsupported_message_without_calling_tool(monkeypatch):
    def boom(question):
        raise AssertionError("the knowledge tool must not run for unknown intents")

    monkeypatch.setattr(knowledge, "run_knowledge_qa", boom)

    response = engine.answer_office_request("Summarize my unread email.")

    assert response.intent == INTENT_UNKNOWN
    assert response.tool is None
    assert response.content == UNSUPPORTED_INTENT_NOTE
