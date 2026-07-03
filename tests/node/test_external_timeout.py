"""
Unit tests for the non-chat external request timeout
(enterprise_rag/graph/config.py::external_request_timeout_seconds and its wiring
into enterprise_rag/ingestion.py's OpenAIEmbeddings construction).

Fully mocked and keys-free: OpenAIEmbeddings and Chroma are patched at the
ingestion module seam, so no real embeddings/vector-store client is built and no
network call is made. Mirrors the LLM-timeout config tests in
tests/graph/test_budget.py.
"""

import importlib

import pytest
from langchain_core.documents import Document

from enterprise_rag.graph.config import (
    DEFAULT_EXTERNAL_REQUEST_TIMEOUT_SECONDS,
    external_request_timeout_seconds,
)

# Resolve the real module object for monkeypatching its imported names.
ingestion = importlib.import_module("enterprise_rag.ingestion")


@pytest.fixture(autouse=True)
def _clear_retriever_cache():
    """get_retriever is @lru_cache(maxsize=1); clear it so each test re-runs the
    (patched) construction under the current environment."""

    ingestion.get_retriever.cache_clear()
    yield
    ingestion.get_retriever.cache_clear()


def _patch_embeddings(monkeypatch):
    """Patch ingestion.OpenAIEmbeddings to record constructor kwargs (no client)."""

    calls = []

    def _fake_embeddings(**kwargs):
        calls.append(kwargs)
        return object()  # opaque embedding_function placeholder

    monkeypatch.setattr(ingestion, "OpenAIEmbeddings", _fake_embeddings)
    return calls


class _FakeVectorstore:
    """Stand-in for Chroma: records construction, no persistence, no network."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def as_retriever(self, **kwargs):
        return {"retriever_search_kwargs": kwargs.get("search_kwargs")}


# ---------------------------------------------------------------------------
# Config function: default / override / invalid fallback
# (shares _positive_int_from_env with the budgets and the LLM timeout)
# ---------------------------------------------------------------------------


def test_external_request_timeout_default_when_env_unset(monkeypatch):
    monkeypatch.delenv("EXTERNAL_REQUEST_TIMEOUT_SECONDS", raising=False)

    assert external_request_timeout_seconds() == DEFAULT_EXTERNAL_REQUEST_TIMEOUT_SECONDS


def test_external_request_timeout_env_override(monkeypatch):
    monkeypatch.setenv("EXTERNAL_REQUEST_TIMEOUT_SECONDS", " 15 ")  # whitespace-tolerant

    assert external_request_timeout_seconds() == 15


@pytest.mark.parametrize("value", ["abc", "0", "-5", "", "3.5"])
def test_external_request_timeout_invalid_or_nonpositive_falls_back(monkeypatch, value):
    monkeypatch.setenv("EXTERNAL_REQUEST_TIMEOUT_SECONDS", value)

    assert external_request_timeout_seconds() == DEFAULT_EXTERNAL_REQUEST_TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# get_retriever(): the default/overridden timeout reaches OpenAIEmbeddings
# ---------------------------------------------------------------------------


def test_get_retriever_passes_default_timeout_to_embeddings(monkeypatch):
    monkeypatch.delenv("EXTERNAL_REQUEST_TIMEOUT_SECONDS", raising=False)
    calls = _patch_embeddings(monkeypatch)
    monkeypatch.setattr(ingestion, "Chroma", _FakeVectorstore)

    retriever = ingestion.get_retriever()

    # Embeddings constructed exactly once, with the default timeout.
    assert len(calls) == 1
    assert calls[0]["timeout"] == DEFAULT_EXTERNAL_REQUEST_TIMEOUT_SECONDS
    # The fake seam was used (no real client / network), and k=3 is preserved.
    assert retriever == {"retriever_search_kwargs": {"k": 3}}


def test_get_retriever_respects_env_override(monkeypatch):
    monkeypatch.setenv("EXTERNAL_REQUEST_TIMEOUT_SECONDS", "15")
    calls = _patch_embeddings(monkeypatch)
    monkeypatch.setattr(ingestion, "Chroma", _FakeVectorstore)

    ingestion.get_retriever()

    assert calls[0]["timeout"] == 15


@pytest.mark.parametrize("value", ["abc", "0", "-5", ""])
def test_get_retriever_invalid_timeout_falls_back_to_default(monkeypatch, value):
    monkeypatch.setenv("EXTERNAL_REQUEST_TIMEOUT_SECONDS", value)
    calls = _patch_embeddings(monkeypatch)
    monkeypatch.setattr(ingestion, "Chroma", _FakeVectorstore)

    ingestion.get_retriever()

    assert calls[0]["timeout"] == DEFAULT_EXTERNAL_REQUEST_TIMEOUT_SECONDS


# ---------------------------------------------------------------------------
# build_vectorstore(): the timeout also reaches the ingestion-time embeddings
# ---------------------------------------------------------------------------


def test_build_vectorstore_passes_timeout_to_embeddings(monkeypatch):
    monkeypatch.delenv("EXTERNAL_REQUEST_TIMEOUT_SECONDS", raising=False)
    calls = _patch_embeddings(monkeypatch)

    # Avoid real corpus IO / chunking; provide one chunk with the source key
    # _chunk_ids requires.
    fake_chunk = Document(page_content="x", metadata={"source": "s"})
    monkeypatch.setattr(ingestion, "load_documents", lambda: [fake_chunk])
    monkeypatch.setattr(ingestion, "split_documents", lambda docs: list(docs))

    from_documents_calls = []

    class _FakeChroma:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def delete_collection(self):
            return None

        @staticmethod
        def from_documents(**kwargs):
            from_documents_calls.append(kwargs)
            return "fake-vectorstore"

    monkeypatch.setattr(ingestion, "Chroma", _FakeChroma)

    result = ingestion.build_vectorstore()

    assert result == "fake-vectorstore"
    # The ingestion-time embeddings construction carries the timeout.
    assert len(calls) == 1
    assert calls[0]["timeout"] == DEFAULT_EXTERNAL_REQUEST_TIMEOUT_SECONDS
    # from_documents was reached via the fake (no real vector store / network).
    assert len(from_documents_calls) == 1
