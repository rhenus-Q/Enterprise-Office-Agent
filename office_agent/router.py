"""
office_agent.router — deterministic intent router.

A rule-based keyword matcher, ordered by priority: inbox/email requests route to
`email_summary`, enterprise knowledge / policy / document questions route to
`knowledge_qa`, and everything else routes to `unknown`. No LLM is involved (that
is a later phase) — this keeps routing fast, free, offline, and fully
deterministic for tests.
"""

from office_agent.schemas import (
    INTENT_EMAIL_SUMMARY,
    INTENT_KNOWLEDGE_QA,
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
_INTENT_RULES = (
    (INTENT_EMAIL_SUMMARY, _EMAIL_KEYWORDS),
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
