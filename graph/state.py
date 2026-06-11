from typing import List, TypedDict
from langchain_core.documents import Document


class GraphState(TypedDict):
    question: str
    documents: List[Document]
    generation: str
    web_search: bool
    web_search_enabled: bool  # WEB_SEARCH_ENABLED toggle; False = privacy mode, never call external web search
    retries: int  # number of generations so far; caps the quality-check loop to prevent infinite retries
    stop_reason: str  # why the run ended early ("" = normal finish); lets the caller add user-facing caveats
    insufficient_context: bool  # True = the latest generation is the deterministic insufficient-context answer (no usable documents); skips the graders, which have nothing to verify
    retry_feedback: str  # corrective instruction for the next generation attempt ("" = none)
    search_query: str  # rewritten web search query for retry rounds ("" = use the original question)
    llm_call_count: int  # counted LLM calls this run (generation, query rewrite, web-result grading)
    web_search_count: int  # Tavily searches this run
    web_result_grading_count: int  # individual web results sent to the relevance grader this run