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
    INTENT_DAILY_BRIEFING,
    INTENT_EMAIL_SUMMARY,
    INTENT_KNOWLEDGE_QA,
    INTENT_MEETING_AGENT,
    INTENT_TICKET_ASSISTANT,
    INTENT_UNKNOWN,
    INTENT_WORKFLOW_APPROVAL,
    KnowledgeObservability,
    NodeTiming,
    ToolResult,
)
from office_agent.tools import (
    approvals,
    briefing,
    calendar,
    email,
    knowledge,
    meeting,
    tickets,
)


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
    monkeypatch.setattr(tickets, "handle_ticket_request", _guard("ticket"))
    monkeypatch.setattr(briefing, "generate_daily_briefing", _guard("briefing"))
    monkeypatch.setattr(meeting, "prepare_meeting", _guard("meeting"))
    monkeypatch.setattr(approvals, "handle_approval_request", _guard("approval"))

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
    monkeypatch.setattr(tickets, "handle_ticket_request", _guard("ticket"))
    monkeypatch.setattr(briefing, "generate_daily_briefing", _guard("briefing"))
    monkeypatch.setattr(meeting, "prepare_meeting", _guard("meeting"))
    monkeypatch.setattr(approvals, "handle_approval_request", _guard("approval"))

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
    monkeypatch.setattr(tickets, "handle_ticket_request", _guard("ticket"))
    monkeypatch.setattr(briefing, "generate_daily_briefing", _guard("briefing"))
    monkeypatch.setattr(meeting, "prepare_meeting", _guard("meeting"))
    monkeypatch.setattr(approvals, "handle_approval_request", _guard("approval"))

    response = engine.answer_office_request("what meetings do I have today?")

    assert calls == ["what meetings do I have today?"]
    assert response.intent == INTENT_CALENDAR_LOOKUP
    assert response.tool == INTENT_CALENDAR_LOOKUP
    assert response.content == "CALENDAR SUMMARY"


def test_ticket_assistant_request_dispatches_to_ticket_tool(monkeypatch):
    calls = []

    def fake_tool(query):
        calls.append(query)
        return ToolResult(tool=INTENT_TICKET_ASSISTANT, content="TICKET SUMMARY")

    monkeypatch.setattr(tickets, "handle_ticket_request", fake_tool)
    monkeypatch.setattr(knowledge, "run_knowledge_qa", _guard("knowledge"))
    monkeypatch.setattr(email, "summarize_emails", _guard("email"))
    monkeypatch.setattr(calendar, "lookup_calendar", _guard("calendar"))
    monkeypatch.setattr(briefing, "generate_daily_briefing", _guard("briefing"))
    monkeypatch.setattr(meeting, "prepare_meeting", _guard("meeting"))
    monkeypatch.setattr(approvals, "handle_approval_request", _guard("approval"))

    response = engine.answer_office_request("show open tickets")

    assert calls == ["show open tickets"]
    assert response.intent == INTENT_TICKET_ASSISTANT
    assert response.tool == INTENT_TICKET_ASSISTANT
    assert response.content == "TICKET SUMMARY"


def test_daily_briefing_request_dispatches_to_briefing_tool(monkeypatch):
    calls = []

    def fake_tool(query):
        calls.append(query)
        return ToolResult(tool=INTENT_DAILY_BRIEFING, content="DAILY BRIEFING")

    monkeypatch.setattr(briefing, "generate_daily_briefing", fake_tool)
    monkeypatch.setattr(knowledge, "run_knowledge_qa", _guard("knowledge"))
    monkeypatch.setattr(email, "summarize_emails", _guard("email"))
    monkeypatch.setattr(calendar, "lookup_calendar", _guard("calendar"))
    monkeypatch.setattr(tickets, "handle_ticket_request", _guard("ticket"))
    monkeypatch.setattr(meeting, "prepare_meeting", _guard("meeting"))
    monkeypatch.setattr(approvals, "handle_approval_request", _guard("approval"))

    response = engine.answer_office_request("give me my daily briefing")

    assert calls == ["give me my daily briefing"]
    assert response.intent == INTENT_DAILY_BRIEFING
    assert response.tool == INTENT_DAILY_BRIEFING
    assert response.content == "DAILY BRIEFING"


def test_meeting_agent_request_dispatches_to_meeting_tool(monkeypatch):
    calls = []

    def fake_tool(query):
        calls.append(query)
        return ToolResult(tool=INTENT_MEETING_AGENT, content="MEETING PREP")

    monkeypatch.setattr(meeting, "prepare_meeting", fake_tool)
    monkeypatch.setattr(knowledge, "run_knowledge_qa", _guard("knowledge"))
    monkeypatch.setattr(email, "summarize_emails", _guard("email"))
    monkeypatch.setattr(calendar, "lookup_calendar", _guard("calendar"))
    monkeypatch.setattr(tickets, "handle_ticket_request", _guard("ticket"))
    monkeypatch.setattr(briefing, "generate_daily_briefing", _guard("briefing"))
    monkeypatch.setattr(approvals, "handle_approval_request", _guard("approval"))

    response = engine.answer_office_request("prepare me for my next meeting")

    assert calls == ["prepare me for my next meeting"]
    assert response.intent == INTENT_MEETING_AGENT
    assert response.tool == INTENT_MEETING_AGENT
    assert response.content == "MEETING PREP"


def test_workflow_approval_request_dispatches_to_approval_tool(monkeypatch):
    calls = []

    def fake_tool(query):
        calls.append(query)
        return ToolResult(tool=INTENT_WORKFLOW_APPROVAL, content="APPROVAL SUMMARY")

    monkeypatch.setattr(approvals, "handle_approval_request", fake_tool)
    monkeypatch.setattr(knowledge, "run_knowledge_qa", _guard("knowledge"))
    monkeypatch.setattr(email, "summarize_emails", _guard("email"))
    monkeypatch.setattr(calendar, "lookup_calendar", _guard("calendar"))
    monkeypatch.setattr(tickets, "handle_ticket_request", _guard("ticket"))
    monkeypatch.setattr(briefing, "generate_daily_briefing", _guard("briefing"))
    monkeypatch.setattr(meeting, "prepare_meeting", _guard("meeting"))

    response = engine.answer_office_request("show pending approvals")

    assert calls == ["show pending approvals"]
    assert response.intent == INTENT_WORKFLOW_APPROVAL
    assert response.tool == INTENT_WORKFLOW_APPROVAL
    assert response.content == "APPROVAL SUMMARY"


def test_unknown_request_returns_unsupported_message_without_calling_any_tool(monkeypatch):
    monkeypatch.setattr(knowledge, "run_knowledge_qa", _guard("knowledge"))
    monkeypatch.setattr(email, "summarize_emails", _guard("email"))
    monkeypatch.setattr(calendar, "lookup_calendar", _guard("calendar"))
    monkeypatch.setattr(tickets, "handle_ticket_request", _guard("ticket"))
    monkeypatch.setattr(briefing, "generate_daily_briefing", _guard("briefing"))
    monkeypatch.setattr(meeting, "prepare_meeting", _guard("meeting"))
    monkeypatch.setattr(approvals, "handle_approval_request", _guard("approval"))

    response = engine.answer_office_request("order lunch for the team")

    assert response.intent == INTENT_UNKNOWN
    assert response.tool is None
    assert response.content == UNSUPPORTED_INTENT_NOTE


# --- observability carry-through (Phase 4, additive) ------------------------


def _observability():
    return KnowledgeObservability(
        run_id="run-xyz",
        node_path=["retrieve", "generate"],
        node_timings_ms=[NodeTiming(node="retrieve", duration_ms=9.5)],
        total_duration_ms=900.0,
        retries=0,
        tracked_llm_calls=3,
        web_fallback_policy="conservative",
    )


def test_knowledge_response_carries_the_tool_observability(monkeypatch):
    """The engine transports the adapter's structure; it builds nothing itself."""

    observability = _observability()
    monkeypatch.setattr(
        knowledge,
        "run_knowledge_qa",
        lambda _question: ToolResult(
            tool=INTENT_KNOWLEDGE_QA,
            content="FORMATTED ANSWER",
            observability=observability,
        ),
    )

    response = engine.answer_office_request("What is the VPN access policy?")

    assert response.observability is observability


def test_non_knowledge_capabilities_have_no_observability(monkeypatch):
    """Deterministic tools never set it, so the response keeps the None default."""

    monkeypatch.setattr(
        email,
        "summarize_emails",
        lambda _text: ToolResult(tool=INTENT_EMAIL_SUMMARY, content="INBOX SUMMARY"),
    )
    monkeypatch.setattr(
        calendar,
        "lookup_calendar",
        lambda _text: ToolResult(tool=INTENT_CALENDAR_LOOKUP, content="CALENDAR"),
    )

    assert engine.answer_office_request("summarize my unread emails").observability is None
    assert engine.answer_office_request("what meetings do I have today?").observability is None


def test_unknown_response_has_no_observability(monkeypatch):
    monkeypatch.setattr(knowledge, "run_knowledge_qa", _guard("knowledge"))

    assert engine.answer_office_request("order lunch for the team").observability is None


def test_tool_result_without_observability_still_constructs():
    """The new field is optional: pre-Phase-4 constructions keep working."""

    result = ToolResult(tool=INTENT_EMAIL_SUMMARY, content="INBOX SUMMARY")

    assert result.observability is None
