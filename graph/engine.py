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

Import is side-effect-free in the repo's sense: no external client is
constructed (graph.graph builds clients lazily), so importing this module
needs no API keys and no network.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

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
    """

    web_search_enabled: Optional[bool] = None
    web_fallback_policy: Optional[str] = None
    run_id: Optional[str] = None


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
    """

    question: str
    answer: str
    stop_reason: str
    sources: List[str] = field(default_factory=list)
    retries: int = 0
    tracked_llm_calls: int = 0
    web_search_count: int = 0
    web_result_grading_count: int = 0
    web_search_enabled: bool = True
    web_fallback_policy: str = config.WEB_FALLBACK_CONSERVATIVE
    raw_state: Dict[str, Any] = field(default_factory=dict)
    run_id: Optional[str] = None


def seed_state(
    question: str,
    *,
    web_search_enabled: Optional[bool] = None,
    web_fallback_policy: Optional[str] = None,
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


def answer_question(
    question: str,
    options: Optional[Union[AnswerOptions, Dict[str, Any]]] = None,
) -> AnswerResult:
    """
    Run one question through the compiled graph and return a structured
    AnswerResult.

    `options` may be an AnswerOptions instance or a plain dict with the same
    keys; omitted fields fall back to the environment defaults. The hard
    privacy guarantee is unchanged: web_search_enabled=False (per run or via
    WEB_SEARCH_ENABLED=false) means zero external web searches regardless of
    the fallback policy.
    """

    if options is None:
        options = AnswerOptions()
    elif isinstance(options, dict):
        options = AnswerOptions(**options)

    initial_state = seed_state(
        question,
        web_search_enabled=options.web_search_enabled,
        web_fallback_policy=options.web_fallback_policy,
    )

    # Resolved via the module attribute so tests can monkeypatch graph.graph.app.
    result = graph_runtime.app.invoke(initial_state)

    return AnswerResult(
        question=question,
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
        run_id=options.run_id,
    )
