from functools import lru_cache

from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI


class RetrievalGrade(BaseModel):
    """
    Structured output for document relevance grading.
    """

    is_relevant: bool = Field(
        description=(
            "Whether the document is relevant to the user's question. "
            "Return true if the document contains information that can help answer the question. "
            "Return false if the document is unrelated or useless for answering the question."
        )
    )


system_prompt = """
You are a document relevance grader for an enterprise RAG system.

Your job is to decide whether a retrieved document is relevant to the user's question.

Return true if the document contains information that can help answer the question.
Return false if the document is unrelated, off-topic, or does not help answer the question.

Be strict, but not overly strict:
- If the document directly answers the question, return true.
- If the document provides useful background for answering the question, return true.
- If the document is only vaguely related and does not help answer the question, return false.
"""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        (
            "human",
            """
User question:
{question}

Retrieved document:
{document}
""",
        ),
    ]
)

@lru_cache(maxsize=1)
def get_retrieval_grader():
    """
    Lazily build and cache the retrieval grader chain.
    The ChatOpenAI client is constructed on first call, not at import time.
    """

    llm = ChatOpenAI(
        model="gpt-5-mini",
        temperature=0,
    )
    structured_llm = llm.with_structured_output(RetrievalGrade)
    return prompt | structured_llm


def __getattr__(name):
    # Backward-compatible lazy access to the old module-level `retrieval_grader`.
    if name == "retrieval_grader":
        return get_retrieval_grader()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")