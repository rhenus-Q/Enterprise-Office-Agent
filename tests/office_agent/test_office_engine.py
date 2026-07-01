"""
Unit tests for the Office Agent entry point (office_agent/engine.py).

The knowledge tool is mocked at the engine's seam
(`office_agent.tools.knowledge.run_knowledge_qa`), so these tests never touch
enterprise_rag, OpenAI, Tavily, or Chroma. They verify dispatch, not RAG.
"""

from office_agent import engine
from office_agent.formatting import UNSUPPORTED_INTENT_NOTE
from office_agent.schemas import (
    INTENT_CALENDAR_LOOKUP,
    INTENT_EMAIL_SUMMARY,
    INTENT_KNOWLEDGE_QA,
    INTENT_UNKNOWN,
    ToolResult,
)
from office_agent.tools import calendar, email, knowledge


def _guard(tool_label):
    """Return a stand-in tool that fails if the engine ever calls it."""

    def _fail(_arg):
        raise AssertionError(f"{tool_label} tool must not run for this request")

    return _fail


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
    monkeypatch.setattr(email, "summarize_emails", _guard("email"))
    monkeypatch.setattr(calendar, "lookup_calendar", _guard("calendar"))

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

    monkeypatch.setattr(email, "summarize_emails", fake_tool)
    monkeypatch.setattr(knowledge, "run_knowledge_qa", _guard("knowledge"))
    monkeypatch.setattr(calendar, "lookup_calendar", _guard("calendar"))

    response = engine.answer_office_request("summarize my unread emails")

    assert calls == ["summarize my unread emails"]
    assert response.intent == INTENT_EMAIL_SUMMARY
    assert response.tool == INTENT_EMAIL_SUMMARY
    assert response.content == "INBOX SUMMARY"


def test_calendar_lookup_request_dispatches_to_calendar_tool(monkeypatch):
    calls = []

    def fake_tool(query):
        calls.append(query)
        return ToolResult(tool=INTENT_CALENDAR_LOOKUP, content="CALENDAR SUMMARY")

    monkeypatch.setattr(calendar, "lookup_calendar", fake_tool)
    monkeypatch.setattr(knowledge, "run_knowledge_qa", _guard("knowledge"))
    monkeypatch.setattr(email, "summarize_emails", _guard("email"))

    response = engine.answer_office_request("what meetings do I have today?")

    assert calls == ["what meetings do I have today?"]
    assert response.intent == INTENT_CALENDAR_LOOKUP
    assert response.tool == INTENT_CALENDAR_LOOKUP
    assert response.content == "CALENDAR SUMMARY"


def test_unknown_request_returns_unsupported_message_without_calling_any_tool(monkeypatch):
    monkeypatch.setattr(knowledge, "run_knowledge_qa", _guard("knowledge"))
    monkeypatch.setattr(email, "summarize_emails", _guard("email"))
    monkeypatch.setattr(calendar, "lookup_calendar", _guard("calendar"))

    response = engine.answer_office_request("Create a Jira ticket for the login bug.")

    assert response.intent == INTENT_UNKNOWN
    assert response.tool is None
    assert response.content == UNSUPPORTED_INTENT_NOTE
