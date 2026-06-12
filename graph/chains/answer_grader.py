"""
answer_grader.py

Purpose:
- Usefulness check.
- Decide whether the generated answer actually addresses the user's question.

The exported `answer_grader` expects:
    {
        "question": str,    # the original user question
        "generation": str,  # the model's answer
    }
and returns a GradeAnswer object with `.answers_question` (bool).

answers_question == True  -> the answer resolves the user's question.
answers_question == False -> the answer is off-topic or does not address it.
"""

from functools import lru_cache

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class GradeAnswer(BaseModel):
    """
    Structured output for the answer usefulness check.
    """

    answers_question: bool = Field(
        description=(
            "Whether the generated answer actually addresses and resolves the "
            "user's question. "
            "Return true if the answer is relevant and answers the question. "
            "Return false if the answer is off-topic, incomplete to the point of "
            "being useless, or does not address the question."
        )
    )


system_prompt = """
You are an answer usefulness grader for an enterprise RAG system.

Your job is to decide whether the generated answer actually answers the user's
question.

Return true if the answer directly and usefully addresses the question.
Return false if the answer is off-topic, evasive, or fails to resolve the
question.

Only judge usefulness. Do NOT judge whether the answer is grounded in any
documents.
"""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        (
            "human",
            """
User question:
{question}

Generated answer:
{generation}
""",
        ),
    ]
)


@lru_cache(maxsize=1)
def get_answer_grader():
    """
    Lazily build and cache the answer usefulness grader chain.
    The ChatOpenAI client is constructed on first call, not at import time.
    """

    llm = ChatOpenAI(
        model="gpt-5-mini",
        temperature=0,
    )
    structured_llm = llm.with_structured_output(GradeAnswer)
    return prompt | structured_llm


def __getattr__(name):
    # Backward-compatible lazy access to the old module-level `answer_grader`.
    if name == "answer_grader":
        return get_answer_grader()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
