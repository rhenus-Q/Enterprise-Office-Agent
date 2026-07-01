"""
Unit tests for the Office Agent rule-based router (office_agent/router.py).

Pure and deterministic — no external dependencies, no API keys.
"""

import pytest

from office_agent.router import route_request
from office_agent.schemas import (
    INTENT_CALENDAR_LOOKUP,
    INTENT_EMAIL_SUMMARY,
    INTENT_KNOWLEDGE_QA,
    INTENT_TICKET_ASSISTANT,
    INTENT_UNKNOWN,
)

# Obvious enterprise knowledge / policy / document questions (from the spec).
KNOWLEDGE_QUESTIONS = [
    "What is the VPN access policy?",
    "How do I request reimbursement?",
    "When should an incident be escalated to Sev-1?",
    "What is the data retention policy?",
    "What does the onboarding guide say?",
]

# Obvious inbox / email-summary requests (Phase 2, from the spec).
EMAIL_REQUESTS = [
    "summarize my emails",
    "summarize unread emails",
    "show important emails",
    "which emails need my response?",
    "what emails came in today?",
    "give me an inbox summary",
]

# Obvious calendar / scheduling requests (Phase 3, from the spec).
CALENDAR_REQUESTS = [
    "what meetings do I have today?",
    "show my calendar today",
    "what is my next meeting?",
    "do I have any meetings tomorrow?",
    "do I have schedule conflicts?",
    "show important meetings",
    "What's on my calendar tomorrow?",
]

# Obvious ticket / task requests (Phase 4, from the spec).
TICKET_REQUESTS = [
    "show open tickets",
    "summarize urgent tickets",
    "which tickets are assigned to me?",
    "show blocked tickets",
    "show my tasks",
    "create a task from TICK-001",
    "create a follow-up task for the VPN ticket",
]

# Unsupported office requests — the router must not claim these.
# (Email, calendar, and ticket/task requests are handled by their own cases; the
# daily briefing is still unimplemented, as are generic requests.)
UNKNOWN_REQUESTS = [
    "Give me my daily briefing.",
    "order lunch for the team",
    "book a flight to Berlin",
    "",
]


@pytest.mark.parametrize("question", KNOWLEDGE_QUESTIONS)
def test_knowledge_questions_route_to_knowledge_qa(question):
    routed = route_request(question)
    assert routed.intent == INTENT_KNOWLEDGE_QA
    assert routed.reason  # a non-empty explanation is recorded


@pytest.mark.parametrize("request_text", EMAIL_REQUESTS)
def test_email_requests_route_to_email_summary(request_text):
    routed = route_request(request_text)
    assert routed.intent == INTENT_EMAIL_SUMMARY
    assert routed.reason


@pytest.mark.parametrize("request_text", CALENDAR_REQUESTS)
def test_calendar_requests_route_to_calendar_lookup(request_text):
    routed = route_request(request_text)
    assert routed.intent == INTENT_CALENDAR_LOOKUP
    assert routed.reason


@pytest.mark.parametrize("request_text", TICKET_REQUESTS)
def test_ticket_requests_route_to_ticket_assistant(request_text):
    routed = route_request(request_text)
    assert routed.intent == INTENT_TICKET_ASSISTANT
    assert routed.reason


@pytest.mark.parametrize("request_text", UNKNOWN_REQUESTS)
def test_unsupported_requests_route_to_unknown(request_text):
    routed = route_request(request_text)
    assert routed.intent == INTENT_UNKNOWN


def test_router_is_case_insensitive():
    assert route_request("WHAT IS THE VPN POLICY?").intent == INTENT_KNOWLEDGE_QA
    assert route_request("SUMMARIZE MY INBOX").intent == INTENT_EMAIL_SUMMARY
    assert route_request("WHAT IS MY NEXT MEETING?").intent == INTENT_CALENDAR_LOOKUP
    assert route_request("SHOW OPEN TICKETS").intent == INTENT_TICKET_ASSISTANT
