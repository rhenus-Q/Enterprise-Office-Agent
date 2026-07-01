"""
test_retrieval_grader.py

Verify that retrieval_grader judges single-document relevance correctly:
- is_relevant == True : the document can help answer the question.
- is_relevant == False: the document is unrelated / not helpful.

Note: these are integration tests; they call the real gpt-5-mini and need OPENAI_API_KEY.
retrieval_grader scores ONE document at a time and takes the document as a plain
string ("document", singular) -- this mirrors how grade_documents passes
doc.page_content per document.
"""

import pytest

from enterprise_rag.graph.chains.retrieval_grader import RetrievalGrade, retrieval_grader
from tests.conftest import requires_openai

# (question, document) document helps answer the question -> expect is_relevant == True
RELEVANT_CASES = [
    (
        "What is Retrieval-Augmented Generation?",
        "Retrieval-Augmented Generation (RAG) retrieves relevant documents from "
        "an external knowledge source and passes them to a language model so it "
        "can generate grounded answers.",
    ),
    (
        "Why do we split documents into chunks?",
        "Text splitters break large documents into smaller chunks. Smaller chunks "
        "improve vector search precision and fit within the model's limited "
        "context window.",
    ),
    (
        "How do vector stores enable semantic search?",
        "A vector store indexes embeddings of text chunks and retrieves the "
        "nearest vectors to a query embedding, enabling semantic similarity search.",
    ),
]


# (question, document) document is unrelated to the question -> expect is_relevant == False
IRRELEVANT_CASES = [
    (
        "What is Retrieval-Augmented Generation?",
        "The Eiffel Tower is a wrought-iron lattice tower in Paris, completed in "
        "1889 for the World's Fair.",
    ),
    (
        "How do vector stores work?",
        "A balanced diet includes proteins, carbohydrates, and healthy fats, and "
        "regular exercise supports cardiovascular health.",
    ),
    (
        "Why do we split documents into chunks?",
        "The 2018 FIFA World Cup was held in Russia and won by the French national football team.",
    ),
]


@requires_openai
def test_retrieval_grader_returns_retrievalgrade_with_bool():
    """The result should be a RetrievalGrade, with is_relevant as a bool."""

    result = retrieval_grader.invoke(
        {
            "question": "What is RAG?",
            "document": "RAG retrieves documents and feeds them to a model.",
        }
    )

    assert isinstance(result, RetrievalGrade)
    assert isinstance(result.is_relevant, bool)


@requires_openai
@pytest.mark.parametrize("user_question, document", RELEVANT_CASES)
def test_retrieval_grader_accepts_relevant_documents(user_question, document):
    """Documents that can help answer the question should be is_relevant == True."""

    result = retrieval_grader.invoke(
        {
            "question": user_question,
            "document": document,
        }
    )

    assert result.is_relevant is True, (
        f"expected True, got {result.is_relevant!r}, question: {user_question!r}"
    )


@requires_openai
@pytest.mark.parametrize("user_question, document", IRRELEVANT_CASES)
def test_retrieval_grader_rejects_irrelevant_documents(user_question, document):
    """Documents unrelated to the question should be is_relevant == False."""

    result = retrieval_grader.invoke(
        {
            "question": user_question,
            "document": document,
        }
    )

    assert result.is_relevant is False, (
        f"expected False, got {result.is_relevant!r}, question: {user_question!r}"
    )
