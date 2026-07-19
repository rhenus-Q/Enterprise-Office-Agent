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

The deterministic briefing is the default and only behavior unless the optional,
**default-off** LLM narrative (`office_agent.llm_assist.briefing_narrative`, gated
by the shared `OFFICE_LLM_ENABLED` flag) is enabled. With the flag off, no LLM
client is constructed and the output is byte-for-byte identical to the
deterministic briefing; when on, a single structured-output call *prepends* an
LLM-assisted narrative + validated reference list above the unchanged deterministic
facts, and any failure falls back to the deterministic briefing with an honest
caveat (see `_maybe_apply_llm_narrative`).
"""

from office_agent.llm_assist import briefing_narrative
from office_agent.llm_assist import config as llm_config
from office_agent.schemas import INTENT_DAILY_BRIEFING, ToolResult
from office_agent.tools import approvals, calendar, email, tickets

# Tool name recorded on the ToolResult / response for observability.
BRIEFING_TOOL_NAME = INTENT_DAILY_BRIEFING

# Ticket / approval priorities treated as urgent/high in the briefing.
_HIGH_TICKET_PRIORITIES = ("high", "urgent")

# How many key email bullets to surface (counts carry the rest).
_MAX_EMAIL_BULLETS = 2

# Per-source cap on the item-level facts collected for the optional LLM narrative
# (deterministic first-N after each source's documented sort). Bounds tokens and
# keeps the grounding whitelist small; does NOT affect the rendered deterministic
# sections above, which are unchanged.
#
# The cap is a *soft* base limit: a meeting that is the schedule-conflict
# counterpart of a selected meeting is additionally preserved past the limit
# (see `collect_briefing_facts`) so the narrative can describe both sides of a
# conflict. Ordinary, non-critical facts beyond the limit stay excluded.
_MAX_FACTS_PER_SOURCE = 5

# Deterministic critical-reason labels attached to the enriched meeting/ticket
# facts handed to the optional LLM narrative. They make urgency, blocking, and
# schedule conflicts explicit in the LLM input rather than something the model
# must infer from a title. Emitted in the fixed order below.
_REASON_SCHEDULE_CONFLICT = "schedule_conflict"
_REASON_HIGH_IMPORTANCE = "high_importance"
_REASON_HIGH_PRIORITY = "high_priority"
_REASON_BLOCKED = "blocked"


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


def _dedup_by_id(items: list[dict]) -> list[dict]:
    """Return `items` with duplicate ids removed, preserving first-seen order."""

    seen: set[str] = set()
    unique: list[dict] = []
    for item in items:
        item_id = str(item.get("id", ""))
        if item_id in seen:
            continue
        seen.add(item_id)
        unique.append(item)
    return unique


def _fact(source_type: str, item: dict, title_field: str) -> dict[str, object]:
    """Build one `{source_type, id, title}` fact from a raw mock item (pure)."""

    return {
        "source_type": source_type,
        "id": str(item.get("id", "")),
        "title": str(item.get(title_field, "(untitled)")),
    }


def _meeting_fact(event: dict, conflicts_with: list[str]) -> dict[str, object]:
    """Build one enriched meeting fact with deterministic critical metadata (pure).

    Beyond the base `{source_type, id, title}` this exposes `start_at`/`end_at`,
    `importance`, the ids the meeting overlaps (`conflicts_with`), and the derived
    `critical_reasons` (`schedule_conflict` when it overlaps another meeting,
    `high_importance` when flagged high). None of this is invented — every value
    comes straight from the deterministic mock event.
    """

    importance = str(event.get("importance", ""))
    reasons: list[str] = []
    if conflicts_with:
        reasons.append(_REASON_SCHEDULE_CONFLICT)
    if importance == "high":
        reasons.append(_REASON_HIGH_IMPORTANCE)

    return {
        "source_type": "meeting",
        "id": str(event.get("id", "")),
        "title": str(event.get("title", "(untitled)")),
        "start_at": str(event.get("start_at", "")),
        "end_at": str(event.get("end_at", "")),
        "importance": importance,
        "conflicts_with": conflicts_with,
        "critical_reasons": reasons,
    }


def _ticket_fact(ticket: dict) -> dict[str, object]:
    """Build one enriched ticket fact with deterministic critical metadata (pure).

    Exposes `priority`/`status` and the derived `critical_reasons`
    (`high_priority` for a high/urgent ticket, `blocked` for a blocked one) so the
    narrative can see urgency and blocking explicitly instead of guessing from the
    title. Values come straight from the deterministic mock ticket.
    """

    priority = str(ticket.get("priority", ""))
    status = str(ticket.get("status", ""))
    reasons: list[str] = []
    if priority in _HIGH_TICKET_PRIORITIES:
        reasons.append(_REASON_HIGH_PRIORITY)
    if status == "blocked":
        reasons.append(_REASON_BLOCKED)

    return {
        "source_type": "ticket",
        "id": str(ticket.get("id", "")),
        "title": str(ticket.get("title", "(untitled)")),
        "priority": priority,
        "status": status,
        "critical_reasons": reasons,
    }


def collect_briefing_facts() -> list[dict[str, object]]:
    """Collect the bounded, item-level fact set for the optional LLM narrative (pure).

    This is the single source of truth for BOTH the LLM input and the grounding
    whitelist. It mutates nothing (loaders return fresh copies), reads no system
    clock (the briefing day comes from the data), and applies a documented
    per-source cap (`_MAX_FACTS_PER_SOURCE`, deterministic first-N after each
    source's sort). Selection intentionally mirrors the rendered sections so the
    facts stay consistent with them; approvals are added because the narrative
    synthesizes them even though the rendered briefing does not list them.

    Meetings and tickets carry deterministic *critical metadata* (schedule
    conflicts, importance, priority, blocking) so those signals are explicit in
    the LLM input. The per-source cap is a soft base limit for meetings: any
    meeting that is the conflict counterpart of a selected meeting is preserved
    past the limit so both sides of a schedule conflict are always available.
    """

    facts: list[dict[str, object]] = []

    # Emails: high-importance OR response-needed, deduped, newest first.
    emails = email.load_emails()
    selected_emails = [
        e for e in emails if e.get("importance") == "high" or e.get("requires_response", False)
    ]
    selected_emails = _dedup_by_id(selected_emails)
    selected_emails.sort(key=lambda e: e.get("received_at", ""), reverse=True)
    facts += [_fact("email", e, "subject") for e in selected_emails[:_MAX_FACTS_PER_SOURCE]]

    # Meetings: today's events, sorted by start time. The base cap keeps the first
    # N, then any omitted meeting that overlaps a selected one is additionally
    # preserved (soft-cap overflow for the conflict counterpart only).
    events = calendar.load_events()
    day = briefing_day()
    todays = sorted(
        (ev for ev in events if ev.get("start_at", "")[:10] == day),
        key=lambda ev: ev.get("start_at", ""),
    )
    selected_meetings = todays[:_MAX_FACTS_PER_SOURCE]
    selected_ids = {str(ev.get("id", "")) for ev in selected_meetings}

    # Deterministic conflict partners across the whole day (reuses the existing
    # calendar overlap rule; symmetric so each side lists the other).
    conflict_partners: dict[str, set[str]] = {}
    for first, second in calendar.find_conflicts(todays):
        a, b = str(first.get("id", "")), str(second.get("id", ""))
        conflict_partners.setdefault(a, set()).add(b)
        conflict_partners.setdefault(b, set()).add(a)

    # Keep the selected meetings (order preserved), then append counterparts that
    # conflict with a selected meeting, in the day's start-time order.
    kept_meetings = list(selected_meetings)
    kept_ids = set(selected_ids)
    for ev in todays:
        ev_id = str(ev.get("id", ""))
        if ev_id in kept_ids:
            continue
        if conflict_partners.get(ev_id, set()) & selected_ids:
            kept_meetings.append(ev)
            kept_ids.add(ev_id)

    facts += [
        _meeting_fact(
            ev,
            sorted(conflict_partners.get(str(ev.get("id", "")), set()) & kept_ids),
        )
        for ev in kept_meetings
    ]

    # Tickets: open OR high/urgent OR blocked OR assigned to me, deduped, by id.
    all_tickets = tickets.load_tickets()
    selected_tickets = [
        t
        for t in all_tickets
        if t.get("status") == "open"
        or t.get("priority") in _HIGH_TICKET_PRIORITIES
        or t.get("status") == "blocked"
        or t.get("assignee") == tickets.ASSIGNEE_ME
    ]
    selected_tickets = _dedup_by_id(selected_tickets)
    selected_tickets.sort(key=lambda t: str(t.get("id", "")))
    facts += [_ticket_fact(t) for t in selected_tickets[:_MAX_FACTS_PER_SOURCE]]

    # Tasks: open tasks, deduped, by id.
    all_tasks = tickets.load_tasks()
    selected_tasks = _dedup_by_id([t for t in all_tasks if t.get("status") == "open"])
    selected_tasks.sort(key=lambda t: str(t.get("id", "")))
    facts += [_fact("task", t, "title") for t in selected_tasks[:_MAX_FACTS_PER_SOURCE]]

    # Approvals: pending OR high/urgent OR mine (approver is me), deduped, by id.
    all_approvals = approvals.load_approvals()
    selected_approvals = [
        a
        for a in all_approvals
        if a.get("status") == "pending"
        or a.get("priority") in _HIGH_TICKET_PRIORITIES
        or a.get("approver") == approvals.ASSIGNEE_ME
    ]
    selected_approvals = _dedup_by_id(selected_approvals)
    selected_approvals.sort(key=lambda a: str(a.get("id", "")))
    facts += [_fact("approval", a, "title") for a in selected_approvals[:_MAX_FACTS_PER_SOURCE]]

    return facts


def _maybe_apply_llm_narrative(content: str, facts: list[dict[str, object]]) -> ToolResult:
    """Optionally prepend an LLM-assisted narrative above the deterministic briefing.

    Default **off**: when `OFFICE_LLM_ENABLED` is not truthy this returns exactly
    the deterministic `ToolResult` and never constructs an LLM client. Empty facts
    (defensive) also skip the call. When enabled with facts, it runs a single
    structured-output call; any failure (timeout, API error, structured-output
    parse failure, Pydantic validation error, or grounding failure from
    `validate_narrative`) logs a type-only banner and falls back to the
    deterministic briefing plus a caveat and `stop_reason="llm_assist_error"`. It
    never re-raises — the assist can never crash the Office Agent.

    On success the narrative block + validated reference list are prepended above a
    `"Deterministic briefing (facts):"`-labeled copy of the unchanged `content`.
    """

    if not llm_config.office_llm_enabled():
        return ToolResult(tool=BRIEFING_TOOL_NAME, content=content)

    if not facts:
        return ToolResult(tool=BRIEFING_TOOL_NAME, content=content)

    try:
        narrative = briefing_narrative.narrate_briefing(facts)
        briefing_narrative.validate_narrative(narrative, facts)
    except Exception as exc:
        # Deliberate catch-all: the optional assist must degrade, never crash.
        # Log only the exception type (repo convention), never the message.
        print(f"---BRIEFING NARRATIVE ASSIST FAILED ({type(exc).__name__})---")
        return ToolResult(
            tool=BRIEFING_TOOL_NAME,
            content=f"{content}\n\n{briefing_narrative.BRIEFING_ASSIST_ERROR_NOTE}",
            stop_reason=llm_config.STOP_REASON_LLM_ASSIST_ERROR,
        )

    narrative_block = briefing_narrative.render_narrative(narrative, facts)
    return ToolResult(
        tool=BRIEFING_TOOL_NAME,
        content=f"{narrative_block}\n\nDeterministic briefing (facts):\n{content}",
    )


def generate_daily_briefing(query: str) -> ToolResult:
    """Aggregate email/calendar/ticket mock data into one deterministic briefing.

    `query` is accepted for interface consistency but not needed: the briefing is
    holistic. The deterministic result is identical on every run (no system clock,
    no LLM); the optional, default-off LLM narrative (`_maybe_apply_llm_narrative`)
    only ever prepends above it and never alters the deterministic lines.
    """

    sections: list[list[str]] = [
        [f"Daily briefing — {briefing_day()}"],
        _email_section(),
        _calendar_section(),
        _tickets_section(),
        _focus_section(),
    ]

    content = "\n\n".join("\n".join(section) for section in sections)
    return _maybe_apply_llm_narrative(content, collect_briefing_facts())
