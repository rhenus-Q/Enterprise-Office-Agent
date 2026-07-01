"""
office_agent.tools.knowledge — Knowledge Q&A adapter over the enterprise_rag engine.

A thin adapter, NOT a reimplementation. It forwards the question to the
completed enterprise_rag engine (`answer_question`) and renders the outcome with
the engine's own formatter (`format_answer`), so the anti-hallucination /
retry / privacy caveats and the deterministic Sources section are preserved
exactly. No retrieval, generation, grading, routing, or formatting rules are
duplicated here.

Import is side-effect-free in the repo's sense: `enterprise_rag` builds its
external clients lazily, so importing this module needs no API keys and no
network (see CLAUDE.md).
"""

from enterprise_rag.graph.engine import answer_question
from enterprise_rag.graph.formatting import format_answer
from office_agent.schemas import INTENT_KNOWLEDGE_QA, ToolResult

# Tool name recorded on the ToolResult / response for observability. Matches the
# intent so a reader can trace intent -> tool at a glance.
KNOWLEDGE_TOOL_NAME = INTENT_KNOWLEDGE_QA


def run_knowledge_qa(question: str) -> ToolResult:
    """Answer an enterprise knowledge question via the enterprise_rag engine.

    Returns a ToolResult whose `content` is the fully formatted answer
    (enterprise_rag caveats + Sources preserved); `stop_reason`, `sources`, and
    `run_id` are carried through unchanged for observability.
    """

    result = answer_question(question)

    return ToolResult(
        tool=KNOWLEDGE_TOOL_NAME,
        content=format_answer(result.raw_state),
        stop_reason=result.stop_reason,
        sources=list(result.sources),
        run_id=result.run_id,
    )
