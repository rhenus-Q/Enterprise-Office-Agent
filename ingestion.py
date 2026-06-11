"""
ingestion.py

Purpose:
- Load the synthetic AcmeCorp internal-document corpus (local Markdown files)
- Split documents into smaller chunks
- Convert chunks into embeddings
- Store them in a Chroma vector database (idempotent rebuild)
- Expose a retriever for the LangGraph retrieve node

This file prepares the knowledge base for the Agentic RAG workflow.

The corpus under data/acmecorp_internal_docs/ is entirely fictional synthetic
content (no real company data) — replace it with real internal documents in
an actual deployment. Each document carries provenance metadata (source,
title, source_type, document_category) that survives chunking and feeds the
user-facing Sources section in main.py.
"""

from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma


load_dotenv()


# 1. Synthetic enterprise corpus: AcmeCorp internal Markdown documents.
# Anchored to this file's directory so ingestion works from any CWD.
CORPUS_DIR = Path(__file__).parent / "data" / "acmecorp_internal_docs"

# document_category metadata per file (provenance / future filtering).
# Files not listed here fall back to "internal_document".
DOCUMENT_CATEGORIES = {
    "vpn_policy.md": "it_security",
    "incident_response_playbook.md": "it_security",
    "expense_reimbursement_policy.md": "finance",
    "on_call_escalation_policy.md": "operations",
    "data_retention_policy.md": "compliance",
    "employee_onboarding_guide.md": "hr",
}


# 2. Chroma local persistence directory
# The vector database is stored in this folder
CHROMA_PATH = "chroma_db"


# 3. Chroma collection name
COLLECTION_NAME = "agentic_rag_docs"


def _extract_title(text: str, fallback: str) -> str:
    """Return the first Markdown H1 heading, or the fallback if none exists."""

    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return fallback


def load_documents():
    """
    Load the local Markdown corpus from CORPUS_DIR.

    Each file becomes one Document with provenance metadata:
    - source: repo-relative path (stable citation key)
    - title: the document's H1 heading (shown in the Sources section)
    - source_type: "local_corpus" (distinguishes from the web supplement)
    - document_category: coarse policy domain

    Returns:
        List[Document]: LangChain Document objects.
    """

    docs = []

    for path in sorted(CORPUS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        docs.append(
            Document(
                page_content=text,
                metadata={
                    "source": f"data/acmecorp_internal_docs/{path.name}",
                    "title": _extract_title(text, path.stem),
                    "source_type": "local_corpus",
                    "document_category": DOCUMENT_CATEGORIES.get(
                        path.name, "internal_document"
                    ),
                },
            )
        )

    print(f"Loaded {len(docs)} corpus documents from {CORPUS_DIR}.")
    return docs


def split_documents(documents):
    """
    Split large documents into smaller chunks.

    Why split?
    - LLM context is limited
    - Vector search works better with smaller semantic chunks
    - Retrieval can return only the most relevant chunks

    Returns:
        List[Document]: Chunked documents (metadata is copied to every chunk).
    """

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )

    splits = text_splitter.split_documents(documents)

    print(f"Split into {len(splits)} chunks.")
    return splits


def _chunk_ids(splits):
    """
    Deterministic per-chunk ids: "<source>::chunk-<index>".

    Stable ids plus the collection reset in build_vectorstore make ingestion
    idempotent — re-running replaces the index instead of appending
    duplicate chunks.
    """

    ids = []
    counters = {}

    for chunk in splits:
        source = chunk.metadata["source"]
        index = counters.get(source, 0)
        counters[source] = index + 1
        ids.append(f"{source}::chunk-{index}")

    return ids


def build_vectorstore():
    """
    Build the local Chroma vector store from the corpus (idempotent).

    The existing collection is dropped before re-indexing, so re-running
    ingestion never duplicates chunks and removed corpus files disappear
    from the index. Tradeoff: a run that fails mid-ingestion leaves the
    knowledge base empty until ingestion is re-run successfully.

    Returns:
        Chroma: A Chroma vector store instance.
    """

    documents = load_documents()
    splits = split_documents(documents)

    embeddings = OpenAIEmbeddings()

    # Idempotent rebuild: drop any previous index of the same collection.
    Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_PATH,
    ).delete_collection()
    print("Cleared existing collection (idempotent rebuild).")

    vectorstore = Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
        ids=_chunk_ids(splits),
        collection_name=COLLECTION_NAME,
        persist_directory=CHROMA_PATH,
    )

    print("Vector store built successfully.")
    return vectorstore


@lru_cache(maxsize=1)
def get_retriever():
    """
    Create a retriever from the Chroma vector store.

    Cached so the Chroma client / embeddings are constructed only once, and only
    when first called at runtime (not at import time).

    This retriever will be used by the retrieve node.

    Returns:
        VectorStoreRetriever
    """

    embeddings = OpenAIEmbeddings()

    vectorstore = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        persist_directory=CHROMA_PATH,
    )

    retriever = vectorstore.as_retriever(
        search_kwargs={"k": 3}
    )

    return retriever


if __name__ == "__main__":
    build_vectorstore()
