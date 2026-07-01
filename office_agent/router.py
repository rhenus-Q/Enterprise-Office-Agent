"""
office_agent.router — deterministic Phase 1 intent router.

A rule-based keyword matcher: obvious enterprise knowledge / policy / document
questions route to `knowledge_qa`; everything else routes to `unknown`. No LLM
is involved yet (that is a later phase) — this keeps Phase 1 fast, free,
offline, and fully deterministic for tests.
"""

from office_agent.schemas import INTENT_KNOWLEDGE_QA, INTENT_UNKNOWN, RoutedIntent

# Substrings that mark an enterprise knowledge-base / policy / document question.
# Drawn from the AcmeCorp corpus domains (VPN, expenses, incident response,
# on-call, data retention, onboarding) plus a few generic policy/document terms.
# Matching is case-insensitive substring containment against the request text.
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


def route_request(text: str) -> RoutedIntent:
    """Classify a request into an Office Agent intent (Phase 1: rule-based).

    Returns `knowledge_qa` when the text contains any known enterprise
    knowledge/policy keyword, otherwise `unknown`. The matched keyword (or the
    lack of a match) is recorded in `reason` for observability and tests.
    """

    normalized = (text or "").casefold()

    for keyword in _KNOWLEDGE_KEYWORDS:
        if keyword in normalized:
            return RoutedIntent(INTENT_KNOWLEDGE_QA, reason=f"matched keyword '{keyword}'")

    return RoutedIntent(INTENT_UNKNOWN, reason="no known office intent matched")
