"""
office_agent.engine — the Office Agent entry point.

`answer_office_request(user_input, options=None)` routes the request and dispatches to a tool.
As of Phase 7 (Office Agent v1.6.0) seven capabilities are supported —
`knowledge_qa` (the enterprise_rag adapter), `email_summary` (the local mock
Email Summary tool), `calendar_lookup` (the local mock Calendar Lookup tool),
`ticket_assistant` (the local mock Task / Ticket Assistant), `daily_briefing`
(the local mock Daily Briefing aggregator), `meeting_agent` (the local mock
Meeting Agent / Meeting Prep), and `workflow_approval` (the local mock Workflow /
Approval Agent). Any other request routes to `unknown` and returns a clear
unsupported-intent message. The selected intent is always included in the
response for observability and testing.

This is the office-agent analogue of `enterprise_rag.graph.engine`: a single,
thin dispatch entry point. It deliberately uses no LLM routing.
"""

from office_agent import formatting, router
from office_agent.llm_assist import config as llm_config
from office_agent.run_settings import (
    OfficeRunOptions,
    ResolvedRunSettings,
    resolve_run_settings,
)
from office_agent.schemas import (
    INTENT_CALENDAR_LOOKUP,
    INTENT_DAILY_BRIEFING,
    INTENT_EMAIL_SUMMARY,
    INTENT_KNOWLEDGE_QA,
    INTENT_MEETING_AGENT,
    INTENT_TICKET_ASSISTANT,
    INTENT_UNKNOWN,
    INTENT_WORKFLOW_APPROVAL,
    OfficeAgentResponse,
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


def answer_office_request(
    user_input: str, options: OfficeRunOptions | None = None
) -> OfficeAgentResponse:
    """Route `user_input` and run the matching Office Agent tool.

    - `knowledge_qa` -> the enterprise_rag Knowledge Q&A adapter (caveats and
      Sources preserved in `content`).
    - `email_summary` -> the local mock Email Summary tool.
    - `calendar_lookup` -> the local mock Calendar Lookup tool.
    - `ticket_assistant` -> the local mock Task / Ticket Assistant.
    - `daily_briefing` -> the local mock Daily Briefing aggregator.
    - `meeting_agent` -> the local mock Meeting Agent / Meeting Prep tool.
    - `workflow_approval` -> the local mock Workflow / Approval Agent.
    - `unknown` -> a safe unsupported-intent message; no tool is invoked.

    Each tool returns a `ToolResult`, so the response is built uniformly with
    the routed intent attached for observability.

    `options` is optional and request-scoped. When omitted (the default),
    behavior is exactly as before: every tool falls back to the server defaults
    and `run_settings` is `None` — there is nothing honest to report as
    "requested". When supplied, the options are resolved against server policy
    *after* routing (routing itself is never influenced by them) and threaded
    explicitly into the affected tool call. Nothing is written to the
    environment or to any module global, so concurrent requests with opposite
    settings stay fully isolated.
    """

    routed = router.route_request(user_input)
    settings = _resolve(routed.intent, options)

    if routed.intent == INTENT_KNOWLEDGE_QA:
        result = knowledge.run_knowledge_qa(
            user_input,
            web_search_enabled=settings.effective.web_search if settings else None,
        )
    elif routed.intent == INTENT_EMAIL_SUMMARY:
        result = email.summarize_emails(
            user_input,
            llm_assist_enabled=settings.effective.llm_assist if settings else None,
        )
    elif routed.intent == INTENT_CALENDAR_LOOKUP:
        result = calendar.lookup_calendar(user_input)
    elif routed.intent == INTENT_TICKET_ASSISTANT:
        result = tickets.handle_ticket_request(user_input)
    elif routed.intent == INTENT_DAILY_BRIEFING:
        result = briefing.generate_daily_briefing(
            user_input,
            llm_assist_enabled=settings.effective.llm_assist if settings else None,
        )
    elif routed.intent == INTENT_MEETING_AGENT:
        result = meeting.prepare_meeting(user_input)
    elif routed.intent == INTENT_WORKFLOW_APPROVAL:
        result = approvals.handle_approval_request(user_input)
    else:
        return OfficeAgentResponse(
            intent=INTENT_UNKNOWN,
            content=formatting.UNSUPPORTED_INTENT_NOTE,
            tool=None,
            run_settings=settings,
        )

    return OfficeAgentResponse(
        intent=routed.intent,
        content=result.content,
        tool=result.tool,
        stop_reason=result.stop_reason,
        sources=list(result.sources),
        run_id=result.run_id,
        # Only the Knowledge Q&A adapter sets this; for every other tool it
        # stays the `None` default rather than being fabricated.
        observability=result.observability,
        run_settings=settings,
    )


def _resolve(intent: str, options: OfficeRunOptions | None) -> ResolvedRunSettings | None:
    """Resolve per-run options against the server's current policy.

    The server policy is read here, once per request, and passed into the pure
    resolver — so the precedence rules stay independent of environment access.
    `None` in, `None` out: a caller that requested nothing gets no fabricated
    "requested" settings.

    Web-search policy comes from the knowledge adapter (the Office Agent's one
    sanctioned `enterprise_rag` boundary); the privacy / offline / assist flags
    come from the office-owned readers. Both are already mode-aware.
    """

    if options is None:
        return None

    return resolve_run_settings(
        intent,
        options,
        server_privacy_mode=llm_config.privacy_mode(),
        server_offline_mode=llm_config.offline_mode(),
        server_llm_assist_available=llm_config.office_llm_enabled(),
        server_web_search_available=knowledge.web_search_available(),
    )
