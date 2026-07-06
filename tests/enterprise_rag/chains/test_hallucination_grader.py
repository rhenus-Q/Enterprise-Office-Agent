"""
test_hallucination_grader.py

Verify that hallucination_grader judges "grounding" correctly:
- is_grounded == True : every claim in the answer is backed by the documents.
- is_grounded == False: the answer adds facts not supported by the documents.

Note: these are integration tests; they call the real gpt-5-mini and need OPENAI_API_KEY.
hallucination_grader only judges grounding, not whether the answer is helpful or
complete (that's answer_grader's job), so the cases focus on supported vs. fabricated.

The grader accepts documents as a List[Document] (it formats them internally),
so each case passes a list of Document objects, mirroring GraphState.
"""

import pytest
from langchain_core.documents import Document

from enterprise_rag.graph.chains.hallucination_grader import (
    GradeHallucination,
    hallucination_grader,
)
from tests.conftest import requires_openai

# Shared source documents the answers are graded against.
DOCS = [
    Document(
        page_content=(
            "Retrieval-Augmented Generation (RAG) retrieves relevant documents "
            "from an external knowledge source and passes them to a language "
            "model so it can generate grounded answers."
        )
    ),
    Document(
        page_content=(
            "Text splitters break large documents into smaller chunks. Smaller "
            "chunks improve vector search precision and fit within the model's "
            "limited context window."
        )
    ),
]


# (documents, generation) answer fully supported by the docs -> expect is_grounded == True
GROUNDED_CASES = [
    (
        DOCS,
        "RAG retrieves relevant documents from an external knowledge source and "
        "feeds them to a language model to produce grounded answers.",
    ),
    (
        DOCS,
        "Text splitters split large documents into smaller chunks, which improves "
        "vector search precision and helps fit the model's limited context window.",
    ),
]


# (documents, generation) answer adds unsupported / fabricated facts -> expect is_grounded == False
NOT_GROUNDED_CASES = [
    (
        DOCS,
        "RAG was invented by OpenAI in 2017 and always uses exactly five documents per query.",
    ),
    (
        DOCS,
        "Text splitters use a fixed chunk size of 512 tokens and require a GPU to run.",
    ),
]


@requires_openai
def test_hallucination_grader_returns_gradehallucination_with_bool():
    """The result should be a GradeHallucination, with is_grounded as a bool."""

    result = hallucination_grader.invoke(
        {
            "documents": DOCS,
            "generation": "RAG retrieves documents and feeds them to a model.",
        }
    )

    assert isinstance(result, GradeHallucination)
    assert isinstance(result.is_grounded, bool)


@requires_openai
@pytest.mark.parametrize("documents, generation", GROUNDED_CASES)
def test_hallucination_grader_accepts_grounded_answers(documents, generation):
    """Answers fully supported by the documents should be is_grounded == True."""

    result = hallucination_grader.invoke(
        {
            "documents": documents,
            "generation": generation,
        }
    )

    assert result.is_grounded is True, (
        f"expected True, got {result.is_grounded!r}, generation: {generation!r}"
    )


@requires_openai
@pytest.mark.parametrize("documents, generation", NOT_GROUNDED_CASES)
def test_hallucination_grader_rejects_unsupported_answers(documents, generation):
    """Answers that add unsupported facts should be is_grounded == False."""

    result = hallucination_grader.invoke(
        {
            "documents": documents,
            "generation": generation,
        }
    )

    assert result.is_grounded is False, (
        f"expected False, got {result.is_grounded!r}, generation: {generation!r}"
    )
