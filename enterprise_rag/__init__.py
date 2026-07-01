"""
enterprise_rag — Enterprise Document Q&A Engine (企业文档问答引擎).

The self-correcting Agentic RAG (CRAG-style) LangGraph workflow that answers
questions from an ingested internal-document knowledge base, with web-search
fallback and explicit quality gates. Formerly the top-level ``graph`` /
``ingestion`` modules; moved under this package so the repository can grow a
separate ``office_agent`` module alongside it.

Public entry points live in :mod:`enterprise_rag.graph.engine`
(``answer_question`` / ``AnswerOptions`` / ``AnswerResult``); the offline
knowledge-base build lives in :mod:`enterprise_rag.ingestion`.

Imports are side-effect-free: no API keys and no network at import time.
"""
