"""
office_agent.schemas — lightweight typed structures for the Office Agent.

A user request, the router's routed intent, a tool result, and the final
office-agent response. Intentionally minimal — plain dataclasses, no behavior.
As of Phase 7 (Office Agent v1.6.0) eight intents exist (`knowledge_qa`,
`email_summary`, `calendar_lookup`, `ticket_assistant`, `daily_briefing`,
`meeting_agent`, `workflow_approval`, `unknown`).
"""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import cycle guard, typing only
    # `run_settings` imports the intent constants from this module, so the
    # reverse reference exists only for type checkers.
    from office_agent.run_settings import ResolvedRunSettings

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
class NodeTiming:
    """One enterprise_rag graph step's wall-clock timing.

    The typed form of an `AnswerResult.node_timings_ms` entry (the engine emits
    plain dicts); the knowledge adapter does the conversion.
    """

    node: str
    duration_ms: float


@dataclass
class KnowledgeObservability:
    """Knowledge Q&A execution metadata carried through from `AnswerResult`.

    Every field mirrors one the enterprise_rag engine already produces — this
    is a transport structure, not a new observability signal. `caveat` is the
    existing `STOP_REASON_NOTES` text for the run's stop reason, reused rather
    than re-written.

    `tracked_llm_calls` is the budgeted operational counter, NOT total LLM
    usage, so any presentation of it must say "tracked".

    Only the knowledge adapter populates this; every other tool leaves it
    `None`.
    """

    run_id: str | None = None
    node_path: list[str] = field(default_factory=list)
    node_timings_ms: list[NodeTiming] = field(default_factory=list)
    total_duration_ms: float = 0.0
    retries: int = 0
    tracked_llm_calls: int = 0
    web_search_count: int = 0
    web_result_grading_count: int = 0
    web_search_enabled: bool = False
    web_fallback_policy: str = ""
    caveat: str = ""


@dataclass
class ToolResult:
    """The outcome of running one Office Agent tool.

    `content` is the user-facing text (already formatted; for the knowledge
    tool the enterprise_rag caveats and Sources section are preserved).
    `stop_reason`, `sources`, and `run_id` are carried through for
    observability and tests.

    `observability` is optional and additive: only the Knowledge Q&A adapter
    sets it, so the local mock tools keep their exact previous shape.
    """

    tool: str
    content: str
    stop_reason: str = ""
    sources: list[str] = field(default_factory=list)
    run_id: str | None = None
    observability: KnowledgeObservability | None = None


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
    observability: KnowledgeObservability | None = None
    # Set only when the caller supplied per-run options; `None` means the run
    # used the server defaults and nothing was requested to report.
    run_settings: "ResolvedRunSettings | None" = None
