"""
office_agent.tools.meeting — deterministic mock Meeting Agent / Meeting Prep.

An advanced *composition* capability (Office Agent v1.5.0): it prepares the user
for a meeting by combining the existing local mock Office Agent data — calendar
events, inbox, tickets, and tasks — into one concise, predictable prep sheet.

It reuses the other tools' *pure* loaders/helpers and NEVER parses another tool's
formatted output. There is NO LLM and NO connection to Google/Outlook Calendar,
Gmail, Slack, Jira, Linear, Asana, or Trello — Phase 6 is local-only and CI-safe.
It also does NOT call the real Enterprise RAG pipeline: "relevant knowledge areas"
are inferred deterministically from labels, not retrieved from the corpus.

- Calendar : `office_agent.tools.calendar` (`load_events`, `next_meeting`,
             `find_conflicts`)
- Email    : `office_agent.tools.email.load_emails`
- Tickets  : `office_agent.tools.tickets` (`load_tickets`, `load_tasks`,
             `ASSIGNEE_ME`)

Meeting selection (deterministic, NO system clock):

- If the query mentions "next", the earliest-starting event (the calendar tool's
  `next_meeting`) is used.
- Otherwise the meeting whose title/labels best match the query's content words
  is selected (ties broken by earliest start).
- If nothing matches, it falls back to the next meeting.

All loaders return fresh copies, so the prep never mutates the mock data. Import
is side-effect-free (data is read lazily by the underlying loaders).
"""

from typing import Any

from office_agent.schemas import INTENT_MEETING_AGENT, ToolResult
from office_agent.tools import calendar, email, tickets

Event = dict[str, Any]
Item = dict[str, Any]

# Tool name recorded on the ToolResult / response for observability.
MEETING_TOOL_NAME = INTENT_MEETING_AGENT

# The identity that "me"/"my" resolves to (matches the ticket tool + mock data).
ASSIGNEE_ME = tickets.ASSIGNEE_ME

# How many relevant items to surface per section (keeps output concise).
_MAX_EMAILS = 3
_MAX_TICKETS_TASKS = 3
_MAX_FOLLOWUPS = 5
_MAX_AGENDA = 5
_MIN_AGENDA = 3

# Priorities treated as high/urgent.
_HIGH_PRIORITIES = ("high", "urgent")
# Ticket/task statuses treated as active (needing attention).
_ACTIVE_STATUSES = ("open", "blocked")

# Generic/function words + meeting jargon stripped before matching, so selection
# keys on domain words (vpn, security, expenses, ...) rather than boilerplate.
_STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "for",
        "of",
        "in",
        "on",
        "to",
        "with",
        "my",
        "me",
        "i",
        "do",
        "does",
        "have",
        "has",
        "what",
        "should",
        "is",
        "are",
        "be",
        "next",
        "this",
        "that",
        "about",
        "before",
        "after",
        "us",
        "you",
        "your",
        "can",
        "please",
        "help",
        "give",
        "show",
        "tell",
        # meeting jargon that recurs across many events / prep requests
        "meeting",
        "meetings",
        "prep",
        "prepare",
        "generate",
        "summarize",
        "context",
        "bring",
        "up",
        "review",
        "sync",
    }
)

# Deterministic label/word -> enterprise knowledge area map. Inferred, NOT
# retrieved: the Meeting Agent only *names* likely policy/domain areas so the
# user knows what to read; it never calls the RAG engine.
_KNOWLEDGE_AREA_BY_LABEL = {
    "vpn": "vpn_access",
    "security": "security",
    "incident": "incident_response",
    "on-call": "on_call_escalation",
    "expense": "expenses",
    "expenses": "expenses",
    "finance": "expenses",
    "onboarding": "onboarding",
    "hr": "onboarding",
    "retention": "data_retention",
    "compliance": "data_retention",
}


def _tokens(text: str) -> set[str]:
    """Lower-cased content words in `text` (stopwords and 1-char tokens dropped)."""

    raw = "".join(ch if ch.isalnum() else " " for ch in (text or "").casefold()).split()
    return {word for word in raw if len(word) > 1 and word not in _STOPWORDS}


def _labels_of(item: Item) -> set[str]:
    """Case-folded label set for an event/email/ticket/task."""

    return {str(label).casefold() for label in item.get("labels", [])}


def select_meeting(query: str, events: list[Event]) -> Event | None:
    """Deterministically pick the meeting a prep request refers to.

    "next" -> the earliest-starting event; otherwise the event whose title words
    and labels best overlap the query's content words (ties broken by earliest
    start); no match -> the next meeting. Returns None only for an empty calendar.
    """

    if not events:
        return None

    normalized = (query or "").casefold()
    if "next" in normalized:
        return calendar.next_meeting(events)

    query_tokens = _tokens(query)
    if query_tokens:
        scored = []
        for event in events:
            haystack = _tokens(str(event.get("title", ""))) | _labels_of(event)
            score = len(query_tokens & haystack)
            scored.append((score, event))
        best_score = max(score for score, _ in scored)
        if best_score > 0:
            # Highest overlap wins; earliest start breaks ties (deterministic).
            best = min(
                (pair for pair in scored if pair[0] == best_score),
                key=lambda pair: pair[1].get("start_at", ""),
            )
            return best[1]

    return calendar.next_meeting(events)


def _meeting_context(meeting: Event, query: str) -> set[str]:
    """Context word set used to score relevance: meeting labels + title + query."""

    return _labels_of(meeting) | _tokens(str(meeting.get("title", ""))) | _tokens(query)


def _overlap(item: Item, context: set[str]) -> int:
    """How many of an item's labels fall inside the meeting context."""

    return len(_labels_of(item) & context)


def _fmt_span(event: Event) -> str:
    """Compact time span, e.g. '2026-07-01 09:30-10:00'."""

    start = str(event.get("start_at", ""))
    end = str(event.get("end_at", ""))
    return f"{start[:16].replace('T', ' ')}-{end[11:16]}"


def _relevant_emails(context: set[str]) -> list[Item]:
    """Up to 3 relevant emails, high-importance/response-needed/unread/newest first."""

    scored = [(e, _overlap(e, context)) for e in email.load_emails()]
    relevant = [pair for pair in scored if pair[1] > 0]
    # Stable sorts, weakest key first: newest, then the priority signals.
    relevant.sort(key=lambda pair: pair[0].get("received_at", ""), reverse=True)
    relevant.sort(
        key=lambda pair: (
            -pair[1],
            0 if pair[0].get("importance") == "high" else 1,
            0 if pair[0].get("requires_response") else 1,
            0 if not pair[0].get("is_read", False) else 1,
        )
    )
    return [e for e, _score in relevant[:_MAX_EMAILS]]


def _relevant_work_items(context: set[str]) -> list[Item]:
    """Up to 3 relevant tickets/tasks, high-priority/active/mine/label-match first.

    Tickets and tasks are normalized into one list. `kind`, `mine`, and the
    original record are attached for rendering and follow-up derivation.
    """

    candidates: list[Item] = []
    for ticket in tickets.load_tickets():
        candidates.append(
            {
                "kind": "ticket",
                "id": ticket.get("id", "?"),
                "title": ticket.get("title", "(untitled)"),
                "status": ticket.get("status", "unknown"),
                "priority": ticket.get("priority", "normal"),
                "labels": ticket.get("labels", []),
                "linked_policy_area": ticket.get("linked_policy_area", ""),
                "mine": ticket.get("assignee") == ASSIGNEE_ME,
            }
        )
    for task in tickets.load_tasks():
        candidates.append(
            {
                "kind": "task",
                "id": task.get("id", "?"),
                "title": task.get("title", "(untitled)"),
                "status": task.get("status", "unknown"),
                "priority": task.get("priority", "normal"),
                "labels": task.get("labels", []),
                "linked_policy_area": "",
                "mine": task.get("owner") == ASSIGNEE_ME,
            }
        )

    scored = [(item, _overlap(item, context)) for item in candidates]
    relevant = [pair for pair in scored if pair[1] > 0]
    # Stable base order by id, then the priority signals on top.
    relevant.sort(key=lambda pair: str(pair[0]["id"]))
    relevant.sort(
        key=lambda pair: (
            -pair[1],
            0 if pair[0]["priority"] in _HIGH_PRIORITIES else 1,
            0 if pair[0]["status"] in _ACTIVE_STATUSES else 1,
            0 if pair[0]["mine"] else 1,
        )
    )
    return [item for item, _score in relevant[:_MAX_TICKETS_TASKS]]


def _knowledge_areas(context: set[str], work_items: list[Item]) -> list[str]:
    """Deterministic policy/domain labels inferred from context + relevant tickets.

    Inferred only — this NEVER calls the Enterprise RAG engine.
    """

    areas = {_KNOWLEDGE_AREA_BY_LABEL[word] for word in context if word in _KNOWLEDGE_AREA_BY_LABEL}
    for item in work_items:
        area = str(item.get("linked_policy_area", ""))
        if area:
            areas.add(area)
    return sorted(areas)


def _suggested_agenda(meeting: Event, emails: list[Item], work_items: list[Item]) -> list[str]:
    """3-5 deterministic agenda items derived from the meeting and its context."""

    title = str(meeting.get("title", "(untitled)"))
    blocked = [w for w in work_items if w["status"] == "blocked"]
    high = [w for w in work_items if w["priority"] in _HIGH_PRIORITIES]
    responses = [e for e in emails if e.get("requires_response", False)]

    agenda = [f"Review objectives for '{title}'."]
    if blocked:
        agenda.append("Review open blockers.")
    if high:
        agenda.append("Confirm owners for high-priority tickets.")
    if responses:
        agenda.append("Resolve response-needed emails.")
    if work_items:
        agenda.append("Align on follow-up tasks.")

    # Pad to the minimum with fixed, deterministic items; then cap.
    for filler in ("Confirm next steps and owners.", "Agree on a follow-up timeline."):
        if len(agenda) >= _MIN_AGENDA:
            break
        agenda.append(filler)
    return agenda[:_MAX_AGENDA]


def _risks(meeting: Event, events: list[Event], work_items: list[Item]) -> list[str]:
    """Schedule conflicts involving the selected meeting + relevant blocked tickets."""

    risks: list[str] = []
    meeting_id = meeting.get("id")
    for first, second in calendar.find_conflicts(events):
        if meeting_id in (first.get("id"), second.get("id")):
            other = second if first.get("id") == meeting_id else first
            risks.append(
                f"Schedule conflict: '{meeting.get('title', '(untitled)')}' overlaps "
                f"'{other.get('title', '(untitled)')}' ({_fmt_span(other)})."
            )
    for item in work_items:
        if item["status"] == "blocked":
            risks.append(f"Blocked {item['kind']} {item['id']}: {item['title']}.")

    return risks or ["No schedule conflicts or blockers detected."]


def _followups(emails: list[Item], work_items: list[Item]) -> list[str]:
    """Deterministic action items derived from the relevant emails/tickets/tasks."""

    followups: list[str] = []
    for message in emails:
        if message.get("requires_response", False):
            followups.append(
                f"Reply to '{message.get('subject', '(no subject)')}' "
                f"— {message.get('from', 'unknown')}."
            )
    for item in work_items:
        if item["priority"] in _HIGH_PRIORITIES or item["status"] == "blocked":
            followups.append(f"Advance {item['id']}: {item['title']}.")

    return (followups or ["No follow-ups identified."])[:_MAX_FOLLOWUPS]


def _meeting_section(meeting: Event) -> list[str]:
    attendees = ", ".join(str(a) for a in meeting.get("attendees", [])) or "—"
    labels = ", ".join(str(label) for label in meeting.get("labels", [])) or "—"
    return [
        "Meeting:",
        f"- Time: {_fmt_span(meeting)}",
        f"- Title: {meeting.get('title', '(untitled)')}",
        f"- Location: {meeting.get('location', '—')}",
        f"- Attendees: {attendees}",
        f"- Importance: {meeting.get('importance', 'normal')}",
        f"- Labels: {labels}",
    ]


def prepare_meeting(query: str) -> ToolResult:
    """Build a deterministic meeting-prep sheet for `query` and return a ToolResult.

    Selects a meeting (next / topic-matched / fallback), then derives relevant
    emails, tickets/tasks, inferred knowledge areas, a suggested agenda,
    risks/blockers, and recommended follow-ups — all from local mock data, with
    no LLM, no RAG call, and no external service. Identical on every run.
    """

    events = calendar.load_events()
    meeting = select_meeting(query, events)

    if meeting is None:
        return ToolResult(
            tool=MEETING_TOOL_NAME,
            content="Meeting Prep — no meetings found in the calendar.",
        )

    context = _meeting_context(meeting, query)
    emails = _relevant_emails(context)
    work_items = _relevant_work_items(context)
    areas = _knowledge_areas(context, work_items)

    sections: list[list[str]] = [
        [f"Meeting Prep — {meeting.get('title', '(untitled)')}"],
        _meeting_section(meeting),
    ]

    email_lines = ["Relevant emails:"]
    if emails:
        email_lines += [
            f"- {e.get('subject', '(no subject)')} — {e.get('from', 'unknown')}" for e in emails
        ]
    else:
        email_lines.append("- None.")
    sections.append(email_lines)

    work_lines = ["Relevant tickets/tasks:"]
    if work_items:
        work_lines += [
            f"- {item['id']}: {item['title']} "
            f"[{str(item['status']).upper()}/{str(item['priority']).upper()}]"
            for item in work_items
        ]
    else:
        work_lines.append("- None.")
    sections.append(work_lines)

    area_lines = ["Relevant knowledge areas:"]
    area_lines += [f"- {area}" for area in areas] if areas else ["- None inferred."]
    sections.append(area_lines)

    agenda = _suggested_agenda(meeting, emails, work_items)
    sections.append(
        ["Suggested agenda:"] + [f"{i}. {item}" for i, item in enumerate(agenda, start=1)]
    )

    sections.append(
        ["Risks / blockers:"] + [f"- {risk}" for risk in _risks(meeting, events, work_items)]
    )

    sections.append(
        ["Recommended follow-ups:"] + [f"- {item}" for item in _followups(emails, work_items)]
    )

    content = "\n\n".join("\n".join(section) for section in sections)
    return ToolResult(tool=MEETING_TOOL_NAME, content=content)
