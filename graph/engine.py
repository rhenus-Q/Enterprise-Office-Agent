"""
engine.py

Canonical programmatic entry point for the Agentic RAG system.

`answer_question()` is the one function every caller — the CLI (main.py),
the eval harness (evals/run_eval.py), tests, and future workflow automation —
uses to run a question through the compiled graph. It owns the two pieces of
logic that used to be duplicated per caller:

- State seeding (`seed_state()`): the full GraphState is initialized in one
  place, so nodes and conditional functions never read a missing key and a
  new state field only needs one update.
- Per-run config resolution: WEB_SEARCH_ENABLED and WEB_FALLBACK_POLICY are
  resolved once at run start (explicit per-run options win over the
  environment defaults) and written into state, so graph decisions never
  read os.environ mid-run and callers can vary both per run without
  mutating the environment.

Lightweight observability (additive, never behavior-changing): every run
gets a run_id (caller-provided or generated), the executed node path and
per-node wall-clock timings are collected by streaming the compiled graph's
node updates, and an optional metadata-only trace JSON can be written via
AnswerOptions.trace_path. Trace data is safe by construction: it contains
node names, timings, counters, flags, and citation lines — never document
page_content, prompts, raw graph state, or secrets.

Import is side-effect-free in the repo's sense: no external client is
constructed (graph.graph builds clients lazily), so importing this module
needs no API keys and no network.
"""

import hashlib
import json
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import graph.graph as graph_runtime
from graph import config
from graph.config import normalize_web_fallback_policy
from graph.formatting import source_lines
from graph.state import GraphState


@dataclass
class AnswerOptions:
    """
    Per-run overrides for `answer_question()`.

    Every field defaults to None, meaning "use the environment default"
    (WEB_SEARCH_ENABLED / WEB_FALLBACK_POLICY via graph/config.py). An
    explicit value wins over the environment for this run only — nothing is
    written back to os.environ.

    run_id: caller-provided run identifier, preserved verbatim; when None a
    fresh one is generated. trace_path: when set, a metadata-only trace JSON
    (see build_trace) is written there after the run; default None = no file.
    """

    web_search_enabled: bool | None = None
    web_fallback_policy: str | None = None
    run_id: str | None = None
    trace_path: str | Path | None = None


@dataclass
class AnswerResult:
    """
    Structured outcome of one graph run.

    `answer` is the raw generation (no caveats, no sources section); callers
    that need the user-facing rendering format `raw_state` with
    graph.formatting.format_answer. `tracked_llm_calls` mirrors the budgeted
    operational counter (generations, query rewrites, web-result grades) —
    NOT total LLM usage: router and grader calls are not individually
    tracked. `web_search_enabled` / `web_fallback_policy` are the values the
    run actually used, after per-run options and environment defaults were
    resolved.

    Input redaction: `question` is the redacted runtime question that the
    graph actually executed — secret-like values are replaced with
    [REDACTED] before the question enters GraphState, so the original raw
    input is never stored here or in `raw_state`. `question_sha256` is the
    SHA-256 of the ORIGINAL (pre-redaction) input, so identical inputs still
    correlate across runs; `input_redacted` is True when redaction changed
    the input.

    Observability fields: `run_id` is always set (caller-provided or
    generated). `node_path` is the executed node sequence in order (repeats
    on retries); `node_timings_ms` is one `{"node", "duration_ms"}` entry per
    step, aligned with `node_path` — wall-clock time between node
    completions, so conditional-edge evaluation is attributed to the
    adjacent step (approximate by design). Both are empty when the graph
    object does not support streaming. `total_duration_ms` covers the whole
    graph run.
    """

    question: str
    answer: str
    stop_reason: str
    sources: list[str] = field(default_factory=list)
    retries: int = 0
    tracked_llm_calls: int = 0
    web_search_count: int = 0
    web_result_grading_count: int = 0
    web_search_enabled: bool = True
    web_fallback_policy: str = config.WEB_FALLBACK_CONSERVATIVE
    raw_state: dict[str, Any] = field(default_factory=dict)
    run_id: str | None = None
    node_path: list[str] = field(default_factory=list)
    node_timings_ms: list[dict[str, Any]] = field(default_factory=list)
    total_duration_ms: float = 0.0
    question_sha256: str = ""
    input_redacted: bool = False


def seed_state(
    question: str,
    *,
    web_search_enabled: bool | None = None,
    web_fallback_policy: str | None = None,
) -> GraphState:
    """
    Build the full initial GraphState for one run.

    The single source of truth for state seeding (formerly duplicated in
    main.py, evals/run_eval.py, and test helpers). None means "resolve from
    the environment"; explicit values are used as-is (the policy is
    normalized, with invalid values falling back to conservative).
    """

    if web_search_enabled is None:
        web_search_enabled = config.web_search_enabled()

    if web_fallback_policy is None:
        web_fallback_policy = config.web_fallback_policy()
    else:
        web_fallback_policy = normalize_web_fallback_policy(web_fallback_policy)

    return {
        "question": question,
        "documents": [],
        "generation": "",
        "web_search": False,
        "web_search_enabled": bool(web_search_enabled),
        "web_fallback_policy": web_fallback_policy,
        "retries": 0,
        "stop_reason": "",
        "insufficient_context": False,
        "retry_feedback": "",
        "search_query": "",
        "llm_call_count": 0,
        "web_search_count": 0,
        "web_result_grading_count": 0,
    }


def _run_graph_with_trace(
    app: Any, initial_state: GraphState
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]]]:
    """
    Execute the compiled graph, collecting the node path and per-step
    timings as a side effect.

    Uses LangGraph's update stream (`stream_mode="updates"`): one chunk per
    completed node, holding that node's partial state update. GraphState has
    no custom reducers — every channel is a plain last-value overwrite — so
    merging the updates onto the seeded state reproduces `app.invoke()`
    exactly; tracing is purely additive and cannot change routing, retries,
    stop_reason, or any node behavior. Objects without `stream` (e.g.
    minimal test fakes) fall back to `invoke()` with an empty trace.
    """

    stream = getattr(app, "stream", None)
    if stream is None:
        return app.invoke(initial_state), [], []

    final_state: dict[str, Any] = dict(initial_state)
    node_path: list[str] = []
    node_timings: list[dict[str, Any]] = []

    previous = time.perf_counter()
    for chunk in stream(initial_state, stream_mode="updates"):
        now = time.perf_counter()
        for node_name, update in chunk.items():
            node_path.append(node_name)
            node_timings.append(
                {"node": node_name, "duration_ms": round((now - previous) * 1000.0, 2)}
            )
            if isinstance(update, dict):
                final_state.update(update)
        previous = now

    return final_state, node_path, node_timings


# Maximum length of the redacted question preview stored in trace output.
QUESTION_PREVIEW_MAX_CHARS = 80

# Obvious secret-like values scrubbed from the question before it is previewed
# in trace output. Each entry is (pattern, replacement). Prefix-style keys are
# matched before the generic key=value form so e.g. `api_key=sk-...` is fully
# redacted regardless of which rule fires first. This is best-effort hygiene for
# debug artifacts, not a guarantee that every possible secret shape is caught.
_SECRET_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"sk-ant-[A-Za-z0-9_\-]+"), "[REDACTED]"),  # Anthropic-style keys
    (re.compile(r"sk-[A-Za-z0-9_\-]+"), "[REDACTED]"),  # OpenAI-style keys
    (re.compile(r"github_pat_[A-Za-z0-9_]+"), "[REDACTED]"),  # GitHub fine-grained PAT
    (re.compile(r"ghp_[A-Za-z0-9]+"), "[REDACTED]"),  # GitHub classic token
    # Generic key=value secrets (api_key / token / password / secret), case-insensitive.
    (re.compile(r"(?i)\b(api_key|apikey|token|password|secret)\s*=\s*\S+"), r"\1=[REDACTED]"),
)


def _redact_secrets(text: str) -> str:
    """Replace obvious secret-like substrings with `[REDACTED]`."""

    redacted = text
    for pattern, replacement in _SECRET_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _question_sha256(question: str) -> str:
    """Stable SHA-256 of a question string (computed from the original input)."""

    return hashlib.sha256(question.encode("utf-8")).hexdigest()


def build_trace(result: AnswerResult) -> dict[str, Any]:
    """
    Metadata-only trace payload for one run (what AnswerOptions.trace_path
    writes as JSON).

    Safe by construction: node names, timings, counters, flags, and the
    deduplicated citation lines — never document page_content, prompts,
    raw graph state, or secrets. The user question is stored only as a
    redacted/truncated preview (`question_redacted`, capped at
    QUESTION_PREVIEW_MAX_CHARS) plus the SHA-256 of the original input
    (`question_sha256`); `input_redacted` flags whether the input was
    scrubbed. `result.question` is already the redacted runtime question; the
    preview re-redacts defensively before truncating so a directly-constructed
    result can never leak a raw secret. `generated_at` is UTC ISO-8601.
    """

    return {
        "run_id": result.run_id,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "question_redacted": _redact_secrets(result.question)[:QUESTION_PREVIEW_MAX_CHARS],
        "question_sha256": result.question_sha256,
        "input_redacted": result.input_redacted,
        "node_path": list(result.node_path),
        "total_duration_ms": result.total_duration_ms,
        "node_timings_ms": [dict(entry) for entry in result.node_timings_ms],
        "stop_reason": result.stop_reason,
        "counters": {
            "retries": result.retries,
            "tracked_llm_calls": result.tracked_llm_calls,
            "web_search_count": result.web_search_count,
            "web_result_grading_count": result.web_result_grading_count,
        },
        "web_search_enabled": result.web_search_enabled,
        "web_fallback_policy": result.web_fallback_policy,
        "sources": list(result.sources),
    }


def _write_trace(trace_path: str | Path, result: AnswerResult) -> None:
    """
    Write the trace JSON, creating parent directories as needed.

    A failed trace write must never lose the answer: the error is reported
    as a console banner (exception type only — messages may carry paths or
    secrets, matching the repo's logging convention) and the run continues.
    """

    try:
        path = Path(trace_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(build_trace(result), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception as exc:
        print(f"---TRACE WRITE FAILED ({type(exc).__name__})---")


def answer_question(
    question: str,
    options: AnswerOptions | dict[str, Any] | None = None,
) -> AnswerResult:
    """
    Run one question through the compiled graph and return a structured
    AnswerResult.

    `options` may be an AnswerOptions instance or a plain dict with the same
    keys; omitted fields fall back to the environment defaults. The hard
    privacy guarantee is unchanged: web_search_enabled=False (per run or via
    WEB_SEARCH_ENABLED=false) means zero external web searches regardless of
    the fallback policy.

    Observability: a missing run_id is generated, the executed node path and
    timings are collected, and when options.trace_path is set a
    metadata-only trace JSON is written after the run (see build_trace).

    Input redaction: secret-like values in `question` are scrubbed to
    [REDACTED] before the question enters GraphState, so no secret reaches the
    retriever, router, generator, graders, or the outbound web-search query.
    The original input is used only to compute `question_sha256` (so identical
    inputs still correlate) and the `input_redacted` flag; it is never stored
    in the result, raw_state, or trace. Redaction does not change routing,
    privacy mode, or the fallback policy.
    """

    if options is None:
        options = AnswerOptions()
    elif isinstance(options, dict):
        options = AnswerOptions(**options)

    run_id = options.run_id if options.run_id else uuid.uuid4().hex

    # Redact the input up front: everything downstream (state, chains, web
    # query, result, trace) sees only the redacted runtime question. The hash
    # and the redaction flag are derived from the original, then the original
    # is dropped — not stored anywhere.
    original_question = question
    runtime_question = _redact_secrets(original_question)
    input_redacted = runtime_question != original_question
    question_sha256 = _question_sha256(original_question)

    initial_state = seed_state(
        runtime_question,
        web_search_enabled=options.web_search_enabled,
        web_fallback_policy=options.web_fallback_policy,
    )

    # Resolved via the module attribute so tests can monkeypatch graph.graph.app.
    started = time.perf_counter()
    result, node_path, node_timings = _run_graph_with_trace(graph_runtime.app, initial_state)
    total_duration_ms = round((time.perf_counter() - started) * 1000.0, 2)

    answer_result = AnswerResult(
        question=runtime_question,
        answer=result.get("generation", ""),
        stop_reason=result.get("stop_reason", ""),
        sources=source_lines(result.get("documents", [])),
        retries=result.get("retries", 0),
        tracked_llm_calls=result.get("llm_call_count", 0),
        web_search_count=result.get("web_search_count", 0),
        web_result_grading_count=result.get("web_result_grading_count", 0),
        web_search_enabled=initial_state["web_search_enabled"],
        web_fallback_policy=initial_state["web_fallback_policy"],
        raw_state=dict(result),
        run_id=run_id,
        node_path=node_path,
        node_timings_ms=node_timings,
        total_duration_ms=total_duration_ms,
        question_sha256=question_sha256,
        input_redacted=input_redacted,
    )

    if options.trace_path is not None:
        _write_trace(options.trace_path, answer_result)

    return answer_result
