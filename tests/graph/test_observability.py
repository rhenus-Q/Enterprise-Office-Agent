"""
Tests for the engine's lightweight observability (graph/engine.py):
run_id generation/preservation, node-path and timing collection, total
duration, and the optional metadata-only trace JSON (AnswerOptions.trace_path).

Tracing must be additive: the same final state as app.invoke(), no behavior
change, and no document page_content / raw state in the trace file.

All external seams are mocked -- no API keys or network required.
"""

import hashlib
import importlib
import json
from types import SimpleNamespace

from langchain_core.documents import Document

import graph.graph as graph_module
from graph.consts import RETRIEVE
from graph.engine import (
    QUESTION_PREVIEW_MAX_CHARS,
    AnswerOptions,
    answer_question,
    build_trace,
    trace_safe_question,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _StreamingFakeApp:
    """Mirrors LangGraph's update stream: one chunk per completed node."""

    def __init__(self, steps):
        # steps: list of (node_name, partial_update) in execution order.
        self.steps = steps
        self.invoked_with = None

    def stream(self, state, stream_mode="updates"):
        assert stream_mode == "updates"
        self.invoked_with = state
        for node_name, update in self.steps:
            yield {node_name: update}


class _InvokeOnlyFakeApp:
    """No stream support: the engine must fall back to invoke()."""

    def invoke(self, state):
        return {**state, "generation": "A"}


_DOC_MARKER = "SECRET-PAGE-CONTENT-MARKER"


def _default_steps():
    doc = Document(
        page_content=_DOC_MARKER,
        metadata={"source": "data/vpn_policy.md", "title": "VPN Policy"},
    )
    return [
        ("retrieve", {"documents": [doc]}),
        ("grade_documents", {"documents": [doc], "web_search": False}),
        (
            "generate",
            {
                "generation": "The answer.",
                "retries": 1,
                "llm_call_count": 1,
            },
        ),
        ("clear_transient_tool_error", {}),
    ]


def _install_fake_app(monkeypatch, steps=None):
    fake = _StreamingFakeApp(_default_steps() if steps is None else steps)
    monkeypatch.setattr(graph_module, "app", fake)
    return fake


# ---------------------------------------------------------------------------
# run_id
# ---------------------------------------------------------------------------


def test_run_id_is_generated_when_not_provided(monkeypatch):
    _install_fake_app(monkeypatch)

    first = answer_question("Q")
    second = answer_question("Q")

    assert isinstance(first.run_id, str) and first.run_id
    assert isinstance(second.run_id, str) and second.run_id
    assert first.run_id != second.run_id  # fresh id per run


def test_run_id_is_preserved_when_provided(monkeypatch):
    _install_fake_app(monkeypatch)

    result = answer_question("Q", AnswerOptions(run_id="my-run-42"))

    assert result.run_id == "my-run-42"


# ---------------------------------------------------------------------------
# Node path, per-node timings, total duration
# ---------------------------------------------------------------------------


def test_node_path_records_executed_nodes_in_order(monkeypatch):
    _install_fake_app(monkeypatch)

    result = answer_question("Q")

    assert result.node_path == [
        "retrieve",
        "grade_documents",
        "generate",
        "clear_transient_tool_error",
    ]


def test_node_timings_align_with_node_path(monkeypatch):
    _install_fake_app(monkeypatch)

    result = answer_question("Q")

    assert len(result.node_timings_ms) == len(result.node_path)
    for entry, node_name in zip(result.node_timings_ms, result.node_path, strict=False):
        assert entry["node"] == node_name
        assert isinstance(entry["duration_ms"], float)
        assert entry["duration_ms"] >= 0.0


def test_total_duration_is_a_nonnegative_float(monkeypatch):
    _install_fake_app(monkeypatch)

    result = answer_question("Q")

    assert isinstance(result.total_duration_ms, float)
    assert result.total_duration_ms >= 0.0


def test_streamed_updates_reproduce_the_final_state(monkeypatch):
    # The merged update stream must yield the same answer/counters as
    # invoke() would: tracing is additive, never behavior-changing.
    _install_fake_app(monkeypatch)

    result = answer_question("Q")

    assert result.answer == "The answer."
    assert result.retries == 1
    assert result.tracked_llm_calls == 1
    assert result.stop_reason == ""
    assert result.sources == ["- Local corpus: VPN Policy"]
    assert result.raw_state["question"] == "Q"


def test_invoke_only_app_falls_back_to_empty_trace(monkeypatch):
    monkeypatch.setattr(graph_module, "app", _InvokeOnlyFakeApp())

    result = answer_question("Q")

    assert result.answer == "A"
    assert result.node_path == []
    assert result.node_timings_ms == []
    assert isinstance(result.run_id, str) and result.run_id
    assert result.total_duration_ms >= 0.0


# ---------------------------------------------------------------------------
# Trace JSON
# ---------------------------------------------------------------------------


def test_no_trace_file_is_written_by_default(monkeypatch, tmp_path):
    _install_fake_app(monkeypatch)

    answer_question("Q")

    assert list(tmp_path.iterdir()) == []


def test_trace_path_writes_a_json_file(monkeypatch, tmp_path):
    _install_fake_app(monkeypatch)
    trace_file = tmp_path / "traces" / "run.json"  # parent dir is created too

    answer_question("Q", AnswerOptions(trace_path=trace_file))

    assert trace_file.exists()
    payload = json.loads(trace_file.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)


def test_trace_json_contains_the_expected_metadata(monkeypatch, tmp_path):
    _install_fake_app(monkeypatch)
    trace_file = tmp_path / "run.json"

    result = answer_question(
        "How do I request VPN access?",
        AnswerOptions(run_id="trace-run-1", trace_path=str(trace_file)),
    )

    payload = json.loads(trace_file.read_text(encoding="utf-8"))

    assert payload["run_id"] == "trace-run-1"
    # The raw question is never stored; only a redacted preview + a hash.
    assert "question" not in payload
    assert payload["question_redacted"] == "How do I request VPN access?"
    assert payload["question_sha256"] == hashlib.sha256(b"How do I request VPN access?").hexdigest()
    assert payload["node_path"] == result.node_path
    assert payload["total_duration_ms"] == result.total_duration_ms
    assert payload["node_timings_ms"] == result.node_timings_ms
    assert payload["stop_reason"] == ""
    assert payload["counters"] == {
        "retries": 1,
        "tracked_llm_calls": 1,
        "web_search_count": 0,
        "web_result_grading_count": 0,
    }
    assert payload["web_search_enabled"] is True
    assert payload["web_fallback_policy"] == result.web_fallback_policy
    assert payload["sources"] == ["- Local corpus: VPN Policy"]
    assert "generated_at" in payload


def test_trace_json_never_contains_document_content_or_raw_state(monkeypatch, tmp_path):
    _install_fake_app(monkeypatch)
    trace_file = tmp_path / "run.json"

    answer_question("Q", AnswerOptions(trace_path=trace_file))

    text = trace_file.read_text(encoding="utf-8")
    payload = json.loads(text)

    assert _DOC_MARKER not in text  # no raw page_content
    assert "raw_state" not in payload
    assert "documents" not in payload


def test_build_trace_matches_answer_result(monkeypatch):
    _install_fake_app(monkeypatch)

    result = answer_question("Q", AnswerOptions(run_id="r1"))
    payload = build_trace(result)

    assert payload["run_id"] == "r1"
    assert payload["node_path"] == result.node_path
    assert payload["counters"]["retries"] == result.retries
    assert payload["sources"] == result.sources


def test_failed_trace_write_does_not_lose_the_answer(monkeypatch, tmp_path, capsys):
    _install_fake_app(monkeypatch)
    # A directory at the target path makes the write fail.
    bad_path = tmp_path / "already-a-directory"
    bad_path.mkdir()

    result = answer_question("Q", AnswerOptions(trace_path=bad_path))

    assert result.answer == "The answer."
    assert "---TRACE WRITE FAILED" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Trace-safe question redaction
# ---------------------------------------------------------------------------


def test_trace_safe_question_hash_is_stable_for_same_input():
    expected = hashlib.sha256(b"What is the VPN policy?").hexdigest()

    first = trace_safe_question("What is the VPN policy?")
    second = trace_safe_question("What is the VPN policy?")

    assert first["question_sha256"] == second["question_sha256"] == expected
    # Different text -> different hash.
    assert trace_safe_question("Other question")["question_sha256"] != expected


def test_trace_safe_question_truncates_long_questions():
    long_question = "word " * 100  # well over the preview cap

    meta = trace_safe_question(long_question)

    assert len(meta["question_redacted"]) <= QUESTION_PREVIEW_MAX_CHARS
    assert meta["question_redacted"] == long_question[:QUESTION_PREVIEW_MAX_CHARS]
    # The hash is over the ORIGINAL full text, not the truncated preview.
    assert meta["question_sha256"] == hashlib.sha256(long_question.encode()).hexdigest()


def test_trace_safe_question_redacts_secret_like_values():
    secrets = [
        "my key is sk-ABC123def456GHI789",  # OpenAI-style
        "anthropic sk-ant-API03-xyz_abc-123",  # Anthropic-style
        "token ghp_0123456789abcdefABCDEF",  # GitHub classic
        "github_pat_11ABCDEFG0_secrettokenvalue",  # GitHub fine-grained PAT
        "api_key=supersecretvalue",  # generic key=value
        "password=hunter2",  # generic key=value
    ]
    leaked_fragments = [
        "sk-ABC123def456GHI789",
        "sk-ant-API03-xyz_abc-123",
        "ghp_0123456789abcdefABCDEF",
        "github_pat_11ABCDEFG0_secrettokenvalue",
        "supersecretvalue",
        "hunter2",
    ]

    for question, leaked in zip(secrets, leaked_fragments, strict=True):
        preview = trace_safe_question(question)["question_redacted"]
        assert "[REDACTED]" in preview, question
        assert leaked not in preview, question


def test_trace_file_does_not_contain_a_raw_secret_question(monkeypatch, tmp_path):
    _install_fake_app(monkeypatch)
    trace_file = tmp_path / "run.json"
    question = "use api_key=sk-LIVE-SECRET-do-not-store please"

    answer_question(question, AnswerOptions(trace_path=trace_file))

    text = trace_file.read_text(encoding="utf-8")
    payload = json.loads(text)
    assert "sk-LIVE-SECRET-do-not-store" not in text
    assert "[REDACTED]" in payload["question_redacted"]
    assert payload["question_sha256"] == hashlib.sha256(question.encode()).hexdigest()


def test_runtime_receives_original_question_not_the_redacted_preview(monkeypatch, tmp_path):
    # A long, secret-bearing question must reach the graph verbatim; only the
    # on-disk trace is redacted/truncated.
    captured = {}

    class _CapturingApp:
        def invoke(self, state):
            captured["question"] = state["question"]
            return {**state, "generation": "A"}

    monkeypatch.setattr(graph_module, "app", _CapturingApp())
    trace_file = tmp_path / "run.json"
    question = "api_key=sk-RAW " + ("x" * 200)

    result = answer_question(question, AnswerOptions(trace_path=trace_file))

    # Runtime answering used the full, unredacted question.
    assert captured["question"] == question
    assert result.question == question
    assert result.raw_state["question"] == question
    # The persisted trace did not.
    payload = json.loads(trace_file.read_text(encoding="utf-8"))
    assert payload["question_redacted"] != question
    assert "sk-RAW" not in trace_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# End-to-end through the real compiled graph (mocked seams): tracing is
# additive and the privacy guarantee is unchanged.
# ---------------------------------------------------------------------------


def _patch_node_seams(monkeypatch):
    retrieve_module = importlib.import_module("graph.nodes.retrieve")
    grade_module = importlib.import_module("graph.nodes.grade_documents")
    generate_module = importlib.import_module("graph.nodes.generate")
    web_module = importlib.import_module("graph.nodes.web_search")

    monkeypatch.setattr(
        retrieve_module,
        "get_node_retriever",
        lambda: SimpleNamespace(
            invoke=lambda q: [Document(page_content="rel", metadata={"title": "Doc"})]
        ),
    )
    monkeypatch.setattr(
        grade_module,
        "get_retrieval_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_relevant=True)),
    )
    monkeypatch.setattr(
        generate_module,
        "generate_answer",
        lambda question, documents, retry_feedback="": "FINAL ANSWER",
    )

    web_calls = []

    class FakeWebTool:
        def invoke(self, payload):
            web_calls.append(payload)
            return [{"content": "web result"}]

    monkeypatch.setattr(web_module, "get_web_search_tool", lambda: FakeWebTool())
    return web_calls


def _patch_router_and_graders(monkeypatch):
    monkeypatch.setattr(
        graph_module,
        "get_question_router",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(datasource=RETRIEVE)),
    )
    monkeypatch.setattr(
        graph_module,
        "get_hallucination_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_grounded=True)),
    )
    monkeypatch.setattr(
        graph_module,
        "get_answer_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(answers_question=True)),
    )


def test_real_graph_run_collects_node_path_and_keeps_behavior(monkeypatch, tmp_path):
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)
    monkeypatch.delenv("WEB_SEARCH_ENABLED", raising=False)
    _patch_router_and_graders(monkeypatch)
    web_calls = _patch_node_seams(monkeypatch)
    trace_file = tmp_path / "run.json"

    result = answer_question("Q", AnswerOptions(trace_path=trace_file))

    # Behavior identical to the pre-observability engine.
    assert result.answer == "FINAL ANSWER"
    assert result.stop_reason == ""
    assert result.retries == 1
    assert web_calls == []

    # Real LangGraph stream: the clean local path in order.
    assert result.node_path == [
        "retrieve",
        "grade_documents",
        "generate",
        "clear_transient_tool_error",
    ]
    assert len(result.node_timings_ms) == len(result.node_path)
    assert result.total_duration_ms >= 0.0

    payload = json.loads(trace_file.read_text(encoding="utf-8"))
    assert payload["node_path"] == result.node_path
    assert "rel" not in payload["sources"]  # citation labels only


def test_real_graph_privacy_run_traces_without_web(monkeypatch):
    # WEB_SEARCH_ENABLED=false still guarantees zero web searches; the trace
    # simply records the local path.
    monkeypatch.delenv("WEB_FALLBACK_POLICY", raising=False)
    _patch_router_and_graders(monkeypatch)
    web_calls = _patch_node_seams(monkeypatch)

    result = answer_question("Q", AnswerOptions(web_search_enabled=False))

    assert web_calls == []
    assert result.web_search_count == 0
    assert result.node_path[0] == "retrieve"
    assert "websearch" not in result.node_path
