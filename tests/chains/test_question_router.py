"""
test_question_router.py

Verify that question_router routes questions correctly to:
- "retrieve" : questions on topics covered by the internal vector store
               (AcmeCorp internal documents: VPN access, expenses, incident
               response, on-call escalation, data retention, onboarding).
- "websearch": questions needing real-time / external information not in the store
               (current events, weather, latest version numbers, etc.).

Note: these are integration tests; they call the real gpt-5-mini and need OPENAI_API_KEY.
Routing is stable for clear-cut questions but still depends on model judgment,
so only unambiguous examples are used here.
"""

import pytest

from tests.conftest import requires_openai

from graph.consts import RETRIEVE, WEBSEARCH
from graph.chains.question_router import question_router, RouteQuery


# Questions that should go to vector retrieval (all on indexed AcmeCorp policy topics)
RETRIEVE_QUESTIONS = [
    "How do I request VPN access?",
    "What expenses require manager approval?",
    "When should a security incident be escalated to Sev-1?",
    "Who gets paged for after-hours production incidents?",
    "How long are audit logs retained?",
    "What should a new employee do during their first week?",
]


# Questions that should go to web search (real-time / external info, clearly not in the internal docs)
WEBSEARCH_QUESTIONS = [
    "What is the weather in Tokyo today?",
    "Who won the most recent FIFA World Cup?",
    "What is the current stock price of NVIDIA?",
    "What are the latest news headlines today?",
     "What is today's exchange rate between the US dollar and the Chinese yuan?",
]


@requires_openai
def test_router_returns_routequery_with_valid_datasource():
    """The result should be a RouteQuery, with datasource one of the two valid values."""

    result = question_router.invoke({"question": "How do I request VPN access?"})

    assert isinstance(result, RouteQuery)
    assert result.datasource in {RETRIEVE, WEBSEARCH}


@requires_openai
@pytest.mark.parametrize("user_question", RETRIEVE_QUESTIONS)
def test_router_routes_internal_topics_to_retrieve(user_question):
    """Questions on internal knowledge-base topics should route to retrieve."""

    result = question_router.invoke({"question": user_question})

    assert result.datasource == RETRIEVE, (
        f"expected retrieve, got {result.datasource!r}, question: {user_question!r}"
    )


@requires_openai
@pytest.mark.parametrize("user_question", WEBSEARCH_QUESTIONS)
def test_router_routes_external_topics_to_websearch(user_question):
    """Questions needing real-time / external info should route to websearch."""

    result = question_router.invoke({"question": user_question})

    assert result.datasource == WEBSEARCH, (
        f"expected websearch, got {result.datasource!r}, question: {user_question!r}"
    )





