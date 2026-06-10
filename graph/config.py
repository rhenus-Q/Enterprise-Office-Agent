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
