"""
query_rewriter.py

Purpose:
- Make web-search retries meaningful.
- When a generated answer is grounded but judged not useful, the workflow runs
  another web search. Re-running the identical query would mostly fetch the
  same content, so this chain rewrites the user's question into a more
  specific search query, informed by the previous (not useful) answer.

The chain expects:
    {
        "question": str,         # the original user question
        "previous_answer": str,  # the answer that was judged not useful
    }
and returns the rewritten query as a plain string.
"""

from functools import lru_cache

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI


system_prompt = """
You are a web search query rewriter for an enterprise RAG system.

The previous answer to the user's question was judged not useful, so a new web
search will be run. Rewrite the user's question into a better web search query.

Rules:
- Preserve the user's original intent exactly; do not change the topic.
- Make the query more specific and keyword-focused so a search engine returns
  more relevant results.
- Use the previous answer only to understand what was missing or off-target.
- Do not invent details that are not implied by the question.
- Return ONLY the rewritten query text, with no quotes and no explanation.
"""

prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        (
            "human",
            """
User question:
{question}

Previous (not useful) answer:
{previous_answer}
""",
        ),
    ]
)


@lru_cache(maxsize=1)
def get_query_rewriter():
    """
    Lazily build and cache the query rewriter chain.
    The ChatOpenAI client is constructed on first call, not at import time.
    """

    llm = ChatOpenAI(
        model="gpt-5-mini",
        temperature=0,
    )
    return prompt | llm | StrOutputParser()
