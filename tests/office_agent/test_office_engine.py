"""
Unit tests for the Office Agent entry point (office_agent/engine.py).

The knowledge tool is mocked at the engine's seam
(`office_agent.tools.knowledge.run_knowledge_qa`), so these tests never touch
enterprise_rag, OpenAI, Tavily, or Chroma. They verify dispatch, not RAG.
"""

from office_agent import engine
from office_agent.formatting import UNSUPPORTED_INTENT_NOTE
from office_agent.schemas import (
    INTENT_EMAIL_SUMMARY,
    INTENT_KNOWLEDGE_QA,
    INTENT_UNKNOWN,
    ToolResult,
)
from office_agent.tools import email, knowledge


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

    def no_email(query):
        raise AssertionError("email tool must not run for a knowledge request")

    monkeypatch.setattr(knowledge, "run_knowledge_qa", fake_tool)
    monkeypatch.setattr(email, "summarize_emails", no_email)

    response = engine.answer_office_request("What is the VPN access policy?")

    assert calls == ["What is the VPN access policy?"]
    assert response.intent == INTENT_KNOWLEDGE_QA
    assert response.tool == INTENT_KNOWLEDGE_QA
    assert response.content == "FORMATTED ANSWER"
    assert response.sources == ["- Local corpus: AcmeCorp VPN Access Policy"]
    assert response.run_id == "run-xyz"


def test_email_summary_request_dispatches_to_email_tool(monkeypatch):
    calls = []

    def fake_tool(query):
        calls.append(query)
        return ToolResult(tool=INTENT_EMAIL_SUMMARY, content="INBOX SUMMARY")

    def no_knowledge(question):
        raise AssertionError("knowledge tool must not run for an email request")

    monkeypatch.setattr(email, "summarize_emails", fake_tool)
    monkeypatch.setattr(knowledge, "run_knowledge_qa", no_knowledge)

    response = engine.answer_office_request("summarize my unread emails")

    assert calls == ["summarize my unread emails"]
    assert response.intent == INTENT_EMAIL_SUMMARY
    assert response.tool == INTENT_EMAIL_SUMMARY
    assert response.content == "INBOX SUMMARY"


def test_unknown_request_returns_unsupported_message_without_calling_any_tool(monkeypatch):
    def boom_knowledge(question):
        raise AssertionError("the knowledge tool must not run for unknown intents")

    def boom_email(query):
        raise AssertionError("the email tool must not run for unknown intents")

    monkeypatch.setattr(knowledge, "run_knowledge_qa", boom_knowledge)
    monkeypatch.setattr(email, "summarize_emails", boom_email)

    response = engine.answer_office_request("What's on my calendar tomorrow?")

    assert response.intent == INTENT_UNKNOWN
    assert response.tool is None
    assert response.content == UNSUPPORTED_INTENT_NOTE
