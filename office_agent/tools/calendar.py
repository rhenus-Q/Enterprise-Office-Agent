"""
office_agent.tools.calendar — deterministic mock Calendar Lookup tool.

Reads a small, entirely fictional AcmeCorp calendar from
`office_agent/mock_data/calendar_events.json` and produces a concise,
deterministic summary. There is NO LLM and NO connection to Google/Outlook
Calendar or any service — Phase 3 is local-only and CI-safe. A real calendar
adapter can replace `load_events` in a later phase behind the same
`lookup_calendar` interface.

Supported query views (case-insensitive substring, first match wins):
`conflict(s)`, `next` (next meeting), `tomorrow`, `today`,
`important`/`high`/`priority`/`urgent`, otherwise the full schedule.

Reference days come from the DATA, never the system clock, so the tool is
deterministic:

- `tomorrow` is the latest calendar day that has events;
- `today` is the calendar day immediately before it.

("today" cannot be the latest populated day, because the "tomorrow" view must
still return events — so today is anchored one day earlier. The mock data places
today's and tomorrow's events on consecutive days.)

`next meeting` is the earliest-starting event in the schedule (ISO timestamps
sort chronologically). Two events `conflict` when one starts before the other
ends and ends after the other starts.

Import is side-effect-free: the JSON file is read lazily on first use (cached),
never at import time.
"""

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from office_agent.schemas import INTENT_CALENDAR_LOOKUP, ToolResult

Event = dict[str, Any]

# Tool name recorded on the ToolResult / response for observability.
CALENDAR_TOOL_NAME = INTENT_CALENDAR_LOOKUP

_EVENTS_PATH = Path(__file__).resolve().parent.parent / "mock_data" / "calendar_events.json"

# Human-readable label per view, shown in the summary header.
_VIEW_ALL = "full schedule"
_VIEW_TODAY = "today"
_VIEW_TOMORROW = "tomorrow"
_VIEW_NEXT = "next meeting"
_VIEW_CONFLICTS = "conflicts"
_VIEW_IMPORTANT = "high-priority"


@lru_cache(maxsize=1)
def _read_events() -> tuple[Event, ...]:
    """Read and cache the raw mock calendar as an immutable tuple."""

    raw = json.loads(_EVENTS_PATH.read_text(encoding="utf-8"))
    return tuple(raw)


def load_events() -> list[Event]:
    """Return a fresh copy of the mock calendar (callers may filter/sort freely)."""

    return [dict(event) for event in _read_events()]


def resolve_days(events: list[Event]) -> tuple[str, str]:
    """Return the (today, tomorrow) reference days (YYYY-MM-DD) from the data.

    `tomorrow` is the latest day with events; `today` is the calendar day
    before it. Empty input yields ("", "").
    """

    latest = max((event["start_at"][:10] for event in events), default="")
    if not latest:
        return "", ""
    today = (date.fromisoformat(latest) - timedelta(days=1)).isoformat()
    return today, latest


def next_meeting(events: list[Event]) -> Event | None:
    """The earliest-starting event in the schedule, or None if there are none."""

    if not events:
        return None
    return min(events, key=lambda event: event.get("start_at", ""))


def find_conflicts(events: list[Event]) -> list[tuple[Event, Event]]:
    """Return overlapping event pairs (deterministic, ordered by start time).

    Two events overlap when one starts before the other ends and ends after the
    other starts. ISO-8601 timestamps compare chronologically as strings.
    """

    ordered = sorted(events, key=lambda event: (event.get("start_at", ""), event.get("end_at", "")))
    conflicts: list[tuple[Event, Event]] = []
    for i in range(len(ordered)):
        for j in range(i + 1, len(ordered)):
            first, second = ordered[i], ordered[j]
            if first.get("start_at", "") < second.get("end_at", "") and first.get(
                "end_at", ""
            ) > second.get("start_at", ""):
                conflicts.append((first, second))
    return conflicts


def _select_view(query: str) -> str:
    """Map a free-text query to one view label (deterministic precedence)."""

    normalized = (query or "").casefold()
    if "conflict" in normalized:
        return _VIEW_CONFLICTS
    if "next" in normalized:
        return _VIEW_NEXT
    if "tomorrow" in normalized:
        return _VIEW_TOMORROW
    if "today" in normalized:
        return _VIEW_TODAY
    if any(word in normalized for word in ("important", "high", "priority", "urgent")):
        return _VIEW_IMPORTANT
    return _VIEW_ALL


def filter_for_query(query: str) -> tuple[str, list[Event]]:
    """Return the chosen view label and the matching events (earliest first).

    Pure and deterministic: sorting is by ISO-8601 `start_at` ascending, and
    today/tomorrow are resolved from the data, never the system clock. The
    `conflicts` view considers the whole schedule (the pairs are computed by the
    summary).
    """

    events = load_events()
    view = _select_view(query)

    if view == _VIEW_TODAY:
        today, _tomorrow = resolve_days(events)
        matched = [event for event in events if event.get("start_at", "")[:10] == today]
    elif view == _VIEW_TOMORROW:
        _today, tomorrow = resolve_days(events)
        matched = [event for event in events if event.get("start_at", "")[:10] == tomorrow]
    elif view == _VIEW_NEXT:
        upcoming = next_meeting(events)
        matched = [upcoming] if upcoming is not None else []
    elif view == _VIEW_IMPORTANT:
        matched = [event for event in events if event.get("importance") == "high"]
    else:
        # _VIEW_CONFLICTS and _VIEW_ALL both consider the whole schedule.
        matched = list(events)

    matched.sort(key=lambda event: event.get("start_at", ""))
    return view, matched


def _fmt_span(event: Event) -> str:
    """Compact time span, e.g. '2026-07-01 09:30-10:00'."""

    start = str(event.get("start_at", ""))
    end = str(event.get("end_at", ""))
    return f"{start[:16].replace('T', ' ')}-{end[11:16]}"


def _event_bullet(event: Event) -> str:
    """One concise bullet line for an event (metadata only)."""

    importance = str(event.get("importance", "normal")).upper()
    return (
        f"- {_fmt_span(event)} [{importance}] "
        f"{event.get('title', '(untitled)')} @ {event.get('location', '—')}"
    )


def lookup_calendar(query: str) -> ToolResult:
    """Summarize the mock calendar for `query` and return a ToolResult.

    The content includes a one-line summary (view + counts), the matching events
    as bullets sorted by start time, and — when relevant — a schedule-conflicts
    section listing overlapping pairs. Everything is deterministic.
    """

    view, matched = filter_for_query(query)
    total = len(load_events())

    lines = [f"Calendar — {view}: {len(matched)} of {total} event(s)."]

    if not matched:
        lines += ["", "No matching events."]
        return ToolResult(tool=CALENDAR_TOOL_NAME, content="\n".join(lines))

    lines += ["", "Events:"]
    lines += [_event_bullet(event) for event in matched]

    conflicts = find_conflicts(matched)
    if conflicts:
        lines += ["", "Schedule conflicts:"]
        lines += [
            f"- {first.get('title', '(untitled)')} overlaps {second.get('title', '(untitled)')} "
            f"({_fmt_span(first)} vs {_fmt_span(second)})"
            for first, second in conflicts
        ]

    return ToolResult(tool=CALENDAR_TOOL_NAME, content="\n".join(lines))
