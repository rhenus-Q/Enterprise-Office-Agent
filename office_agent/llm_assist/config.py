"""
office_agent.llm_assist.config — Office-Agent-only settings for the LLM email digest.

Deliberately independent of `enterprise_rag`: this module reads its own environment
variables and defines its own stop-reason / caveat constants, so the Office Agent
gains one optional LLM feature without importing `enterprise_rag` config. Reading
configuration is side-effect-free — no client construction, no `.env` loading.

The flag defaults to **off** and the stop-reason / caveat constants live here (not
in `office_agent/schemas.py`), so the existing `ToolResult` / `OfficeAgentResponse`
schema shape is unchanged.
"""

import os

# Values (case-insensitive, whitespace-stripped) that count as "enabled".
_TRUTHY_VALUES = {"true", "1", "yes", "on"}

# Default per-request timeout (seconds) for the single digest LLM call.
DEFAULT_OFFICE_LLM_REQUEST_TIMEOUT_SECONDS = 60

# stop_reason recorded on the ToolResult when the assist fails and the tool falls
# back to the deterministic summary. Office-only; distinct from enterprise_rag's
# stop reasons and never added to office_agent/schemas.py.
STOP_REASON_LLM_ASSIST_ERROR = "llm_assist_error"

# User-facing caveat appended to the deterministic summary on any assist failure.
LLM_ASSIST_ERROR_NOTE = (
    "Note: the LLM-assisted digest was unavailable; showing the standard summary."
)


def office_llm_enabled() -> bool:
    """Whether the optional LLM email digest is enabled (`OFFICE_LLM_ENABLED`).

    Default **off**: only an explicit truthy value (`"true"`/`"1"`/`"yes"`/`"on"`,
    case-insensitive, whitespace-stripped) enables it. This is the deliberate
    inverse of `enterprise_rag`'s `WEB_SEARCH_ENABLED` default-on parsing — the
    office assist must never turn on by accident.
    """

    return os.getenv("OFFICE_LLM_ENABLED", "false").strip().lower() in _TRUTHY_VALUES


def office_llm_request_timeout_seconds() -> int:
    """Per-request timeout (seconds) for the digest LLM call.

    `OFFICE_LLM_REQUEST_TIMEOUT_SECONDS`; missing, malformed, zero, or negative
    values fall back to the default (mirrors `enterprise_rag`'s positive-int
    parsing without importing it).
    """

    raw = os.getenv("OFFICE_LLM_REQUEST_TIMEOUT_SECONDS")
    if raw is None:
        return DEFAULT_OFFICE_LLM_REQUEST_TIMEOUT_SECONDS

    try:
        value = int(raw.strip())
    except ValueError:
        return DEFAULT_OFFICE_LLM_REQUEST_TIMEOUT_SECONDS

    return value if value > 0 else DEFAULT_OFFICE_LLM_REQUEST_TIMEOUT_SECONDS
