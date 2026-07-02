"""
Unit tests for the Office Agent rule-based router (office_agent/router.py).

Pure and deterministic — no external dependencies, no API keys.
"""

import pytest

from office_agent.router import _INTENT_RULES, route_request
from office_agent.schemas import (
    INTENT_CALENDAR_LOOKUP,
    INTENT_DAILY_BRIEFING,
    INTENT_EMAIL_SUMMARY,
    INTENT_KNOWLEDGE_QA,
    INTENT_MEETING_AGENT,
    INTENT_TICKET_ASSISTANT,
    INTENT_UNKNOWN,
    INTENT_WORKFLOW_APPROVAL,
    OFFICE_INTENTS,
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

# Obvious workflow / approval requests (Phase 7, from the spec). These must route
# to the Workflow / Approval Agent, ahead of the ticket/task and knowledge rules.
WORKFLOW_REQUESTS = [
    "show pending approvals",
    "which approvals are assigned to me?",
    "show urgent approvals",
    "what is the status of APR-001?",
    "approve APR-001",
    "reject APR-002",
    "create a follow-up task for APR-001",
    "show audit log for APR-001",
    "show expense approvals",
    "show VPN approvals",
]

# Obvious meeting-prep requests (Phase 6, from the spec). These must route to the
# Meeting Agent, NOT to the broad calendar lookup.
MEETING_REQUESTS = [
    "prepare me for my next meeting",
    "generate meeting prep",
    "what should I bring up in the VPN rollout meeting?",
    "summarize context for my next meeting",
    "prep me for the security review board",
    "meeting prep for the budget workshop",
    "what should I bring up in my meeting?",
]

# Obvious daily-briefing requests (Phase 5, from the spec).
BRIEFING_REQUESTS = [
    "give me my daily briefing",
    "daily briefing",
    "what should I focus on today?",
    "summarize my day",
    "morning briefing",
    "what is on my plate today?",
    "brief me for today",
]

# Unsupported office requests — the router must not claim these. Email, calendar,
# ticket/task, and briefing requests are handled by their own cases; what remains
# is genuinely out of scope.
UNKNOWN_REQUESTS = [
    "order lunch for the team",
    "book a flight to Berlin",
    "translate this paragraph to German",
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


@pytest.mark.parametrize("request_text", WORKFLOW_REQUESTS)
def test_workflow_requests_route_to_workflow_approval(request_text):
    routed = route_request(request_text)
    assert routed.intent == INTENT_WORKFLOW_APPROVAL
    assert routed.reason


@pytest.mark.parametrize("request_text", MEETING_REQUESTS)
def test_meeting_prep_requests_route_to_meeting_agent(request_text):
    routed = route_request(request_text)
    assert routed.intent == INTENT_MEETING_AGENT
    assert routed.reason


@pytest.mark.parametrize("request_text", BRIEFING_REQUESTS)
def test_briefing_requests_route_to_daily_briefing(request_text):
    routed = route_request(request_text)
    assert routed.intent == INTENT_DAILY_BRIEFING
    assert routed.reason


@pytest.mark.parametrize("request_text", UNKNOWN_REQUESTS)
def test_unsupported_requests_route_to_unknown(request_text):
    routed = route_request(request_text)
    assert routed.intent == INTENT_UNKNOWN


def test_meeting_prep_and_calendar_lookup_are_distinguished():
    # Meeting-*prep* semantics route to the Meeting Agent...
    assert route_request("prepare me for my next meeting").intent == INTENT_MEETING_AGENT
    assert route_request("what should I bring up in my meeting?").intent == INTENT_MEETING_AGENT
    # ...but plain calendar *lookups* still route to Calendar Lookup.
    assert route_request("what meetings do I have today?").intent == INTENT_CALENDAR_LOOKUP
    assert route_request("show my calendar today").intent == INTENT_CALENDAR_LOOKUP
    assert route_request("what is my next meeting?").intent == INTENT_CALENDAR_LOOKUP


def test_workflow_approval_and_ticket_assistant_are_distinguished():
    # Plain task/ticket requests (no approval id, no approval keyword) stay on the
    # Task / Ticket Assistant...
    assert route_request("show my tasks").intent == INTENT_TICKET_ASSISTANT
    assert route_request("create a task from TICK-001").intent == INTENT_TICKET_ASSISTANT
    # ...but an approval id or an explicit approval word routes to Workflow / Approval.
    assert route_request("create a follow-up task for APR-001").intent == INTENT_WORKFLOW_APPROVAL
    assert route_request("approve APR-001").intent == INTENT_WORKFLOW_APPROVAL
    assert route_request("show expense approvals").intent == INTENT_WORKFLOW_APPROVAL
    # A plain policy question is still Knowledge Q&A (not an approval request).
    assert route_request("what is the expense policy?").intent == INTENT_KNOWLEDGE_QA


def test_router_is_case_insensitive():
    assert route_request("WHAT IS THE VPN POLICY?").intent == INTENT_KNOWLEDGE_QA
    assert route_request("SUMMARIZE MY INBOX").intent == INTENT_EMAIL_SUMMARY
    assert route_request("WHAT IS MY NEXT MEETING?").intent == INTENT_CALENDAR_LOOKUP
    assert route_request("SHOW OPEN TICKETS").intent == INTENT_TICKET_ASSISTANT
    assert route_request("GIVE ME MY DAILY BRIEFING").intent == INTENT_DAILY_BRIEFING
    assert route_request("PREPARE ME FOR MY NEXT MEETING").intent == INTENT_MEETING_AGENT
    assert route_request("SHOW PENDING APPROVALS").intent == INTENT_WORKFLOW_APPROVAL
    assert route_request("APPROVE APR-001").intent == INTENT_WORKFLOW_APPROVAL


# ---------------------------------------------------------------------------
# Golden routing table (regression fence)
# ---------------------------------------------------------------------------
# Each row pins a representative request phrase to the intent the router MUST
# return today. The overlap rows deliberately mention words that belong to more
# than one intent, so they exercise the precedence order encoded in
# office_agent.router._INTENT_RULES:
#
#   email_summary -> workflow_approval -> ticket_assistant -> meeting_agent ->
#   calendar_lookup -> daily_briefing -> knowledge_qa -> unknown
#
# with an explicit APR-<n> id matched at the workflow_approval position (2),
# i.e. ahead of ticket/task (3) but behind an explicit email request (1).
#
# This table documents CURRENT behavior, not a wish list. A change to routing
# precedence or keywords should surface here as a clear, reviewable diff. Do NOT
# edit an expected intent merely to make a changed router pass — first confirm
# the new behavior is intended and update the router docs alongside it.
GOLDEN_ROUTES = [
    # --- One representative phrase per intent --------------------------------
    ("summarize my unread emails", INTENT_EMAIL_SUMMARY),
    ("show pending approvals", INTENT_WORKFLOW_APPROVAL),
    ("show open tickets", INTENT_TICKET_ASSISTANT),
    ("prepare me for my next meeting", INTENT_MEETING_AGENT),
    ("what meetings do I have today?", INTENT_CALENDAR_LOOKUP),
    ("give me my daily briefing", INTENT_DAILY_BRIEFING),
    ("what is the VPN access policy?", INTENT_KNOWLEDGE_QA),
    ("order lunch for the team", INTENT_UNKNOWN),
    # --- Overlap: email + meeting -> email wins (precedence 1 > 5) -----------
    ("summarize emails about the VPN rollout meeting", INTENT_EMAIL_SUMMARY),
    # --- Overlap: briefing + email -> email wins (precedence 1 > 6) ----------
    ("include unread emails in my morning briefing", INTENT_EMAIL_SUMMARY),
    # --- Overlap: approval + task -> approval wins (precedence 2 > 3) --------
    ("create a follow-up task for the pending approval", INTENT_WORKFLOW_APPROVAL),
    # --- Overlap: approval + meeting prep -> approval wins (precedence 2 > 4) -
    ("prepare me for the vendor approval meeting", INTENT_WORKFLOW_APPROVAL),
    # --- Overlap: ticket + follow-up task (no approval) -> ticket wins -------
    #     precedence 3; the "vpn" knowledge keyword at 7 does not steal it.
    ("create a follow-up task for the VPN ticket", INTENT_TICKET_ASSISTANT),
    # --- Overlap: meeting prep + calendar -> meeting prep wins (4 > 5) -------
    ("meeting prep for tomorrow's calendar", INTENT_MEETING_AGENT),
    # --- Overlap: briefing + knowledge -> briefing wins (6 > 7) --------------
    ("what should I focus on in the VPN rollout?", INTENT_DAILY_BRIEFING),
    # --- Overlap: calendar + knowledge -> calendar wins (5 > 7) --------------
    ("do I have schedule conflicts before the compliance review?", INTENT_CALENDAR_LOOKUP),
    # --- Explicit APR-<n> ids -> workflow_approval ---------------------------
    ("APR-001", INTENT_WORKFLOW_APPROVAL),
    ("what is the status of APR-042?", INTENT_WORKFLOW_APPROVAL),
    # APR id is matched at the workflow position (2), ahead of ticket/task (3):
    ("create a follow-up task for APR-001", INTENT_WORKFLOW_APPROVAL),
    ("show audit log for APR-001", INTENT_WORKFLOW_APPROVAL),
    # ...but an explicit email request (precedence 1) still beats an APR id:
    ("email me the status of APR-001", INTENT_EMAIL_SUMMARY),
    # A plain audit-log / retention question (no APR id, no approval word) is
    # Knowledge Q&A, not workflow:
    ("what is our audit log retention policy?", INTENT_KNOWLEDGE_QA),
    # --- Unsupported requests -> unknown -------------------------------------
    ("book a flight to Berlin", INTENT_UNKNOWN),
    ("", INTENT_UNKNOWN),
]


@pytest.mark.parametrize("phrase, expected_intent", GOLDEN_ROUTES)
def test_golden_routes(phrase, expected_intent):
    """Every golden phrase routes to exactly the pinned intent."""

    assert route_request(phrase).intent == expected_intent


def test_router_surface_matches_declared_intents():
    """The intents the router can emit == the declared OFFICE_INTENTS.

    Guards against version drift between office_agent.schemas (the declared
    intent surface, kept in lockstep with the engine dispatch) and
    office_agent.router (the rules that actually produce those intents): adding
    an intent constant without a routing rule, or a routing rule for an
    undeclared intent, breaks this test.
    """

    router_intents = {intent for intent, _ in _INTENT_RULES} | {INTENT_UNKNOWN}
    assert router_intents == set(OFFICE_INTENTS)


def test_golden_table_covers_every_declared_intent():
    """The golden table exercises exactly the declared intents (incl. unknown).

    Keeps the regression fence complete: a newly declared intent must gain both
    a routing rule (previous test) and a golden phrase here.
    """

    covered = {expected for _, expected in GOLDEN_ROUTES}
    assert covered == set(OFFICE_INTENTS)
