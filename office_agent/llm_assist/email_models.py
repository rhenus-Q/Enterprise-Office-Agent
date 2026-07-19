"""
office_agent.llm_assist.email_models — Pydantic models for the LLM email digest.

These models are the ONLY boundary through which LLM output crosses into the
Office Agent: the digest chain returns a validated `EmailDigest`, and
`office_agent/tools/email.py` renders it deterministically. Field descriptions
guide structured output; length caps keep a runaway generation from flooding the
summary — over-long output fails validation and triggers the deterministic
fallback rather than being shown.
"""

from pydantic import BaseModel, Field, field_validator

_MAX_SUMMARY_CHARS = 1200
_MAX_ASK_CHARS = 300
_MAX_DEADLINE_CHARS = 120


class ActionItem(BaseModel):
    """A single extracted action item tied to exactly one source email."""

    email_id: str = Field(
        description=(
            "The id of the source email this action item comes from; "
            "must be one of the provided email ids."
        ),
        max_length=64,
    )
    ask: str = Field(
        description="The concrete request or task stated in that email, as a short phrase.",
        max_length=_MAX_ASK_CHARS,
    )
    deadline: str | None = Field(
        default=None,
        description=(
            "The deadline stated in the email body, if any; leave null when the "
            "body states no deadline. Do not invent dates."
        ),
        max_length=_MAX_DEADLINE_CHARS,
    )

    @field_validator("deadline")
    @classmethod
    def _empty_deadline_to_none(cls, value: str | None) -> str | None:
        """Normalize an empty / whitespace-only deadline to None (deterministic).

        Some models emit "" instead of null for an unset optional field; treating
        it as None here keeps the "no invented deadline" contract simple and
        avoids a blank "(deadline: )" in the rendered output.
        """

        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class EmailDigest(BaseModel):
    """The structured digest produced from the deterministically filtered emails."""

    summary: str = Field(
        description="A concise summary of the filtered emails.",
        max_length=_MAX_SUMMARY_CHARS,
    )
    action_items: list[ActionItem] = Field(
        default_factory=list,
        description="Action items extracted from the emails; empty when none require action.",
    )
    priority_order: list[str] = Field(
        default_factory=list,
        description=(
            "The provided email ids ordered from most to least important; each id "
            "must be one of the provided ids and appear at most once."
        ),
    )
