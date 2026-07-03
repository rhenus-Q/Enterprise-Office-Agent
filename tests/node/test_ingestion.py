"""
Producer-side contract tests for enterprise_rag/ingestion.py.

These assert the REAL metadata, chunk ids, splitting, and rebuild behavior the
ingestion code produces — not manually built Documents tested through downstream
consumers. Everything is mocked or uses temporary directories: OpenAIEmbeddings
and Chroma are patched at the module seam, and CORPUS_DIR is redirected to a
tmp_path fixture, so no real embeddings/vector-store client is built, the real
`chroma_db` is never touched, and the real corpus is never read or modified. No
network and no API keys.
"""

import importlib

from langchain_core.documents import Document

# Resolve the real module object for monkeypatching its globals/imported names.
ingestion = importlib.import_module("enterprise_rag.ingestion")

_SOURCE_PREFIX = "enterprise_rag/data/acmecorp_internal_docs"


# ---------------------------------------------------------------------------
# Markdown H1 / title extraction (and fallback)
# ---------------------------------------------------------------------------


def test_extract_title_returns_first_h1():
    assert (
        ingestion._extract_title("# VPN Access Policy\n\nbody", "fallback") == "VPN Access Policy"
    )


def test_extract_title_first_h1_wins_over_later_headings():
    assert ingestion._extract_title("# First\n## sub\n# Second", "fallback") == "First"


def test_extract_title_strips_surrounding_whitespace():
    assert ingestion._extract_title("#   Spaced Title   \nbody", "fallback") == "Spaced Title"


def test_extract_title_ignores_h2_and_uses_fallback():
    # "## ..." is not an H1 ("# " prefix), so the fallback is returned.
    assert ingestion._extract_title("## Not An H1\ntext", "the-stem") == "the-stem"


def test_extract_title_uses_fallback_when_no_heading():
    assert ingestion._extract_title("no heading anywhere\njust text", "the-stem") == "the-stem"


# ---------------------------------------------------------------------------
# load_documents: real provenance metadata per document (temp corpus)
# ---------------------------------------------------------------------------


def test_load_documents_produces_full_provenance_metadata(monkeypatch, tmp_path):
    # A file whose name is in DOCUMENT_CATEGORIES + a valid H1.
    (tmp_path / "vpn_policy.md").write_text(
        "# VPN Access Policy\n\nUse the corporate VPN.", encoding="utf-8"
    )
    monkeypatch.setattr(ingestion, "CORPUS_DIR", tmp_path)

    (doc,) = ingestion.load_documents()

    assert doc.page_content == "# VPN Access Policy\n\nUse the corporate VPN."
    assert doc.metadata == {
        "source": f"{_SOURCE_PREFIX}/vpn_policy.md",  # repo-relative citation key
        "title": "VPN Access Policy",  # from the H1
        "source_type": "local_corpus",  # distinguishes from the web supplement
        "document_category": "it_security",  # from DOCUMENT_CATEGORIES
    }


def test_load_documents_title_falls_back_to_stem_and_category_to_default(monkeypatch, tmp_path):
    # A file with no H1 and a name NOT in DOCUMENT_CATEGORIES.
    (tmp_path / "misc_notes.md").write_text("no heading here\nbody text", encoding="utf-8")
    monkeypatch.setattr(ingestion, "CORPUS_DIR", tmp_path)

    (doc,) = ingestion.load_documents()

    assert doc.metadata["title"] == "misc_notes"  # fallback = path.stem
    assert doc.metadata["document_category"] == "internal_document"  # unlisted → default
    assert doc.metadata["source_type"] == "local_corpus"
    assert doc.metadata["source"] == f"{_SOURCE_PREFIX}/misc_notes.md"


def test_load_documents_is_one_per_file_sorted_by_name(monkeypatch, tmp_path):
    (tmp_path / "b_doc.md").write_text("# Bravo", encoding="utf-8")
    (tmp_path / "a_doc.md").write_text("# Alpha", encoding="utf-8")
    monkeypatch.setattr(ingestion, "CORPUS_DIR", tmp_path)

    docs = ingestion.load_documents()

    # sorted(CORPUS_DIR.glob(...)) → deterministic filename order, one Document each.
    assert [d.metadata["title"] for d in docs] == ["Alpha", "Bravo"]


# ---------------------------------------------------------------------------
# Deterministic splitting + metadata propagation
# ---------------------------------------------------------------------------


def test_split_documents_is_deterministic_and_copies_metadata():
    metadata = {
        "source": f"{_SOURCE_PREFIX}/long.md",
        "title": "Long Doc",
        "source_type": "local_corpus",
        "document_category": "hr",
    }
    doc = Document(page_content="paragraph. " + ("word " * 400), metadata=metadata)

    first = ingestion.split_documents([doc])
    second = ingestion.split_documents([doc])

    assert len(first) > 1  # the 2000+ char doc actually splits at chunk_size=1000
    assert [c.page_content for c in first] == [c.page_content for c in second]  # deterministic
    for chunk in first:
        assert chunk.metadata == metadata  # provenance copied to every chunk


# ---------------------------------------------------------------------------
# Deterministic, collision-free, per-source chunk ids
# ---------------------------------------------------------------------------


def test_chunk_ids_are_deterministic_and_per_source():
    splits = [
        Document(page_content="a1", metadata={"source": "docA"}),
        Document(page_content="a2", metadata={"source": "docA"}),
        Document(page_content="b1", metadata={"source": "docB"}),
    ]

    ids1 = ingestion._chunk_ids(splits)
    ids2 = ingestion._chunk_ids(splits)

    assert ids1 == ["docA::chunk-0", "docA::chunk-1", "docB::chunk-0"]  # per-source counter
    assert ids1 == ids2  # stable across repeated runs
    assert len(set(ids1)) == len(ids1)  # no collisions


def test_chunk_ids_do_not_collide_within_one_source():
    splits = [Document(page_content=str(i), metadata={"source": "s"}) for i in range(6)]

    ids = ingestion._chunk_ids(splits)

    assert ids == [f"s::chunk-{i}" for i in range(6)]
    assert len(set(ids)) == 6


# ---------------------------------------------------------------------------
# build_vectorstore: reset-before-rebuild + idempotent deterministic ids
# ---------------------------------------------------------------------------


def _patch_build_seams(monkeypatch, events):
    """Patch embeddings + corpus loading + Chroma so build_vectorstore performs
    no real network / file / vector-store work; record the Chroma events."""

    monkeypatch.setattr(ingestion, "OpenAIEmbeddings", lambda **kwargs: object())
    chunks = [
        Document(page_content="one", metadata={"source": "s"}),
        Document(page_content="two", metadata={"source": "s"}),
    ]
    monkeypatch.setattr(ingestion, "load_documents", lambda: list(chunks))
    monkeypatch.setattr(ingestion, "split_documents", lambda docs: list(docs))

    class _FakeChroma:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def delete_collection(self):
            events.append(("delete", self.kwargs.get("collection_name")))

        @staticmethod
        def from_documents(**kwargs):
            events.append(("from_documents", kwargs.get("collection_name"), kwargs.get("ids")))
            return "fake-vectorstore"

    monkeypatch.setattr(ingestion, "Chroma", _FakeChroma)


def test_build_vectorstore_resets_collection_before_rebuild(monkeypatch):
    events = []
    _patch_build_seams(monkeypatch, events)

    result = ingestion.build_vectorstore()

    assert result == "fake-vectorstore"
    # The existing collection is dropped BEFORE re-indexing (idempotent reset).
    assert [e[0] for e in events] == ["delete", "from_documents"]
    # Same collection dropped and rebuilt.
    assert events[0][1] == ingestion.COLLECTION_NAME
    assert events[1][1] == ingestion.COLLECTION_NAME
    # Deterministic ids are passed so a rerun replaces chunks instead of appending.
    assert events[1][2] == ["s::chunk-0", "s::chunk-1"]


def test_build_vectorstore_is_idempotent_across_runs(monkeypatch):
    events = []
    _patch_build_seams(monkeypatch, events)

    ingestion.build_vectorstore()
    ingestion.build_vectorstore()

    from_documents_ids = [e[2] for e in events if e[0] == "from_documents"]
    assert len(from_documents_ids) == 2
    assert from_documents_ids[0] == from_documents_ids[1]  # same ids every run
