"""
office_agent.schemas — lightweight typed structures for the Office Agent.

A user request, the router's routed intent, a tool result, and the final
office-agent response. Intentionally minimal — plain dataclasses, no behavior.
As of Phase 7 (Office Agent v1.6) eight intents exist (`knowledge_qa`,
`email_summary`, `calendar_lookup`, `ticket_assistant`, `daily_briefing`,
`meeting_agent`, `workflow_approval`, `unknown`).
"""

from dataclasses import dataclass, field

# Routed intents. Keep this in lockstep with the router and the engine dispatch:
# adding a value here is meaningless until a route rule and a tool back it.
INTENT_KNOWLEDGE_QA = "knowledge_qa"
INTENT_EMAIL_SUMMARY = "email_summary"
INTENT_CALENDAR_LOOKUP = "calendar_lookup"
INTENT_TICKET_ASSISTANT = "ticket_assistant"
INTENT_DAILY_BRIEFING = "daily_briefing"
INTENT_MEETING_AGENT = "meeting_agent"
INTENT_WORKFLOW_APPROVAL = "workflow_approval"
INTENT_UNKNOWN = "unknown"

# Every intent the Office Agent can currently produce.
OFFICE_INTENTS = (
    INTENT_KNOWLEDGE_QA,
    INTENT_EMAIL_SUMMARY,
    INTENT_CALENDAR_LOOKUP,
    INTENT_TICKET_ASSISTANT,
    INTENT_DAILY_BRIEFING,
    INTENT_MEETING_AGENT,
    INTENT_WORKFLOW_APPROVAL,
    INTENT_UNKNOWN,
)


@dataclass
class OfficeRequest:
    """A raw user request to the Office Agent."""

    text: str


@dataclass
class RoutedIntent:
    """The router's decision for a request: the chosen intent + a short why."""

    intent: str
    reason: str = ""


@dataclass
class ToolResult:
    """The outcome of running one Office Agent tool.

    `content` is the user-facing text (already formatted; for the knowledge
    tool the enterprise_rag caveats and Sources section are preserved).
    `stop_reason`, `sources`, and `run_id` are carried through for
    observability and tests.
    """

    tool: str
    content: str
    stop_reason: str = ""
    sources: list[str] = field(default_factory=list)
    run_id: str | None = None


@dataclass
class OfficeAgentResponse:
    """The final Office Agent response for one request.

    `intent` is always set (including `unknown`) so callers and tests can see
    how the request was routed without parsing `content`.
    """

    intent: str
    content: str
    tool: str | None = None
    stop_reason: str = ""
    sources: list[str] = field(default_factory=list)
    run_id: str | None = None
