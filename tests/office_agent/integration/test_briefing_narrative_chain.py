"""
Gated real-model test for the Office Agent LLM Daily Briefing narrative chain.

Lives under tests/office_agent/integration/, kept OUT of the mocked
tests/office_agent/ unit suite (which is strictly keys-free) and marked
`requires_openai`, so it is skipped unless `OPENAI_API_KEY` is set. It calls the
real gpt-5-mini narrative chain over the collected briefing facts and asserts the
parsed result is a well-formed, grounded `BriefingNarrative`. Run only with
explicit approval:

    uv run pytest tests/office_agent/integration/ -v
"""

from office_agent.llm_assist import briefing_narrative
from office_agent.llm_assist.briefing_models import BriefingNarrative
from office_agent.tools import briefing
from tests.conftest import requires_openai


@requires_openai
def test_real_briefing_narrative_parses_and_is_grounded():
    facts = briefing.collect_briefing_facts()

    narrative = briefing_narrative.narrate_briefing(facts)

    assert isinstance(narrative, BriefingNarrative)
    assert narrative.narrative.strip()
    # Grounding must hold against the collected facts (raises on any violation).
    briefing_narrative.validate_narrative(narrative, facts)
