from typing import List, TypedDict
from langchain_core.documents import Document


class GraphState(TypedDict):
    question: str
    documents: List[Document]
    generation: str
    web_search: bool
    retries: int  # number of generations so far; caps the quality-check loop to prevent infinite retries