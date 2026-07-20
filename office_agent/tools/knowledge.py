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

from enterprise_rag.graph.engine import AnswerResult, answer_question
from enterprise_rag.graph.formatting import STOP_REASON_NOTES, format_answer
from office_agent.schemas import (
    INTENT_KNOWLEDGE_QA,
    KnowledgeObservability,
    NodeTiming,
    ToolResult,
)

# Tool name recorded on the ToolResult / response for observability. Matches the
# intent so a reader can trace intent -> tool at a glance.
KNOWLEDGE_TOOL_NAME = INTENT_KNOWLEDGE_QA


def run_knowledge_qa(question: str) -> ToolResult:
    """Answer an enterprise knowledge question via the enterprise_rag engine.

    Returns a ToolResult whose `content` is the fully formatted answer
    (enterprise_rag caveats + Sources preserved); `stop_reason`, `sources`,
    `run_id`, and the engine's execution metadata (`observability`) are carried
    through unchanged for observability.
    """

    result = answer_question(question)

    return ToolResult(
        tool=KNOWLEDGE_TOOL_NAME,
        content=format_answer(result.raw_state),
        stop_reason=result.stop_reason,
        sources=list(result.sources),
        run_id=result.run_id,
        observability=_observability_from(result),
    )


def _observability_from(result: AnswerResult) -> KnowledgeObservability:
    """Copy the engine's `AnswerResult` metadata into the transport structure.

    Nothing is computed here: each field is the engine's own value, the timing
    dicts are only re-typed as `NodeTiming`, and `caveat` reuses the engine's
    existing `STOP_REASON_NOTES` mapping rather than restating any caveat text.
    """

    return KnowledgeObservability(
        run_id=result.run_id,
        node_path=list(result.node_path),
        node_timings_ms=[
            NodeTiming(node=timing["node"], duration_ms=timing["duration_ms"])
            for timing in result.node_timings_ms
        ],
        total_duration_ms=result.total_duration_ms,
        retries=result.retries,
        tracked_llm_calls=result.tracked_llm_calls,
        web_search_count=result.web_search_count,
        web_result_grading_count=result.web_result_grading_count,
        web_search_enabled=result.web_search_enabled,
        web_fallback_policy=result.web_fallback_policy,
        caveat=STOP_REASON_NOTES.get(result.stop_reason, ""),
    )
