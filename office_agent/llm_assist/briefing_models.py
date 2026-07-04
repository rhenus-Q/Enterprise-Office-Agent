"""
office_agent.llm_assist.briefing_models — Pydantic models for the LLM Daily
Briefing narrative (Phase 2 of the optional Office LLM assist).

These models are the ONLY boundary through which the briefing-narrative LLM output
crosses into the Office Agent: the narrative chain returns a validated
`BriefingNarrative`, and `office_agent/tools/briefing.py` renders it
deterministically. Field descriptions guide structured output; the length cap keeps
a runaway generation from flooding the briefing — over-long output fails validation
and triggers the deterministic fallback rather than being shown.

Deliberately separate from `office_agent/llm_assist/models.py` (the email digest's
`EmailDigest`/`ActionItem`): the two assists share the flag/timeout/stop_reason
config but keep independent schemas so neither can regress the other.
"""

from typing import Literal

from pydantic import BaseModel, Field

# The source lists a reference id may belong to. Mirrors the mock-data families
# collected by `briefing.collect_briefing_facts` (emails, calendar meetings,
# tickets, tasks, approvals).
BriefingSourceType = Literal["email", "meeting", "ticket", "task", "approval"]

_MAX_NARRATIVE_CHARS = 1500


class BriefingReference(BaseModel):
    """A single citation tying the narrative to one real source item."""

    source_type: BriefingSourceType = Field(
        description="Which source list the id belongs to (email/meeting/ticket/task/approval).",
    )
    id: str = Field(
        description="An id copied verbatim from the provided facts; never invent one.",
        max_length=64,
    )


class BriefingNarrative(BaseModel):
    """The structured narrative produced from the deterministically collected facts."""

    narrative: str = Field(
        description="A concise cross-source narrative of the day.",
        max_length=_MAX_NARRATIVE_CHARS,
    )
    references: list[BriefingReference] = Field(
        default_factory=list,
        description="The real source items the narrative relies on; each must be a provided id.",
    )
