"""
ingestion.py

Purpose:
- Load documents from web pages
- Split documents into smaller chunks
- Convert chunks into embeddings
- Store them in a Chroma vector database
- Expose a retriever for the LangGraph retrieve node

This file prepares the knowledge base for the Agentic RAG workflow.
"""

from functools import lru_cache

from dotenv import load_dotenv

from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma


load_dotenv()


# 1. Raw knowledge sources
# Replace these with enterprise internal doc URLs, technical docs, product docs, SOPs, etc.
URLS = [
    "https://python.langchain.com/docs/concepts/rag/",
    "https://python.langchain.com/docs/concepts/vectorstores/",
    "https://python.langchain.com/docs/concepts/text_splitters/",
]


# 2. Chroma local persistence directory
# The vector database is stored in this folder
CHROMA_PATH = "chroma_db"


# 3. Chroma collection name
COLLECTION_NAME = "agentic_rag_docs"


def load_documents():
    """
    Load raw documents from URLs.

    Returns:
        List[Document]: LangChain Document objects.
    """

    docs = []

    for url in URLS:
        loader = WebBaseLoader(url)
        loaded_docs = loader.load()
        docs.extend(loaded_docs)

    print(f"Loaded {len(docs)} raw documents.")
    return docs


def split_documents(documents):
    """
    Split large documents into smaller chunks.

    Why split?
    - LLM context is limited
    - Vector search works better with smaller semantic chunks
    - Retrieval can return only the most relevant chunks

    Returns:
        List[Document]: Chunked documents.
    """

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )

    splits = text_splitter.split_documents(documents)

    print(f"Split into {len(splits)} chunks.")
    return splits


def build_vectorstore():
    """
    Build a local Chroma vector store from loaded and split documents.

    Returns:
        Chroma: A Chroma vector store instance.
    """

    documents = load_documents()
    splits = split_documents(documents)

    embeddings = OpenAIEmbeddings()

    vectorstore = Chroma.from_documents(
        documents=splits,
        embedding=embeddings,
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