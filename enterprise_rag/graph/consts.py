RETRIEVE = "retrieve"
GRADE_DOCUMENTS = "grade_documents"
GENERATE = "generate"
WEBSEARCH = "websearch"
WEB_SEARCH_DISABLED_NOTICE = "web_search_disabled_notice"
WEB_FALLBACK_DISABLED_NOTICE = "web_fallback_disabled_notice"
MAX_RETRIES_NOT_GROUNDED_NOTICE = "max_retries_not_grounded_notice"
MAX_RETRIES_NOT_USEFUL_NOTICE = "max_retries_not_useful_notice"
ADD_GROUNDING_FEEDBACK = "add_grounding_feedback"
REWRITE_QUERY = "rewrite_query"
BUDGET_EXHAUSTED_NOTICE = "budget_exhausted_notice"
TOOL_ERROR_NOTICE = "tool_error_notice"
CLEAR_TRANSIENT_TOOL_ERROR = "clear_transient_tool_error"

# Metadata "source" marker identifying the merged web-search supplement
# Document. Shared by the web_search node (which writes it),
# enterprise_rag/graph/formatting.py (which reads it for the Sources section), and the
# eval harness (which inspects source metadata), so they never drift.
WEB_SEARCH_SOURCE = "web_search"

# Values for GraphState["stop_reason"] ("" = normal finish).
STOP_REASON_WEB_SEARCH_DISABLED = "web_search_disabled"
STOP_REASON_WEB_FALLBACK_DISABLED = (
    "web_fallback_disabled"  # WEB_FALLBACK_POLICY=disabled blocked a local run's web retry
)
STOP_REASON_MAX_RETRIES_NOT_GROUNDED = "max_retries_not_grounded"
STOP_REASON_MAX_RETRIES_NOT_USEFUL = "max_retries_not_useful"
STOP_REASON_BUDGET_EXHAUSTED = "budget_exhausted"

# External-dependency failure stop reasons. Degraded runs record these so the
# caller can attach an honest caveat instead of crashing or staying silent.
STOP_REASON_RETRIEVAL_ERROR = "retrieval_error"  # Chroma / retriever failed
STOP_REASON_WEB_SEARCH_ERROR = "web_search_error"  # Tavily search failed
STOP_REASON_GENERATION_ERROR = "generation_error"  # generation LLM call failed
STOP_REASON_TOOL_ERROR = "tool_error"  # a grader / query-rewrite call failed
