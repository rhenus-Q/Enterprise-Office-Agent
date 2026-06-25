"""
config.py

Runtime configuration flags read from environment variables.

Kept separate from the graph modules so that reading configuration stays
side-effect-free and easy to test: no client construction, no .env loading
(callers such as main.py load .env before invoking the graph).
"""

import os

# Values (case-insensitive, whitespace-stripped) that disable a boolean flag.
_FALSY_VALUES = {"false", "0", "no", "off"}


def web_search_enabled() -> bool:
    """
    Read the WEB_SEARCH_ENABLED toggle from the environment.

    Returns True when the variable is missing or set to anything other than an
    explicit falsy value, preserving the original always-on behavior. Only an
    explicit "false" / "0" / "no" / "off" enables privacy mode, in which user
    questions are never sent to an external web search service.
    """

    return os.getenv("WEB_SEARCH_ENABLED", "true").strip().lower() not in _FALSY_VALUES


# Web-fallback policy values (WEB_FALLBACK_POLICY). Distinct from the
# WEB_SEARCH_ENABLED privacy switch: the switch decides whether external web
# search is allowed at all; the policy decides WHEN the system chooses
# retrieval-triggered web fallback while web search is otherwise allowed.
WEB_FALLBACK_CONSERVATIVE = (
    "conservative"  # web only when zero relevant local docs remain (default)
)
WEB_FALLBACK_AGGRESSIVE = (
    "aggressive"  # legacy CRAG behavior: any irrelevant doc triggers web fallback
)
WEB_FALLBACK_DISABLED = "disabled"  # local retrieval paths never fall back to the web

_WEB_FALLBACK_POLICIES = {
    WEB_FALLBACK_CONSERVATIVE,
    WEB_FALLBACK_AGGRESSIVE,
    WEB_FALLBACK_DISABLED,
}


def normalize_web_fallback_policy(value) -> str:
    """
    Normalize a web-fallback policy value (case-insensitive,
    whitespace-stripped). Unknown, missing, or None values fall back to
    "conservative" — for an enterprise internal-document assistant the safe
    default is to answer from the curated local corpus first and use the web
    only when nothing relevant remains.

    Shared by the env reader below and by per-run callers (graph/engine.py)
    that pass an explicit policy, so both resolve values identically.
    """

    if value is None:
        return WEB_FALLBACK_CONSERVATIVE

    cleaned = str(value).strip().lower()
    return cleaned if cleaned in _WEB_FALLBACK_POLICIES else WEB_FALLBACK_CONSERVATIVE


def web_fallback_policy() -> str:
    """
    Read the WEB_FALLBACK_POLICY default from the environment. This is the
    default source only: the engine resolves the effective policy into
    GraphState["web_fallback_policy"] once per run, and graph decisions read
    it from state.
    """

    return normalize_web_fallback_policy(os.getenv("WEB_FALLBACK_POLICY"))


# Per-run budget defaults. Sized above the worst case the MAX_RETRIES loop can
# produce today (5 generations + 4 query rewrites + 15 web-result grades = 24
# counted LLM calls, 5 searches, 15 grades), so the budgets never bind before
# the retry cap does unless explicitly tightened via environment variables.
DEFAULT_MAX_LLM_CALLS_PER_RUN = 30
DEFAULT_MAX_WEB_SEARCHES_PER_RUN = 5
DEFAULT_MAX_WEB_RESULTS_TO_GRADE = 15


def _positive_int_from_env(name: str, default: int) -> int:
    """
    Read a positive integer from the environment.
    Missing, malformed, zero, or negative values fall back to the default —
    a budget can be tightened or loosened, but never accidentally disabled.
    """

    raw = os.getenv(name)
    if raw is None:
        return default

    try:
        value = int(raw.strip())
    except ValueError:
        return default

    return value if value > 0 else default


def max_llm_calls_per_run() -> int:
    """Budget for counted LLM calls per graph run (MAX_LLM_CALLS_PER_RUN)."""

    return _positive_int_from_env("MAX_LLM_CALLS_PER_RUN", DEFAULT_MAX_LLM_CALLS_PER_RUN)


def max_web_searches_per_run() -> int:
    """Budget for Tavily searches per graph run (MAX_WEB_SEARCHES_PER_RUN)."""

    return _positive_int_from_env("MAX_WEB_SEARCHES_PER_RUN", DEFAULT_MAX_WEB_SEARCHES_PER_RUN)


def max_web_results_to_grade() -> int:
    """Budget for web results graded for relevance per run (MAX_WEB_RESULTS_TO_GRADE)."""

    return _positive_int_from_env("MAX_WEB_RESULTS_TO_GRADE", DEFAULT_MAX_WEB_RESULTS_TO_GRADE)


# Per-request timeout (seconds) for an individual LLM call. Bounds wall-clock
# time on a single ChatOpenAI request so a hung dependency cannot stall a run;
# the existing per-call exception handlers map a timeout to the right *_error
# stop_reason, so the success path is unchanged.
DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS = 60


def llm_request_timeout_seconds() -> int:
    """Per-request timeout in seconds for LLM calls (LLM_REQUEST_TIMEOUT_SECONDS)."""

    return _positive_int_from_env(
        "LLM_REQUEST_TIMEOUT_SECONDS", DEFAULT_LLM_REQUEST_TIMEOUT_SECONDS
    )
