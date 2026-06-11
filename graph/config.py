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

    return _positive_int_from_env(
        "MAX_WEB_SEARCHES_PER_RUN", DEFAULT_MAX_WEB_SEARCHES_PER_RUN
    )


def max_web_results_to_grade() -> int:
    """Budget for web results graded for relevance per run (MAX_WEB_RESULTS_TO_GRADE)."""

    return _positive_int_from_env(
        "MAX_WEB_RESULTS_TO_GRADE", DEFAULT_MAX_WEB_RESULTS_TO_GRADE
    )
