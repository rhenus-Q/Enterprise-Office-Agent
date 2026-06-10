"""
generation.py

Purpose:
- Build the RAG answer-generation chain.
- Take the user question and a list of retrieved documents,
  and produce a grounded natural-language answer.

The exported `generation_chain` is the raw LCEL chain.
It expects:
    {
        "question": str,
        "documents": List[Document],
    }
and returns a plain string answer.

The exported `generate_answer` function is a mockable seam for node tests.
It accepts:
    question: str
    documents: list[Document]
and returns a plain string answer.
"""

from functools import lru_cache

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI


INSUFFICIENT_CONTEXT_ANSWER = (
    "I do not have enough information in the provided documents."
)


system_prompt = """
You are an enterprise knowledge assistant for internal document Q&A.

Answer the user's question using ONLY the provided context documents.

Rules:
- Base your answer strictly on the context. Do not use outside knowledge.
- If the context does not contain enough information to answer, say that you
  do not have enough information in the provided documents.
- Be concise, accurate, and professional.
- Do not fabricate facts, sources, or numbers.
"""


prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        (
            "human",
            """
User question:
{question}

Context documents:
{context}
""",
        ),
    ]
)


def format_documents(documents: list[Document]) -> str:
    """
    Join a list of Documents into a single plain-text context.
    Documents are separated by a divider so the model can tell sources apart.
    """

    if not documents:
        return "No documents available."

    return "\n\n---\n\n".join(doc.page_content for doc in documents)


@lru_cache(maxsize=1)
def get_generation_chain():
    """
    Lazily build and cache the generation LCEL chain.

    The ChatOpenAI client is constructed here on first call, not at import time,
    so importing this module needs no API key or network.

    Chain:
    1. format documents into a context string
    2. pass to prompt + llm to generate the answer
    3. extract a plain string with StrOutputParser
    """

    llm = ChatOpenAI(
        model="gpt-5-mini",
        temperature=0,
    )

    return (
        {
            "context": lambda x: format_documents(x["documents"]),
            "question": lambda x: x["question"],
        }
        | prompt
        | llm
        | StrOutputParser()
    )


def generate_answer(question: str, documents: list[Document]) -> str:
    """
    Generate an answer from a question + documents.

    This function is the single mockable seam used by the generate node.
    If no documents are available, return a deterministic insufficient-context
    answer without calling the LLM.
    """

    if not documents:
        return INSUFFICIENT_CONTEXT_ANSWER

    return get_generation_chain().invoke(
        {
            "question": question,
            "documents": documents,
        }
    )


def __getattr__(name):
    # Backward-compatible lazy access to the old module-level `generation_chain`.
    # Building it on attribute access (not import) keeps the import free of the LLM client.
    if name == "generation_chain":
        return get_generation_chain()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")