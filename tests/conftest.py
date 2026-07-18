"""
conftest.py

pytest loads conftest.py before collecting tests.
We load env vars from .env (OPENAI_API_KEY, etc.) here, before any
`from enterprise_rag.graph.chains.question_router import ...` triggers ChatOpenAI construction.
"""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()


# Values enabling a runtime privacy mode. Mirrors the parsing in
# enterprise_rag/graph/config.py; inlined so collection imports no application code.
_TRUTHY_VALUES = {"true", "1", "yes", "on"}

# OFFLINE_MODE fails closed for real-model tests: no external call may be made,
# so the gated suites skip instead of attempting one.
_offline_mode = os.getenv("OFFLINE_MODE", "false").strip().lower() in _TRUTHY_VALUES

# Skip the whole integration suite (instead of erroring) when no API key is set,
# or when OFFLINE_MODE forbids external calls. A whitespace-only key counts as
# missing (mirrors evals/office_agent/llm_assist/_env.py), so the real-model
# suites skip cleanly instead of failing on auth.
requires_openai = pytest.mark.skipif(
    _offline_mode or not os.getenv("OPENAI_API_KEY", "").strip(),
    reason=(
        "OFFLINE_MODE is enabled — real-model tests must not call external services"
        if _offline_mode
        else "OPENAI_API_KEY is required to call the real gpt-5-mini for these tests"
    ),
)
