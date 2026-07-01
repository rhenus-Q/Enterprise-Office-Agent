"""
Unit tests for the Office Agent rule-based router (office_agent/router.py).

Pure and deterministic — no external dependencies, no API keys.
"""

import pytest

from office_agent.router import route_request
from office_agent.schemas import INTENT_EMAIL_SUMMARY, INTENT_KNOWLEDGE_QA, INTENT_UNKNOWN

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

# Unsupported office requests — the router must not claim these.
# (Email requests are handled by their own case as of Phase 2; the ones left
# here are still unimplemented: calendar, tickets, tasks, daily briefing.)
UNKNOWN_REQUESTS = [
    "What's on my calendar tomorrow?",
    "Create a Jira ticket for the login bug.",
    "Add 'call the vendor' to my task list.",
    "Give me my daily briefing.",
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


@pytest.mark.parametrize("request_text", UNKNOWN_REQUESTS)
def test_unsupported_requests_route_to_unknown(request_text):
    routed = route_request(request_text)
    assert routed.intent == INTENT_UNKNOWN


def test_router_is_case_insensitive():
    assert route_request("WHAT IS THE VPN POLICY?").intent == INTENT_KNOWLEDGE_QA
    assert route_request("SUMMARIZE MY INBOX").intent == INTENT_EMAIL_SUMMARY
