"""
office_agent.llm_assist.config — shared Office-Agent-only settings for both optional
LLM assists: the Email Digest and the Daily Briefing narrative.

Both assists are gated by the same default-off `OFFICE_LLM_ENABLED` flag, share the
per-request timeout (`office_llm_request_timeout_seconds()`), and record the same
`STOP_REASON_LLM_ASSIST_ERROR` when they fail and their tool falls back to the
deterministic output.

Deliberately independent of `enterprise_rag`: this module reads its own environment
variables and defines its own stop-reason / caveat constants, so the Office Agent
gains its optional LLM features without importing `enterprise_rag` config. Importing
this module and reading configuration are side-effect-free — no client construction,
no `.env` loading.

`LLM_ASSIST_ERROR_NOTE` is specifically the **Email Digest** caveat; the Daily
Briefing defines its own caveat (`BRIEFING_ASSIST_ERROR_NOTE`) in
`office_agent/llm_assist/briefing_narrative.py`.

The flag defaults to **off** and the stop-reason / caveat constants live here (not
in `office_agent/schemas.py`), so the existing `ToolResult` / `OfficeAgentResponse`
schema shape is unchanged.
"""

import os

# Values (case-insensitive, whitespace-stripped) that count as "enabled".
_TRUTHY_VALUES = {"true", "1", "yes", "on"}

# Default per-request timeout (seconds) for the single LLM call made by either
# assist (email digest or briefing narrative).
DEFAULT_OFFICE_LLM_REQUEST_TIMEOUT_SECONDS = 60

# stop_reason recorded on the ToolResult when either assist fails and the tool falls
# back to its deterministic output. Office-only; distinct from enterprise_rag's
# stop reasons and never added to office_agent/schemas.py.
STOP_REASON_LLM_ASSIST_ERROR = "llm_assist_error"

# User-facing caveat appended to the deterministic email summary when the Email
# Digest assist fails. Email-specific: the Daily Briefing narrative has its own
# caveat (BRIEFING_ASSIST_ERROR_NOTE) in briefing_narrative.py.
LLM_ASSIST_ERROR_NOTE = (
    "Note: the LLM-assisted digest was unavailable; showing the standard summary."
)


def office_llm_enabled() -> bool:
    """Whether the optional LLM assists are enabled (`OFFICE_LLM_ENABLED`).

    The single switch for both the Email Digest and the Daily Briefing narrative.

    Default **off**: only an explicit truthy value (`"true"`/`"1"`/`"yes"`/`"on"`,
    case-insensitive, whitespace-stripped) enables them. This is the deliberate
    inverse of `enterprise_rag`'s `WEB_SEARCH_ENABLED` default-on parsing — the
    office assists must never turn on by accident.
    """

    return os.getenv("OFFICE_LLM_ENABLED", "false").strip().lower() in _TRUTHY_VALUES


def office_llm_request_timeout_seconds() -> int:
    """Per-request timeout (seconds) for either assist's single LLM call.

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
