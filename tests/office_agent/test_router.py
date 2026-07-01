"""
Unit tests for the Office Agent Phase 1 rule-based router
(office_agent/router.py).

Pure and deterministic — no external dependencies, no API keys.
"""

import pytest

from office_agent.router import route_request
from office_agent.schemas import INTENT_KNOWLEDGE_QA, INTENT_UNKNOWN

# Obvious enterprise knowledge / policy / document questions (from the spec).
KNOWLEDGE_QUESTIONS = [
    "What is the VPN access policy?",
    "How do I request reimbursement?",
    "When should an incident be escalated to Sev-1?",
    "What is the data retention policy?",
    "What does the onboarding guide say?",
]

# Unsupported office requests — the Phase 1 router must not claim these.
UNKNOWN_REQUESTS = [
    "Summarize my unread email.",
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


@pytest.mark.parametrize("request_text", UNKNOWN_REQUESTS)
def test_unsupported_requests_route_to_unknown(request_text):
    routed = route_request(request_text)
    assert routed.intent == INTENT_UNKNOWN


def test_router_is_case_insensitive():
    assert route_request("WHAT IS THE VPN POLICY?").intent == INTENT_KNOWLEDGE_QA
