"""
Tests for the engine's lightweight observability (graph/engine.py):
run_id generation/preservation, node-path and timing collection, total
duration, and the optional limited trace JSON (AnswerOptions.trace_path).

Tracing must be additive: the same final state as app.invoke(), no behavior
change, and no document page_content / raw state in the trace file.

All external seams are mocked -- no API keys or network required.
"""

import hashlib
import importlib
import json
from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

import enterprise_rag.graph.graph as graph_module
from enterprise_rag.graph.consts import RETRIEVE
from enterprise_rag.graph.engine import (
    QUESTION_PREVIEW_MAX_CHARS,
    AnswerOptions,
    AnswerResult,
    _redact_secrets,
    answer_question,
    build_trace,
)
from enterprise_rag.graph.formatting import source_lines

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
    assert payload["input_redacted"] is False  # a normal question is not redacted
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
# Input-level secret redaction (redacted before the question enters the graph)
# ---------------------------------------------------------------------------

# Secret-bearing questions and the raw fragment each must never leak.
_SECRET_QUESTIONS = [
    ("my key is sk-ABC123def456GHI789", "sk-ABC123def456GHI789"),  # OpenAI-style
    ("anthropic sk-ant-API03-xyz_abc-123", "sk-ant-API03-xyz_abc-123"),  # Anthropic-style
    ("token ghp_0123456789abcdefABCDEF", "ghp_0123456789abcdefABCDEF"),  # GitHub classic
    ("github_pat_11ABCDEFG0_secrettokenvalue", "github_pat_11ABCDEFG0_secrettokenvalue"),  # PAT
    ("api_key=supersecretvalue", "supersecretvalue"),  # generic key=value
    ("password=hunter2", "hunter2"),  # generic key=value
]


def test_redact_secrets_replaces_secret_like_values():
    for question, leaked in _SECRET_QUESTIONS:
        redacted = _redact_secrets(question)
        assert "[REDACTED]" in redacted, question
        assert leaked not in redacted, question


# Expanded coverage (second hardening batch). Each row is
# (question, leaked_fragment_that_must_be_gone, substring_that_must_remain_or_None).
_EXPANDED_SECRET_CASES = [
    # AWS access-key ids.
    pytest.param(
        "rotate AKIAIOSFODNN7EXAMPLE before monday",
        "AKIAIOSFODNN7EXAMPLE",
        "rotate",
        id="aws-akia",
    ),
    pytest.param(
        "temp creds ASIAIOSFODNN7EXAMPLE here",
        "ASIAIOSFODNN7EXAMPLE",
        "temp creds",
        id="aws-asia",
    ),
    # JWT (three dot-separated segments).
    pytest.param(
        "my jwt eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signaturevalue ok",
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.signaturevalue",
        "my jwt",
        id="jwt",
    ),
    # Bearer tokens (label preserved).
    pytest.param(
        "Authorization: Bearer abcdef1234567890",
        "abcdef1234567890",
        "Authorization: Bearer",
        id="bearer-labeled",
    ),
    pytest.param("Bearer abcdef1234567890", "abcdef1234567890", "Bearer", id="bearer-bare"),
    # Slack tokens.
    pytest.param(
        "slack xoxb-123456789012-123456789012-abcdefghijklmnopqrstuvwxyz",
        "xoxb-123456789012-123456789012-abcdefghijklmnopqrstuvwxyz",
        "slack",
        id="slack-xoxb",
    ),
    pytest.param(
        "key xoxp-123456789012-123456789012-123456789012-abcdef",
        "xoxp-123456789012-123456789012-123456789012-abcdef",
        None,
        id="slack-xoxp",
    ),
    # Google / GCP API key.
    pytest.param(
        "gcp AIzaSyD_example_value_with_expected_length end",
        "AIzaSyD_example_value_with_expected_length",
        "gcp",
        id="google-aiza",
    ),
    # Colon-separated generic secrets.
    pytest.param("password: hunter2", "hunter2", "password", id="colon-password"),
    pytest.param("token: abcdef123456", "abcdef123456", "token", id="colon-token"),
    pytest.param("api_key: secret-value", "secret-value", "api_key", id="colon-api_key"),
    pytest.param("apikey: secret-value", "secret-value", "apikey", id="colon-apikey"),
    pytest.param("secret: secret-value", "secret-value", "secret", id="colon-secret"),
    # Credentials in connection-string URIs (password only; rest preserved).
    pytest.param(
        "postgres://user:password@db.example.com/database",
        "password",
        "postgres://user:",
        id="uri-postgres",
    ),
    pytest.param(
        "postgresql://user:password@db.example.com/database",
        "password",
        "db.example.com/database",
        id="uri-postgresql",
    ),
    pytest.param(
        "mysql://user:password@db.example.com/database",
        "password",
        "mysql://user:",
        id="uri-mysql",
    ),
    pytest.param(
        "mongodb://user:password@db.example.com/database",
        "password",
        "mongodb://user:",
        id="uri-mongodb",
    ),
    pytest.param(
        "mongodb+srv://user:password@cluster.example.com/database",
        "password",
        "mongodb+srv://user:",
        id="uri-mongodb-srv",
    ),
    pytest.param(
        "redis://user:password@redis.example.com/0",
        "password",
        "redis.example.com/0",
        id="uri-redis",
    ),
]


@pytest.mark.parametrize("question, leaked, must_remain", _EXPANDED_SECRET_CASES)
def test_expanded_redaction_positive_cases(question, leaked, must_remain):
    """Each newly supported secret format is scrubbed to [REDACTED]; harmless
    surrounding label/scheme text is preserved where applicable."""

    redacted = _redact_secrets(question)

    assert "[REDACTED]" in redacted, question
    assert leaked not in redacted, question
    if must_remain is not None:
        assert must_remain in redacted, question


# Boundary / negative cases that must NOT be redacted at all (over-redaction guard).
_NON_SECRET_CASES = [
    pytest.param("please send me the token for the standup meeting", id="prose-token"),
    pytest.param("the constant THISISNOTANAWSKEYVALUE is fine", id="uppercase-not-aws"),
    pytest.param(
        "header eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ4In0 has only two parts", id="jwt-2-segments"
    ),
    pytest.param("visit https://user.example.com/path for the docs", id="url-no-password"),
    pytest.param("xoxo hugs to the whole team", id="xox-not-slack"),
    pytest.param("how do I reset the password:", id="colon-empty-value"),
]


@pytest.mark.parametrize("question", _NON_SECRET_CASES)
def test_expanded_redaction_does_not_over_redact(question):
    """Ordinary prose, non-AWS uppercase ids, 2-segment eyJ strings, password-less
    URLs, non-Slack xox words, and empty colon values are left untouched."""

    assert _redact_secrets(question) == question


def test_redaction_does_not_consume_following_lines():
    """A secret on one line is redacted without swallowing the next line."""

    text = "password: hunter2\nkeep this second line fully intact"
    redacted = _redact_secrets(text)

    assert "hunter2" not in redacted
    assert "[REDACTED]" in redacted
    assert "keep this second line fully intact" in redacted
    assert redacted.count("\n") == text.count("\n")  # newline structure preserved


def test_answer_question_seeds_redacted_new_format_secret(monkeypatch):
    """Integration: a newly supported secret shape (AWS key) is redacted before the
    graph is invoked, and the original input hash is unchanged."""

    captured = {}

    class _CapturingApp:
        def invoke(self, state):
            captured["question"] = state["question"]
            return {**state, "generation": "A"}

    monkeypatch.setattr(graph_module, "app", _CapturingApp())
    question = "rotate AKIAIOSFODNN7EXAMPLE before monday"

    result = answer_question(question)

    # The graph, the result, and raw_state all see only the redacted question.
    assert "AKIAIOSFODNN7EXAMPLE" not in captured["question"]
    assert "AKIAIOSFODNN7EXAMPLE" not in result.question
    assert "AKIAIOSFODNN7EXAMPLE" not in result.raw_state["question"]
    assert result.input_redacted is True
    # Hashing is unchanged: still over the ORIGINAL input.
    assert result.question_sha256 == hashlib.sha256(question.encode()).hexdigest()


def test_non_secret_question_passes_through_unchanged(monkeypatch):
    _install_fake_app(monkeypatch)

    result = answer_question("How do I request VPN access?")

    # Identical to the original: no redaction happened.
    assert result.question == "How do I request VPN access?"
    assert result.input_redacted is False
    assert result.raw_state["question"] == "How do I request VPN access?"
    assert result.question_sha256 == hashlib.sha256(b"How do I request VPN access?").hexdigest()


def test_input_redaction_hashes_original_and_sets_flag(monkeypatch):
    _install_fake_app(monkeypatch)
    question = "use api_key=sk-LIVE-SECRET please"

    result = answer_question(question)

    # The stored question is the redacted runtime question; the raw secret is gone.
    assert result.input_redacted is True
    assert "sk-LIVE-SECRET" not in result.question
    assert "[REDACTED]" in result.question
    # Hash is over the ORIGINAL input, not the redacted form.
    assert result.question_sha256 == hashlib.sha256(question.encode()).hexdigest()
    assert result.question_sha256 != hashlib.sha256(result.question.encode()).hexdigest()


def test_graph_receives_redacted_question_not_raw_secret(monkeypatch):
    # The compiled graph (and thus retriever/router/generator/graders) must see
    # the redacted question, never the raw secret.
    captured = {}

    class _CapturingApp:
        def invoke(self, state):
            captured["question"] = state["question"]
            return {**state, "generation": "A"}

    monkeypatch.setattr(graph_module, "app", _CapturingApp())
    question = "api_key=sk-RAW " + ("x" * 200)

    result = answer_question(question)

    assert captured["question"] == _redact_secrets(question)
    assert "sk-RAW" not in captured["question"]
    # Nothing user-visible or in raw_state carries the raw secret.
    assert "sk-RAW" not in result.question
    assert "sk-RAW" not in result.raw_state["question"]


def test_trace_file_does_not_contain_a_raw_secret_question(monkeypatch, tmp_path):
    _install_fake_app(monkeypatch)
    trace_file = tmp_path / "run.json"
    question = "use api_key=sk-LIVE-SECRET-do-not-store please"

    answer_question(question, AnswerOptions(trace_path=trace_file))

    text = trace_file.read_text(encoding="utf-8")
    payload = json.loads(text)
    assert "sk-LIVE-SECRET-do-not-store" not in text
    assert "[REDACTED]" in payload["question_redacted"]
    assert payload["input_redacted"] is True
    # Hash in the trace is over the original input.
    assert payload["question_sha256"] == hashlib.sha256(question.encode()).hexdigest()


def test_trace_preview_is_truncated_to_max_chars(monkeypatch, tmp_path):
    _install_fake_app(monkeypatch)
    trace_file = tmp_path / "run.json"
    long_question = "word " * 100  # well over the preview cap

    result = answer_question(long_question, AnswerOptions(trace_path=trace_file))

    payload = json.loads(trace_file.read_text(encoding="utf-8"))
    assert len(payload["question_redacted"]) <= QUESTION_PREVIEW_MAX_CHARS
    # The hash still covers the full original text, not the truncated preview.
    assert result.question_sha256 == hashlib.sha256(long_question.encode()).hexdigest()


def test_web_search_query_is_redacted_without_changing_policy(monkeypatch):
    # A secret in the question must not reach the outbound web-search query, and
    # redaction must not flip web_search_enabled or the fallback policy.
    from enterprise_rag.graph.consts import WEBSEARCH

    web_module = importlib.import_module("enterprise_rag.graph.nodes.web_search")
    generate_module = importlib.import_module("enterprise_rag.graph.nodes.generate")

    web_calls = []

    class FakeWebTool:
        def invoke(self, payload):
            web_calls.append(payload)
            return [{"content": "web result"}]

    monkeypatch.setattr(
        graph_module,
        "get_question_router",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(datasource=WEBSEARCH)),
    )
    monkeypatch.setattr(web_module, "get_web_search_tool", lambda: FakeWebTool())
    monkeypatch.setattr(
        web_module,
        "get_retrieval_grader",
        lambda: SimpleNamespace(invoke=lambda p: SimpleNamespace(is_relevant=True)),
    )
    monkeypatch.setattr(
        generate_module,
        "generate_answer",
        lambda question, documents, retry_feedback="": "FINAL ANSWER",
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

    question = "look up api_key=sk-WEBSECRET-123 online"
    result = answer_question(
        question,
        AnswerOptions(web_search_enabled=True, web_fallback_policy="conservative"),
    )

    assert web_calls, "the web tool should have been invoked"
    for payload in web_calls:
        assert "sk-WEBSECRET-123" not in payload["query"]
        assert "[REDACTED]" in payload["query"]
    # Policy/privacy unchanged by redaction.
    assert result.web_search_enabled is True
    assert result.web_fallback_policy == "conservative"


def test_sanitized_web_source_metadata_reaches_trace_source_lines(monkeypatch):
    # A hostile web title + an unsafe-scheme URL sanitized by the web_search node
    # must reach the limited trace `sources` already cleaned: the unsafe
    # entry omitted, the title stripped of control bytes and newlines.
    web_module = importlib.import_module("enterprise_rag.graph.nodes.web_search")

    monkeypatch.setattr(
        web_module,
        "get_web_search_tool",
        lambda: SimpleNamespace(
            invoke=lambda payload: [
                {"content": "useful", "url": "https://ok.example/a", "title": "Real\nTitle\x1b[0m"},
                {"content": "payload", "url": "javascript:alert(1)", "title": "Evil"},
            ]
        ),
    )
    monkeypatch.setattr(
        web_module,
        "get_retrieval_grader",
        lambda: SimpleNamespace(invoke=lambda payload: SimpleNamespace(is_relevant=True)),
    )

    documents = web_module.web_search({"question": "Q", "documents": []})["documents"]

    # AnswerResult.sources is what build_trace serializes into the trace file.
    result = AnswerResult(
        question="Q",
        answer="A",
        stop_reason="",
        sources=source_lines(documents),
    )
    trace = build_trace(result)

    assert trace["sources"] == ["- Web search: Real Title — https://ok.example/a"]
    assert all("javascript:" not in line and "\x1b" not in line for line in trace["sources"])


# ---------------------------------------------------------------------------
# End-to-end through the real compiled graph (mocked seams): tracing is
# additive and the privacy guarantee is unchanged.
# ---------------------------------------------------------------------------


def _patch_node_seams(monkeypatch):
    retrieve_module = importlib.import_module("enterprise_rag.graph.nodes.retrieve")
    grade_module = importlib.import_module("enterprise_rag.graph.nodes.grade_documents")
    generate_module = importlib.import_module("enterprise_rag.graph.nodes.generate")
    web_module = importlib.import_module("enterprise_rag.graph.nodes.web_search")

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


# ---------------------------------------------------------------------------
# Exception contract: an unexpected mid-run error propagates unchanged
#
# answer_question() handles *expected* dependency failures at their component
# boundaries, but there is intentionally no broad catch-all around the graph
# run: an unexpected internal error must propagate to the caller unchanged,
# never be swallowed or converted into an AnswerResult. These tests lock that
# documented contract (engine docstring + structure.md §13).
# ---------------------------------------------------------------------------


class _MidStreamError(Exception):
    """Distinctive local exception type, so the assertions prove the exact
    error identity/type is preserved (not wrapped or replaced)."""


class _RaisingStreamApp:
    """Mirrors LangGraph's update stream but fails partway.

    stream() yields one {node: update} chunk per entry in `pre_updates`, then
    raises _MidStreamError — standing in for an unexpected internal error that
    surfaces while the graph is running. With an empty `pre_updates` it raises
    before yielding its first update.
    """

    def __init__(self, pre_updates):
        self.pre_updates = pre_updates

    def stream(self, state, stream_mode="updates"):
        assert stream_mode == "updates"
        for node_name, update in self.pre_updates:
            yield {node_name: update}
        raise _MidStreamError("boom mid-run")


def test_mid_stream_exception_propagates_unchanged(monkeypatch, tmp_path):
    # The app streams one valid update and then raises. The same exception type
    # must propagate out of answer_question() — not be swallowed, not become an
    # AnswerResult, not be replaced by another exception type.
    fake = _RaisingStreamApp([("retrieve", {"documents": []})])
    monkeypatch.setattr(graph_module, "app", fake)
    trace_file = tmp_path / "run.json"

    with pytest.raises(_MidStreamError) as excinfo:
        answer_question("Q", AnswerOptions(trace_path=trace_file))

    # The exact exception instance propagated (message preserved), proving it
    # was neither wrapped nor converted.
    assert str(excinfo.value) == "boom mid-run"

    # No partial trace file: the write happens only after a successful run, so
    # a failed stream leaves nothing behind.
    assert not trace_file.exists()
    assert list(tmp_path.iterdir()) == []


def test_exception_before_first_update_propagates_unchanged(monkeypatch, tmp_path):
    # The app raises before yielding any update at all. Same contract: the
    # exception propagates and no trace file is written.
    fake = _RaisingStreamApp([])
    monkeypatch.setattr(graph_module, "app", fake)
    trace_file = tmp_path / "run.json"

    with pytest.raises(_MidStreamError) as excinfo:
        answer_question("Q", AnswerOptions(trace_path=trace_file))

    assert str(excinfo.value) == "boom mid-run"
    assert not trace_file.exists()
    assert list(tmp_path.iterdir()) == []
