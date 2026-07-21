"""
office_agent.tools.email — deterministic mock Email Summary tool.

Reads a small, entirely fictional AcmeCorp inbox from
`office_agent/mock_data/emails.json` and produces a concise, deterministic
summary. There is NO connection to Gmail/Outlook/any mail service — local-only and
CI-safe. A real mail adapter can replace `load_emails` in a later phase behind the
same `summarize_emails` interface.

The deterministic summary is the default and only behavior unless the optional,
**default-off** LLM digest (`office_agent.llm_assist`, gated by `OFFICE_LLM_ENABLED`)
is enabled. With the flag off, no LLM client is constructed and the output is
byte-for-byte identical to the deterministic summary; when on, a single
structured-output call appends an LLM-assisted digest and any failure falls back
to the deterministic summary with an honest caveat (see `_maybe_apply_llm_digest`).

Supported query filters (case-insensitive substring, first match wins):
`unread`, `important`/`high`/`priority`/`urgent`, response-needed
(`respond`/`response`/`reply`), `today`, otherwise all messages. "Today" is the
most recent calendar day present in the mock data (not the system clock), so the
tool stays deterministic.

Import is side-effect-free: the JSON file is read lazily on first use (cached),
never at import time.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from office_agent.llm_assist import config as llm_config
from office_agent.llm_assist import email_digest
from office_agent.llm_assist.email_models import EmailDigest
from office_agent.schemas import INTENT_EMAIL_SUMMARY, ToolResult

Email = dict[str, Any]

# Tool name recorded on the ToolResult / response for observability.
EMAIL_TOOL_NAME = INTENT_EMAIL_SUMMARY

_EMAILS_PATH = Path(__file__).resolve().parent.parent / "mock_data" / "emails.json"

# Human-readable label per filter, shown in the summary header.
_FILTER_ALL = "all messages"
_FILTER_UNREAD = "unread"
_FILTER_IMPORTANT = "high-priority"
_FILTER_RESPONSE = "response needed"
_FILTER_TODAY = "today"


@lru_cache(maxsize=1)
def _read_emails() -> tuple[Email, ...]:
    """Read and cache the raw mock inbox as an immutable tuple."""

    raw = json.loads(_EMAILS_PATH.read_text(encoding="utf-8"))
    return tuple(raw)


def load_emails() -> list[Email]:
    """Return a fresh copy of the mock inbox (callers may filter/sort freely)."""

    return [dict(email) for email in _read_emails()]


def _latest_day(emails: list[Email]) -> str:
    """The most recent calendar day (YYYY-MM-DD) present in the inbox."""

    return max((email["received_at"][:10] for email in emails), default="")


def _select_filter(query: str) -> str:
    """Map a free-text query to one filter label (deterministic precedence)."""

    normalized = (query or "").casefold()
    if "unread" in normalized:
        return _FILTER_UNREAD
    if any(word in normalized for word in ("important", "high", "priority", "urgent")):
        return _FILTER_IMPORTANT
    if any(word in normalized for word in ("respond", "response", "reply")):
        return _FILTER_RESPONSE
    if "today" in normalized:
        return _FILTER_TODAY
    return _FILTER_ALL


def filter_for_query(query: str) -> tuple[str, list[Email]]:
    """Return the chosen filter label and the matching emails (newest first).

    Pure and deterministic: sorting is by ISO-8601 `received_at` descending
    (ISO strings sort chronologically), and "today" is resolved against the
    latest day in the data, never the system clock.
    """

    emails = load_emails()
    label = _select_filter(query)

    if label == _FILTER_UNREAD:
        matched = [email for email in emails if not email.get("is_read", False)]
    elif label == _FILTER_IMPORTANT:
        matched = [email for email in emails if email.get("importance") == "high"]
    elif label == _FILTER_RESPONSE:
        matched = [email for email in emails if email.get("requires_response", False)]
    elif label == _FILTER_TODAY:
        today = _latest_day(emails)
        matched = [email for email in emails if email.get("received_at", "")[:10] == today]
    else:
        matched = list(emails)

    matched.sort(key=lambda email: email.get("received_at", ""), reverse=True)
    return label, matched


def _email_bullet(email: Email) -> str:
    """One concise bullet line for an email (metadata only, no full body)."""

    flags = []
    if not email.get("is_read", False):
        flags.append("UNREAD")
    flags.append(str(email.get("importance", "normal")).upper())
    prefix = " ".join(f"[{flag}]" for flag in flags)
    suffix = " (needs response)" if email.get("requires_response", False) else ""
    return f"- {prefix} {email.get('subject', '(no subject)')} — from {email.get('from', 'unknown')}{suffix}"


def _render_digest(digest: EmailDigest, matched: list[Email]) -> str:
    """Render a validated `EmailDigest` deterministically.

    Subjects in the priority section are looked up from the matched emails by id
    (the validated `priority_order` ids), never taken from the LLM output.
    """

    subject_by_id = {
        str(email.get("id", "")): email.get("subject", "(no subject)") for email in matched
    }

    lines = ["Digest (LLM-assisted):", digest.summary, "", "Action items (extracted):"]
    if digest.action_items:
        for item in digest.action_items:
            deadline = f" (deadline: {item.deadline})" if item.deadline else ""
            lines.append(f"- [{item.email_id}] {item.ask}{deadline}")
    else:
        lines.append("- None.")

    lines += ["", "Priority order:"]
    if digest.priority_order:
        for index, email_id in enumerate(digest.priority_order, start=1):
            lines.append(f"{index}. {subject_by_id.get(email_id, '(unknown)')} ({email_id})")
    else:
        lines.append("- None.")

    return "\n".join(lines)


def _assist_enabled(llm_assist_enabled: bool | None) -> bool:
    """Resolve the per-run assist decision, defaulting to the server flag."""

    if llm_assist_enabled is None:
        return llm_config.office_llm_enabled()
    return llm_assist_enabled


def _maybe_apply_llm_digest(
    content: str, matched: list[Email], llm_assist_enabled: bool | None = None
) -> ToolResult:
    """Optionally append an LLM-assisted digest to the deterministic summary.

    Default **off**: when `OFFICE_LLM_ENABLED` is not truthy, this returns exactly
    the deterministic `ToolResult` and never constructs an LLM client. When enabled,
    it runs a single structured-output call; any failure (timeout, API error,
    structured-output parse failure, Pydantic validation error, or grounding
    failure from `validate_digest`) logs a type-only banner and falls back to the
    deterministic summary plus a caveat and `stop_reason="llm_assist_error"`. It
    never re-raises — the assist can never crash the Office Agent.

    `llm_assist_enabled` is the request-scoped decision: `None` (the default)
    reads the server flag exactly as before, so behavior without per-run options
    is unchanged. An explicit value is expected to have already been ANDed with
    the server flag by the caller, so a request can only ever turn the assist
    *off*, never on.
    """

    if not _assist_enabled(llm_assist_enabled):
        return ToolResult(tool=EMAIL_TOOL_NAME, content=content)

    try:
        digest = email_digest.digest_emails(matched)
        email_digest.validate_digest(digest, matched)
    except Exception as exc:
        # Deliberate catch-all: the optional assist must degrade, never crash.
        # Log only the exception type (repo convention), never the message.
        print(f"---EMAIL DIGEST ASSIST FAILED ({type(exc).__name__})---")
        return ToolResult(
            tool=EMAIL_TOOL_NAME,
            content=f"{content}\n\n{llm_config.LLM_ASSIST_ERROR_NOTE}",
            stop_reason=llm_config.STOP_REASON_LLM_ASSIST_ERROR,
        )

    return ToolResult(
        tool=EMAIL_TOOL_NAME,
        content=f"{content}\n\n{_render_digest(digest, matched)}",
    )


def summarize_emails(query: str, *, llm_assist_enabled: bool | None = None) -> ToolResult:
    """Summarize the mock inbox for `query` and return a ToolResult.

    The content includes a one-line summary (filter + counts), the matching
    messages as bullets, and an explicit action-items list for messages that
    require a response. The deterministic summary is identical on every run; the
    optional, default-off LLM digest (`_maybe_apply_llm_digest`) only ever appends
    to it and never alters the deterministic lines.

    `llm_assist_enabled` is the request-scoped assist decision; `None` keeps the
    previous server-flag behavior exactly.
    """

    label, matched = filter_for_query(query)
    total = len(load_emails())

    lines = [f"Inbox summary — {label}: {len(matched)} of {total} message(s)."]

    if not matched:
        # No matches: skip the assist entirely (no LLM call) — output unchanged.
        lines += ["", "No matching emails."]
        return ToolResult(tool=EMAIL_TOOL_NAME, content="\n".join(lines))

    lines += ["", "Messages:"]
    lines += [_email_bullet(email) for email in matched]

    action_items = [email for email in matched if email.get("requires_response", False)]
    if action_items:
        lines += ["", "Action items (response needed):"]
        lines += [
            f"- {email.get('subject', '(no subject)')} — from {email.get('from', 'unknown')}"
            for email in action_items
        ]

    return _maybe_apply_llm_digest("\n".join(lines), matched, llm_assist_enabled)
