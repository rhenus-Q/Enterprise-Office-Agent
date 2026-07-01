"""
office_agent.engine — the Office Agent entry point.

`answer_office_request(user_input)` routes the request and dispatches to a tool.
As of Phase 3 three capabilities are supported — `knowledge_qa` (the
enterprise_rag adapter), `email_summary` (the local mock Email Summary tool), and
`calendar_lookup` (the local mock Calendar Lookup tool). Any other request routes
to `unknown` and returns a clear unsupported-intent message. The selected intent
is always included in the response for observability and testing.

This is the office-agent analogue of `enterprise_rag.graph.engine`: a single,
thin dispatch entry point. It deliberately adds no LLM routing yet — that
arrives in a later phase.
"""

from office_agent import formatting, router
from office_agent.schemas import (
    INTENT_CALENDAR_LOOKUP,
    INTENT_EMAIL_SUMMARY,
    INTENT_KNOWLEDGE_QA,
    INTENT_UNKNOWN,
    OfficeAgentResponse,
)
from office_agent.tools import calendar, email, knowledge


def answer_office_request(user_input: str) -> OfficeAgentResponse:
    """Route `user_input` and run the matching Office Agent tool.

    - `knowledge_qa` -> the enterprise_rag Knowledge Q&A adapter (caveats and
      Sources preserved in `content`).
    - `email_summary` -> the local mock Email Summary tool.
    - `calendar_lookup` -> the local mock Calendar Lookup tool.
    - `unknown` -> a safe unsupported-intent message; no tool is invoked.

    Each tool returns a `ToolResult`, so the response is built uniformly with
    the routed intent attached for observability.
    """

    routed = router.route_request(user_input)

    if routed.intent == INTENT_KNOWLEDGE_QA:
        result = knowledge.run_knowledge_qa(user_input)
    elif routed.intent == INTENT_EMAIL_SUMMARY:
        result = email.summarize_emails(user_input)
    elif routed.intent == INTENT_CALENDAR_LOOKUP:
        result = calendar.lookup_calendar(user_input)
    else:
        return OfficeAgentResponse(
            intent=INTENT_UNKNOWN,
            content=formatting.UNSUPPORTED_INTENT_NOTE,
            tool=None,
        )

    return OfficeAgentResponse(
        intent=routed.intent,
        content=result.content,
        tool=result.tool,
        stop_reason=result.stop_reason,
        sources=list(result.sources),
        run_id=result.run_id,
    )
