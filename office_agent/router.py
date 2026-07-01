"""
office_agent.router — deterministic intent router.

A rule-based keyword matcher, ordered by priority: inbox/email requests route to
`email_summary`, ticket/task requests route to `ticket_assistant`, meeting-prep
requests route to `meeting_agent`, calendar/meeting/schedule lookups route to
`calendar_lookup`, whole-day "briefing / what should I focus on" requests route
to `daily_briefing`, enterprise knowledge / policy / document questions route to
`knowledge_qa`, and everything else routes to `unknown`. No LLM is involved —
this keeps routing fast, free, offline, and fully deterministic for tests.
"""

from office_agent.schemas import (
    INTENT_CALENDAR_LOOKUP,
    INTENT_DAILY_BRIEFING,
    INTENT_EMAIL_SUMMARY,
    INTENT_KNOWLEDGE_QA,
    INTENT_MEETING_AGENT,
    INTENT_TICKET_ASSISTANT,
    INTENT_UNKNOWN,
    RoutedIntent,
)

# Substrings that mark an inbox / email request (the *channel* the user is
# asking about). Checked before the knowledge keywords so an explicit inbox
# request ("summarize my emails about VPN") is treated as an email request
# rather than a policy lookup.
_EMAIL_KEYWORDS = (
    "email",
    "emails",
    "inbox",
    "mailbox",
    "unread",
)

# Substrings that mark a calendar / scheduling *lookup* request. Checked before
# the knowledge keywords so "do I have any meetings about the VPN rollout?" is
# treated as a calendar request rather than a policy lookup. Meeting-*prep*
# semantics (see `_MEETING_KEYWORDS`) are matched earlier, so a plain lookup like
# "what meetings do I have today?" still lands here.
_CALENDAR_KEYWORDS = (
    "calendar",
    "meeting",
    "meetings",
    "schedule",
    "conflict",
    "conflicts",
)

# Substrings that mark a meeting-*prep* request — the user wants to be prepared
# for a meeting (agenda, talking points, context), not just look up the schedule.
# Checked before the broad calendar keywords, but kept specific enough that a
# plain "what meetings do I have today?" lookup still routes to calendar.
_MEETING_KEYWORDS = (
    "meeting prep",
    "prepare me for",
    "prep me for",
    "prepare for",
    "prep for",
    "bring up",
    "agenda",
    "summarize context",
    "context for my next meeting",
)

# Substrings that mark a ticket / task request. Checked before the knowledge
# keywords so "create a follow-up task for the VPN ticket" is treated as a
# ticket request rather than a policy lookup.
_TICKET_KEYWORDS = (
    "ticket",
    "tickets",
    "task",
    "tasks",
    "to-do",
    "todo",
    "backlog",
    "blocked",
)

# Substrings that mark a whole-day "brief me / what should I focus on" request.
# Checked after the specific channel keywords (email/calendar/ticket) so an
# explicit single-tool request still wins, but before the broad knowledge
# keywords so "what should I focus on today?" is a briefing, not a policy lookup.
_BRIEFING_KEYWORDS = (
    "briefing",
    "brief me",
    "focus",
    "my day",
    "on my plate",
)

# Substrings that mark an enterprise knowledge-base / policy / document question.
# Drawn from the AcmeCorp corpus domains (VPN, expenses, incident response,
# on-call, data retention, onboarding) plus a few generic policy/document terms.
_KNOWLEDGE_KEYWORDS = (
    "policy",
    "policies",
    "vpn",
    "reimburse",
    "reimbursement",
    "expense",
    "incident",
    "sev-1",
    "sev 1",
    "sev1",
    "escalate",
    "escalation",
    "retention",
    "onboard",
    "onboarding",
    "on-call",
    "on call",
    "playbook",
    "handbook",
    "knowledge base",
    "compliance",
    "audit log",
)

# Ordered routing rules: the first intent whose keyword set matches wins.
# Precedence: explicit channel requests (email, then ticket/task) win first;
# meeting-*prep* is matched before the broad calendar keywords so "prepare me for
# my next meeting" is prep (not a lookup); a plain calendar lookup follows; then
# the whole-day briefing; and finally the broad knowledge keywords.
_INTENT_RULES = (
    (INTENT_EMAIL_SUMMARY, _EMAIL_KEYWORDS),
    (INTENT_TICKET_ASSISTANT, _TICKET_KEYWORDS),
    (INTENT_MEETING_AGENT, _MEETING_KEYWORDS),
    (INTENT_CALENDAR_LOOKUP, _CALENDAR_KEYWORDS),
    (INTENT_DAILY_BRIEFING, _BRIEFING_KEYWORDS),
    (INTENT_KNOWLEDGE_QA, _KNOWLEDGE_KEYWORDS),
)


def route_request(text: str) -> RoutedIntent:
    """Classify a request into an Office Agent intent (rule-based).

    Matching is case-insensitive substring containment against the request
    text, evaluated in the priority order of `_INTENT_RULES`. No rule matches
    -> `unknown`. The matched keyword (or the lack of a match) is recorded in
    `reason` for observability and tests.
    """

    normalized = (text or "").casefold()

    for intent, keywords in _INTENT_RULES:
        for keyword in keywords:
            if keyword in normalized:
                return RoutedIntent(intent, reason=f"matched keyword '{keyword}'")

    return RoutedIntent(INTENT_UNKNOWN, reason="no known office intent matched")
