from typing import TypedDict

from langchain_core.documents import Document


class GraphState(TypedDict):
    # All fields are plain last-value channels (no typing.Annotated reducers).
    # enterprise_rag/graph/engine.py::_run_graph_with_trace merges streamed node updates with
    # dict.update(), which reproduces app.invoke() only for last-value channels.
    # If a reducer / accumulating channel is ever added here, revisit that merge.
    question: str
    documents: list[Document]
    generation: str
    web_search: bool
    web_search_enabled: (
        bool  # WEB_SEARCH_ENABLED toggle; False = privacy mode, never call external web search
    )
    web_fallback_policy: str  # resolved per-run WEB_FALLBACK_POLICY ("conservative" / "aggressive" / "disabled"); seeded once at run start so graph decisions never read os.environ mid-run
    retries: (
        int  # number of generations so far; caps the quality-check loop to prevent infinite retries
    )
    stop_reason: (
        str  # why the run ended early ("" = normal finish); lets the caller add user-facing caveats
    )
    insufficient_context: bool  # True = the latest generation is the deterministic insufficient-context answer (no usable documents); skips the graders, which have nothing to verify
    retry_feedback: str  # corrective instruction for the next generation attempt ("" = none)
    search_query: (
        str  # rewritten web search query for retry rounds ("" = use the original question)
    )
    llm_call_count: int  # tracked LLM calls this run (generation, query rewrite, web-result grading) — a budgeted operational counter, NOT total LLM usage: router and grader calls are not individually tracked
    web_search_count: int  # Tavily searches this run
    web_result_grading_count: int  # individual web results sent to the relevance grader this run
