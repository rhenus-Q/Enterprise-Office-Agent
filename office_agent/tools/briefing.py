"""
office_agent.tools.briefing — deterministic mock Daily Briefing aggregator.

Aggregates the other local, mock Office Agent capabilities into one concise
morning briefing. It reuses the existing *pure* loaders/helpers — it never parses
another tool's formatted output and never calls an LLM or any external service:

- Email     : `office_agent.tools.email.load_emails`
- Calendar  : `office_agent.tools.calendar` (`load_events`, `resolve_days`,
              `next_meeting`, `find_conflicts`)
- Tickets   : `office_agent.tools.tickets` (`load_tickets`, `load_tasks`,
              `ASSIGNEE_ME`)

Briefing day (deterministic, NO system clock): the calendar tool's resolved
"today" (`calendar.resolve_days(...)[0]`), which is anchored to the mock data and
aligns with the latest day present in the mock inbox. The briefing is therefore
identical on every run, which is what makes it CI-safe.

Deterministic sorting:
- emails   : key bullets are high-priority emails, newest first (by `received_at`);
- calendar : events sorted by `start_at`; "next" is the earliest event that day;
- tickets  : counts only (order-independent); tasks: counts only.

All loaders return fresh copies, so the briefing never mutates the mock data.
Import is side-effect-free (data is read lazily by the underlying loaders).
"""

from office_agent.schemas import INTENT_DAILY_BRIEFING, ToolResult
from office_agent.tools import calendar, email, tickets

# Tool name recorded on the ToolResult / response for observability.
BRIEFING_TOOL_NAME = INTENT_DAILY_BRIEFING

# Ticket priorities treated as urgent/high in the briefing.
_HIGH_TICKET_PRIORITIES = ("high", "urgent")

# How many key email bullets to surface (counts carry the rest).
_MAX_EMAIL_BULLETS = 2


def _email_section() -> list[str]:
    emails = email.load_emails()
    unread = [e for e in emails if not e.get("is_read", False)]
    important = [e for e in emails if e.get("importance") == "high"]
    needs_response = [e for e in emails if e.get("requires_response", False)]

    lines = [
        "Priority emails:",
        f"- {len(unread)} unread email(s).",
        f"- {len(important)} high-priority email(s).",
        f"- {len(needs_response)} email(s) need a response.",
    ]

    key = sorted(important, key=lambda e: e.get("received_at", ""), reverse=True)
    for message in key[:_MAX_EMAIL_BULLETS]:
        importance = str(message.get("importance", "normal")).upper()
        lines.append(
            f"- [{importance}] {message.get('subject', '(no subject)')} "
            f"— {message.get('from', 'unknown')}"
        )
    return lines


def _calendar_section() -> list[str]:
    events = calendar.load_events()
    briefing_day, _tomorrow = calendar.resolve_days(events)
    todays = sorted(
        (e for e in events if e.get("start_at", "")[:10] == briefing_day),
        key=lambda e: e.get("start_at", ""),
    )

    lines = [f"Calendar ({briefing_day}):", f"- {len(todays)} meeting(s) today."]

    upcoming = calendar.next_meeting(todays)
    if upcoming is not None:
        start = str(upcoming.get("start_at", ""))[11:16]
        lines.append(
            f"- Next: {start} {upcoming.get('title', '(untitled)')} "
            f"@ {upcoming.get('location', '—')}"
        )
    else:
        lines.append("- No more meetings today.")

    conflicts = calendar.find_conflicts(todays)
    if conflicts:
        lines.append(f"- Schedule conflicts: {len(conflicts)}")
        lines += [
            f"  - {first.get('title', '(untitled)')} overlaps {second.get('title', '(untitled)')}"
            for first, second in conflicts
        ]
    else:
        lines.append("- Schedule conflicts: none")
    return lines


def _tickets_section() -> list[str]:
    all_tickets = tickets.load_tickets()
    open_tickets = [t for t in all_tickets if t.get("status") == "open"]
    high_tickets = [t for t in all_tickets if t.get("priority") in _HIGH_TICKET_PRIORITIES]
    blocked_tickets = [t for t in all_tickets if t.get("status") == "blocked"]
    mine = [t for t in all_tickets if t.get("assignee") == tickets.ASSIGNEE_ME]

    all_tasks = tickets.load_tasks()
    open_tasks = [t for t in all_tasks if t.get("status") == "open"]
    linked_tasks = [t for t in all_tasks if t.get("source_ticket_id")]

    return [
        "Tickets and tasks:",
        f"- {len(open_tickets)} open ticket(s).",
        f"- {len(high_tickets)} urgent/high-priority ticket(s).",
        f"- {len(blocked_tickets)} blocked ticket(s).",
        f"- {len(mine)} ticket(s) assigned to you.",
        f"- {len(open_tasks)} open task(s) ({len(linked_tasks)} linked to tickets).",
    ]


def _focus_section() -> list[str]:
    emails = email.load_emails()
    needs_response = [e for e in emails if e.get("requires_response", False)]

    events = calendar.load_events()
    briefing_day, _tomorrow = calendar.resolve_days(events)
    todays = [e for e in events if e.get("start_at", "")[:10] == briefing_day]
    upcoming = calendar.next_meeting(todays)

    all_tickets = tickets.load_tickets()
    high_tickets = [t for t in all_tickets if t.get("priority") in _HIGH_TICKET_PRIORITIES]
    blocked_tickets = [t for t in all_tickets if t.get("status") == "blocked"]

    # Deterministic recommendations derived from the data above, in a fixed order.
    recommendations: list[str] = []
    if needs_response:
        recommendations.append(f"Respond to {len(needs_response)} email(s) awaiting your reply.")
    if upcoming is not None:
        start = str(upcoming.get("start_at", ""))[11:16]
        recommendations.append(f"Prepare for '{upcoming.get('title', '(untitled)')}' at {start}.")
    if high_tickets:
        recommendations.append(f"Progress {len(high_tickets)} high-priority ticket(s).")
    if blocked_tickets:
        recommendations.append(f"Follow up on {len(blocked_tickets)} blocked ticket(s).")
    if not recommendations:
        recommendations.append("Nothing urgent flagged for today.")

    lines = ["Recommended focus:"]
    lines += [f"{index}. {text}" for index, text in enumerate(recommendations, start=1)]
    return lines


def briefing_day() -> str:
    """The deterministic briefing day (YYYY-MM-DD) — the calendar's 'today'."""

    today, _tomorrow = calendar.resolve_days(calendar.load_events())
    return today


def generate_daily_briefing(query: str) -> ToolResult:
    """Aggregate email/calendar/ticket mock data into one deterministic briefing.

    `query` is accepted for interface consistency but not needed: the briefing is
    holistic. The result is identical on every run (no system clock, no LLM).
    """

    sections: list[list[str]] = [
        [f"Daily briefing — {briefing_day()}"],
        _email_section(),
        _calendar_section(),
        _tickets_section(),
        _focus_section(),
    ]

    content = "\n\n".join("\n".join(section) for section in sections)
    return ToolResult(tool=BRIEFING_TOOL_NAME, content=content)
