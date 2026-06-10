
"""
test_generation.py

Tests for the answer-generation chain in graph/chains/generation.py.

Two surfaces are covered:
1. format_documents() -- a pure function (no LLM). Fast, deterministic unit tests
   that need no API key.
2. generation_chain  -- the full LCEL chain. It calls the real gpt-5-mini, so those
   tests are integration tests and need OPENAI_API_KEY (skipped otherwise).

The chain expects {"question": str, "documents": List[Document]} and returns a
plain string answer.
"""

from langchain_core.documents import Document

from LangGraph.Agentic_RAG_Claude.tests.conftest import requires_openai

from graph.chains.generation import format_documents, generation_chain


# ---------------------------------------------------------------------------
# format_documents -- pure function, no LLM, no API key required
# ---------------------------------------------------------------------------


def test_format_documents_joins_with_divider():
    """Multiple documents are joined into one string separated by a divider."""

    docs = [
        Document(page_content="First chunk."),
        Document(page_content="Second chunk."),
    ]

    result = format_documents(docs)

    assert "First chunk." in result
    assert "Second chunk." in result
    # The two chunks are separated by the divider, not concatenated directly.
    assert "First chunk.\n\n---\n\nSecond chunk." == result


def test_format_documents_single_document_has_no_divider():
    """A single document is returned as-is, with no divider."""

    result = format_documents([Document(page_content="Only chunk.")])

    assert result == "Only chunk."
    assert "---" not in result


def test_format_documents_empty_list_returns_placeholder():
    """An empty document list returns the 'no documents' placeholder."""

    assert format_documents([]) == "No documents available."


# ---------------------------------------------------------------------------
# generation_chain -- integration, calls real gpt-5-mini
# ---------------------------------------------------------------------------


GROUNDING_DOCS = [
    Document(
        page_content=(
            "Retrieval-Augmented Generation (RAG) retrieves relevant documents "
            "from an external knowledge source and passes them to a language "
            "model so it can generate grounded answers."
        )
    ),
]


@requires_openai
def test_generation_chain_returns_nonempty_string():
    """The chain should return a non-empty plain string answer."""

    result = generation_chain.invoke(
        {
            "question": "What is Retrieval-Augmented Generation?",
            "documents": GROUNDING_DOCS,
        }
    )

    assert isinstance(result, str)
    assert result.strip() != ""


@requires_openai
def test_generation_chain_answer_uses_unique_context_fact():
    """The chain should use a unique fact from the provided context."""

    unique_docs = [
        Document(
            page_content=(
                "In this test corpus, Retrieval-Augmented Generation is described "
                "as the Silver Bridge method. The Silver Bridge method retrieves "
                "company-approved documents before generating an answer."
            )
        )
    ]

    result = generation_chain.invoke(
        {
            "question": (
                "According to the documents, what method describes "
                "Retrieval-Augmented Generation?"
            ),
            "documents": unique_docs,
        }
    )

    assert isinstance(result, str)
    assert result.strip() != ""

    lowered = result.lower()

    assert "silver bridge" in lowered, (
        f"expected answer to use the unique context fact, got: {result!r}"
    )



"""
test_generation.py

Tests for the answer-generation logic in graph/chains/generation.py.

Three surfaces are covered:
1. format_documents() -- a pure function (no LLM). Fast, deterministic unit tests
   that need no API key.
2. generate_answer()   -- deterministic wrapper logic. It returns a fixed
   insufficient-context answer when no documents are provided.
3. generation_chain    -- the full LCEL chain. It calls the real gpt-5-mini, so
   those tests are integration tests and need OPENAI_API_KEY (skipped otherwise).

The chain expects {"question": str, "documents": List[Document]} and returns a
plain string answer.
"""

from langchain_core.documents import Document

from LangGraph.Agentic_RAG_Claude.tests.conftest import requires_openai

from graph.chains.generation import (
    INSUFFICIENT_CONTEXT_ANSWER,
    format_documents,
    generate_answer,
    generation_chain,
)


# ---------------------------------------------------------------------------
# format_documents -- pure function, no LLM, no API key required
# ---------------------------------------------------------------------------


def test_format_documents_joins_with_divider():
    """Multiple documents are joined into one string separated by a divider."""

    docs = [
        Document(page_content="First chunk."),
        Document(page_content="Second chunk."),
    ]

    result = format_documents(docs)

    assert "First chunk." in result
    assert "Second chunk." in result
    # The two chunks are separated by the divider, not concatenated directly.
    assert "First chunk.\n\n---\n\nSecond chunk." == result


def test_format_documents_single_document_has_no_divider():
    """A single document is returned as-is, with no divider."""

    result = format_documents([Document(page_content="Only chunk.")])

    assert result == "Only chunk."
    assert "---" not in result


def test_format_documents_empty_list_returns_placeholder():
    """An empty document list returns the 'no documents' placeholder."""

    assert format_documents([]) == "No documents available."


# ---------------------------------------------------------------------------
# generate_answer -- deterministic wrapper logic, no LLM for empty documents
# ---------------------------------------------------------------------------


def test_generate_answer_returns_fixed_message_when_no_context():
    """With no documents, generate_answer returns a fixed message without LLM."""

    result = generate_answer(
        {
            "question": "What is the internal SOP for expense approval?",
            "documents": [],
        }
    )

    assert result == INSUFFICIENT_CONTEXT_ANSWER


def test_generate_answer_returns_fixed_message_when_documents_key_missing():
    """Missing documents are treated the same as an empty document list."""

    result = generate_answer(
        {
            "question": "What is the internal SOP for expense approval?",
        }
    )

    assert result == INSUFFICIENT_CONTEXT_ANSWER


# ---------------------------------------------------------------------------
# generation_chain -- integration, calls real gpt-5-mini
# ---------------------------------------------------------------------------


GROUNDING_DOCS = [
    Document(
        page_content=(
            "Retrieval-Augmented Generation (RAG) retrieves relevant documents "
            "from an external knowledge source and passes them to a language "
            "model so it can generate grounded answers."
        )
    ),
]


@requires_openai
def test_generation_chain_returns_nonempty_string():
    """The chain should return a non-empty plain string answer."""

    result = generation_chain.invoke(
        {
            "question": "What is Retrieval-Augmented Generation?",
            "documents": GROUNDING_DOCS,
        }
    )

    assert isinstance(result, str)
    assert result.strip() != ""


@requires_openai
def test_generation_chain_answer_uses_unique_context_fact():
    """The chain should use a unique fact from the provided context."""

    unique_docs = [
        Document(
            page_content=(
                "In this test corpus, Retrieval-Augmented Generation is described "
                "as the Silver Bridge method. The Silver Bridge method retrieves "
                "company-approved documents before generating an answer."
            )
        )
    ]

    result = generation_chain.invoke(
        {
            "question": (
                "According to the documents, what method describes "
                "Retrieval-Augmented Generation?"
            ),
            "documents": unique_docs,
        }
    )

    assert isinstance(result, str)
    assert result.strip() != ""

    lowered = result.lower()

    assert "silver bridge" in lowered, (
        f"expected answer to use the unique context fact, got: {result!r}"
    )

