"""
hallucination_grader.py

Purpose:
- Grounding check (anti-hallucination).
- Decide whether the generated answer is supported by the retrieved documents.

The exported `hallucination_grader` takes its data directly from GraphState:
    {
        "documents": List[Document],  # state["documents"] (list, not str)
        "generation": str,            # state["generation"]
    }
and returns a GradeHallucination object with `.is_grounded` (bool).

is_grounded == True  -> the answer is grounded in the documents.
is_grounded == False -> the answer contains unsupported / hallucinated content.
"""

from functools import lru_cache

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class GradeHallucination(BaseModel):
    """
    Structured output for the grounding / hallucination check.
    """

    is_grounded: bool = Field(
        description=(
            "Whether the generated answer is grounded in and supported by the "
            "provided documents. "
            "Return true if every claim in the answer is backed by the documents. "
            "Return false if the answer contains facts that are not supported by "
            "the documents (hallucination)."
        )
    )


system_prompt = """
You are a grounding grader for an enterprise RAG system.

Your job is to decide whether the generated answer is grounded in the set of
provided documents.

Return true if all of the information in the answer can be traced back to the
documents.
Return false if the answer introduces facts, numbers, or claims that are not
supported by the documents.

Only judge grounding. Do NOT judge whether the answer is helpful or complete.
"""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        (
            "human",
            """
Set of documents:
{documents}

Generated answer:
{generation}
""",
        ),
    ]
)


def format_documents(documents: list[Document]) -> str:
    """
    Join the List[Document] from GraphState into a single plain-text context.
    If a string is passed in, return it unchanged.
    """

    if isinstance(documents, str):
        return documents

    if not documents:
        return "No documents available."

    return "\n\n---\n\n".join(doc.page_content for doc in documents)


@lru_cache(maxsize=1)
def get_hallucination_grader():
    """
    Lazily build and cache the grounding/hallucination grader chain.
    The ChatOpenAI client is constructed on first call, not at import time.

    Documents are formatted to text first, then passed to prompt + structured LLM,
    so the chain can be called directly with GraphState's documents (List[Document]).
    """

    llm = ChatOpenAI(
        model="gpt-5-mini",
        temperature=0,
    )
    structured_llm = llm.with_structured_output(GradeHallucination)
    return (
        {
            "documents": lambda x: format_documents(x["documents"]),
            "generation": lambda x: x["generation"],
        }
        | prompt
        | structured_llm
    )


def __getattr__(name):
    # Backward-compatible lazy access to the old module-level `hallucination_grader`.
    if name == "hallucination_grader":
        return get_hallucination_grader()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
