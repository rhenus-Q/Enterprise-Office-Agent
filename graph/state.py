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