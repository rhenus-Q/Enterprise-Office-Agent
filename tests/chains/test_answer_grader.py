"""
test_answer_grader.py

Verify that answer_grader judges "usefulness" correctly:
- answers_question == True : the answer actually addresses the user's question.
- answers_question == False: the answer is off-topic / does not resolve it.

Note: these are integration tests; they call the real gpt-5-mini and need OPENAI_API_KEY.
answer_grader only judges "does it answer the question", not whether the answer is
grounded in documents (that's hallucination_grader's job), so the cases focus on
on-topic vs. off-topic.
"""

import pytest

from graph.chains.answer_grader import GradeAnswer, answer_grader
from tests.conftest import requires_openai

# (question, generation) answer actually addresses the question -> expect answers_question == True
USEFUL_CASES = [
    (
        "What is Retrieval-Augmented Generation?",
        "Retrieval-Augmented Generation (RAG) is a technique that retrieves "
        "relevant documents from an external knowledge source and feeds them "
        "to a language model so it can generate grounded answers.",
    ),
    (
        "Why do we split documents into chunks before embedding?",
        "We split documents into smaller chunks because language models have a "
        "limited context window, and smaller semantic chunks make vector search "
        "more precise, so retrieval returns only the most relevant pieces.",
    ),
    (
        "What is the capital of France?",
        "The capital of France is Paris.",
    ),
]


# (question, generation) answer off-topic / does not address it -> expect answers_question == False
NOT_USEFUL_CASES = [
    (
        "What is Retrieval-Augmented Generation?",
        "Paris is the capital of France and is famous for the Eiffel Tower.",
    ),
    (
        "How do vector stores work?",
        "I'm sorry, I don't have enough information to answer that question.",
    ),
    (
        "What is the difference between a retriever and a vector store?",
        "Text splitters break large documents into smaller chunks.",
    ),
]


@requires_openai
def test_answer_grader_returns_gradeanswer_with_bool():
    """The result should be a GradeAnswer, with answers_question as a bool."""

    result = answer_grader.invoke(
        {
            "question": "What is RAG?",
            "generation": "RAG combines retrieval with generation.",
        }
    )

    assert isinstance(result, GradeAnswer)
    assert isinstance(result.answers_question, bool)


@requires_openai
@pytest.mark.parametrize("user_question, generation", USEFUL_CASES)
def test_answer_grader_accepts_relevant_answers(user_question, generation):
    """On-topic answers that actually address the question should be answers_question == True."""

    result = answer_grader.invoke(
        {
            "question": user_question,
            "generation": generation,
        }
    )

    assert result.answers_question is True, (
        f"expected True, got {result.answers_question!r}, question: {user_question!r}"
    )


@requires_openai
@pytest.mark.parametrize("user_question, generation", NOT_USEFUL_CASES)
def test_answer_grader_rejects_offtopic_answers(user_question, generation):
    """Off-topic answers that don't address the question should be answers_question == False."""

    result = answer_grader.invoke(
        {
            "question": user_question,
            "generation": generation,
        }
    )

    assert result.answers_question is False, (
        f"expected False, got {result.answers_question!r}, question: {user_question!r}"
    )
