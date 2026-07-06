"""
Gated real-model test for the Office Agent LLM email-digest chain.

Lives under tests/office_agent/integration/, kept OUT of the mocked
tests/office_agent/ unit suite (which is strictly keys-free) and marked
`requires_openai`, so it is skipped unless `OPENAI_API_KEY` is set. It calls the
real gpt-5-mini digest chain over the mock inbox and asserts the parsed result is
a well-formed, grounded `EmailDigest`. Run only with explicit approval:

    uv run pytest tests/office_agent/integration/ -v
"""

from office_agent.llm_assist import email_digest
from office_agent.llm_assist.models import EmailDigest
from office_agent.tools import email
from tests.conftest import requires_openai


@requires_openai
def test_real_email_digest_parses_and_is_grounded():
    _label, matched = email.filter_for_query("summarize my emails")

    digest = email_digest.digest_emails(matched)

    assert isinstance(digest, EmailDigest)
    assert digest.summary.strip()
    # Grounding must hold against the filtered inbox (raises on any violation).
    email_digest.validate_digest(digest, matched)
