"""
Tests for the engine's lightweight observability (graph/engine.py):
run_id generation/preservation, node-path and timing collection, total
duration, and the optional metadata-only trace JSON (AnswerOptions.trace_path).

Tracing must be additive: the same final state as app.invoke(), no behavior
change, and no document page_content / raw state in the trace file.

All external seams are mocked -- no API keys or network required.
"""

import importlib
import json
from types import SimpleNamespace

from langchain_core.documents import Document

import graph.graph as graph_module
from graph.consts import RETRIEVE
from graph.engine import AnswerOptions, answer_question, build_trace

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
    assert payload["question"] == "How do I request VPN access?"
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
