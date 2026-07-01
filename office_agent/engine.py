"""
office_agent.engine — the Office Agent entry point (Phase 1).

`answer_office_request(user_input)` routes the request and dispatches to a tool.
Phase 1 supports exactly one capability — `knowledge_qa`, via the enterprise_rag
adapter. Any other request routes to `unknown` and returns a clear
unsupported-intent message. The selected intent is always included in the
response for observability and testing.

This is the office-agent analogue of `enterprise_rag.graph.engine`: a single,
thin dispatch entry point. It deliberately adds no LLM routing and no new
capabilities yet — those arrive in later phases.
"""

from office_agent import formatting, router
from office_agent.schemas import INTENT_KNOWLEDGE_QA, INTENT_UNKNOWN, OfficeAgentResponse
from office_agent.tools import knowledge


def answer_office_request(user_input: str) -> OfficeAgentResponse:
    """Route `user_input` and run the matching Office Agent tool.

    - `knowledge_qa` -> the enterprise_rag Knowledge Q&A adapter (caveats and
      Sources preserved in `content`).
    - `unknown` -> a safe unsupported-intent message; no tool is invoked.
    """

    routed = router.route_request(user_input)

    if routed.intent == INTENT_KNOWLEDGE_QA:
        result = knowledge.run_knowledge_qa(user_input)
        return OfficeAgentResponse(
            intent=INTENT_KNOWLEDGE_QA,
            content=result.content,
            tool=result.tool,
            stop_reason=result.stop_reason,
            sources=list(result.sources),
            run_id=result.run_id,
        )

    return OfficeAgentResponse(
        intent=INTENT_UNKNOWN,
        content=formatting.UNSUPPORTED_INTENT_NOTE,
        tool=None,
    )
