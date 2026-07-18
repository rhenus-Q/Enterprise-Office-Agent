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


# Skip the whole integration suite (instead of erroring) when no API key is set.
# A whitespace-only key counts as missing (mirrors evals/office_agent/llm_assist/_env.py),
# so the real-model suites skip cleanly instead of failing on auth.
requires_openai = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY", "").strip(),
    reason="OPENAI_API_KEY is required to call the real gpt-5-mini for these tests",
)
