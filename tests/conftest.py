"""
conftest.py

pytest loads conftest.py before collecting tests.
We load env vars from .env (OPENAI_API_KEY, etc.) here, before any
`from graph.chains.question_router import ...` triggers ChatOpenAI construction.
"""

import os

import pytest
from dotenv import load_dotenv

load_dotenv()


# Skip the whole integration suite (instead of erroring) when no API key is set.
requires_openai = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="OPENAI_API_KEY is required to call the real gpt-5-mini for these tests",
)
