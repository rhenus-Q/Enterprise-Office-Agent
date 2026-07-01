"""
office_agent.formatting — presentation for the Office Agent.

Phase 1 keeps this deliberately small: the message shown for unsupported
intents, and a thin renderer for the final response. The knowledge tool already
returns fully-formatted content (enterprise_rag caveats + Sources preserved via
`enterprise_rag.graph.formatting.format_answer`), so this module does NOT
re-format answers — it only selects/renders the final text.
"""

from office_agent.schemas import OfficeAgentResponse

# Shown when the Office Agent cannot handle a request yet. The supported
# capabilities are named so the user gets a clear "not yet" rather than an
# opaque failure.
UNSUPPORTED_INTENT_NOTE = (
    "Sorry — the Office Agent can't handle that request yet. Right now it "
    "answers enterprise knowledge and policy questions from the internal "
    "knowledge base, summarizes your inbox, and looks up your calendar. Tickets, "
    "tasks, and the daily briefing are planned for later phases."
)


def format_office_response(response: OfficeAgentResponse) -> str:
    """Render the final Office Agent response as plain text for CLI/tests."""

    return response.content
