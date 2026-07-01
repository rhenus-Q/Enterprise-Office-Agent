"""
office_agent.tools.tickets — deterministic mock Task / Ticket Assistant.

Reads a small, entirely fictional AcmeCorp ticket queue and task list from
`office_agent/mock_data/tickets.json` and `.../tasks.json` and produces concise,
deterministic summaries. There is NO LLM and NO connection to Jira/Linear/Asana/
Trello or any service — Phase 4 is local-only and CI-safe.

Supported query views (case-insensitive substring, first match wins):
`create` (simulate a task from a ticket), `blocked`, `open`,
`urgent`/`high`/`priority`, `assigned`/`my ticket` (assigned to me), `linked`
(tasks linked to tickets), `task(s)` (existing tasks), otherwise all tickets.

Task-creation is a *simulation*: `handle_ticket_request` NEVER writes to disk.
`build_simulated_task` is pure, and the source mock JSON files are immutable by
default. `create_task_from_ticket` exposes an optional `persist_path` seam for
tests only — it writes solely to the caller-provided path (e.g. pytest's
`tmp_path`) and never to the repo's `mock_data/` files.

Import is side-effect-free: the JSON files are read lazily on first use
(cached), never at import time.
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from office_agent.schemas import INTENT_TICKET_ASSISTANT, ToolResult

Ticket = dict[str, Any]
Task = dict[str, Any]

# Tool name recorded on the ToolResult / response for observability.
TICKET_TOOL_NAME = INTENT_TICKET_ASSISTANT

# The identity that "me"/"my" resolves to for the assigned-to-me view and for
# simulated task ownership. Matches the mock data.
ASSIGNEE_ME = "employee@acmecorp.example"

_TICKETS_PATH = Path(__file__).resolve().parent.parent / "mock_data" / "tickets.json"
_TASKS_PATH = Path(__file__).resolve().parent.parent / "mock_data" / "tasks.json"

_TICKET_ID_PATTERN = re.compile(r"tick-\d+", re.IGNORECASE)

# Human-readable label per view, shown in the summary header.
_VIEW_ALL = "all tickets"
_VIEW_OPEN = "open tickets"
_VIEW_BLOCKED = "blocked tickets"
_VIEW_URGENT = "high-priority tickets"
_VIEW_ASSIGNED = "assigned to me"
_VIEW_TASKS = "existing tasks"
_VIEW_LINKED = "tasks linked to tickets"
_VIEW_CREATE = "create task"

# Priorities treated as high-priority for the urgent view.
_HIGH_PRIORITIES = ("high", "urgent")


@lru_cache(maxsize=1)
def _read_tickets() -> tuple[Ticket, ...]:
    """Read and cache the raw mock ticket queue as an immutable tuple."""

    return tuple(json.loads(_TICKETS_PATH.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def _read_tasks() -> tuple[Task, ...]:
    """Read and cache the raw mock task list as an immutable tuple."""

    return tuple(json.loads(_TASKS_PATH.read_text(encoding="utf-8")))


def load_tickets() -> list[Ticket]:
    """Return a fresh copy of the mock tickets (callers may filter/sort freely)."""

    return [dict(ticket) for ticket in _read_tickets()]


def load_tasks() -> list[Task]:
    """Return a fresh copy of the mock tasks (callers may filter/sort freely)."""

    return [dict(task) for task in _read_tasks()]


def find_ticket(ticket_id: str) -> Ticket | None:
    """Return the ticket with `ticket_id` (case-insensitive), or None."""

    wanted = (ticket_id or "").strip().upper()
    for ticket in load_tickets():
        if str(ticket.get("id", "")).upper() == wanted:
            return ticket
    return None


def build_simulated_task(ticket: Ticket) -> Task:
    """Build a deterministic simulated follow-up task from a ticket (pure).

    No wall-clock is used — timestamps mirror the source ticket — so the same
    ticket always yields the same task. Nothing is persisted here.
    """

    ticket_id = str(ticket.get("id", ""))
    return {
        "id": f"TASK-SIM-{ticket_id}",
        "title": f"Follow up on {ticket.get('title', '(untitled)')}",
        "description": f"Auto-created follow-up task for ticket {ticket_id}.",
        "status": "open",
        "priority": ticket.get("priority", "normal"),
        "source_ticket_id": ticket_id,
        "owner": ASSIGNEE_ME,
        "created_at": ticket.get("created_at", ""),
        "due_at": ticket.get("due_at", ""),
        "labels": list(ticket.get("labels", [])),
    }


def create_task_from_ticket(ticket_id: str, *, persist_path: Path | None = None) -> Task | None:
    """Create a simulated task from a ticket id; return None if unknown.

    Persistence is opt-in and test-only: when `persist_path` is given the task
    is appended to THAT file (e.g. pytest `tmp_path`). With the default
    `persist_path=None` nothing is written, and the repo's `mock_data/` files
    are never touched.
    """

    ticket = find_ticket(ticket_id)
    if ticket is None:
        return None

    task = build_simulated_task(ticket)
    if persist_path is not None:
        _append_task(task, persist_path)
    return task


def _append_task(task: Task, path: Path) -> None:
    """Append a task to a JSON-list file at `path` (creating it if needed)."""

    path = Path(path)
    existing: list[Task] = []
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    existing.append(task)
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def _resolve_ticket_from_query(query: str) -> Ticket | None:
    """Find the ticket a create-request refers to (by explicit id, else label).

    An explicit `TICK-<n>` id wins (and an unknown id resolves to None, safely).
    Otherwise the first ticket (by id order) whose label appears in the query is
    used, so "the VPN ticket" maps to a vpn-labelled ticket deterministically.
    """

    normalized = (query or "").casefold()

    match = _TICKET_ID_PATTERN.search(normalized)
    if match:
        return find_ticket(match.group(0))

    for ticket in sorted(load_tickets(), key=lambda item: str(item.get("id", ""))):
        labels = [str(label).casefold() for label in ticket.get("labels", [])]
        if any(label and label in normalized for label in labels):
            return ticket
    return None


def _select_view(query: str) -> str:
    """Map a free-text query to one view label (deterministic precedence)."""

    normalized = (query or "").casefold()
    if "create" in normalized:
        return _VIEW_CREATE
    if "blocked" in normalized:
        return _VIEW_BLOCKED
    if "open" in normalized:
        return _VIEW_OPEN
    if any(word in normalized for word in ("urgent", "high", "priority", "important")):
        return _VIEW_URGENT
    if "assigned" in normalized or "my ticket" in normalized:
        return _VIEW_ASSIGNED
    if "linked" in normalized:
        return _VIEW_LINKED
    if "task" in normalized:
        return _VIEW_TASKS
    return _VIEW_ALL


def filter_tickets(view: str) -> list[Ticket]:
    """Return the tickets matching a ticket view, sorted by id (deterministic)."""

    tickets = load_tickets()
    if view == _VIEW_OPEN:
        matched = [t for t in tickets if t.get("status") == "open"]
    elif view == _VIEW_BLOCKED:
        matched = [t for t in tickets if t.get("status") == "blocked"]
    elif view == _VIEW_URGENT:
        matched = [t for t in tickets if t.get("priority") in _HIGH_PRIORITIES]
    elif view == _VIEW_ASSIGNED:
        matched = [t for t in tickets if t.get("assignee") == ASSIGNEE_ME]
    else:
        matched = list(tickets)
    matched.sort(key=lambda item: str(item.get("id", "")))
    return matched


def _ticket_bullet(ticket: Ticket) -> str:
    """One concise bullet line for a ticket."""

    status = str(ticket.get("status", "unknown")).upper()
    priority = str(ticket.get("priority", "normal")).upper()
    return (
        f"- [{status}] [{priority}] {ticket.get('id', '?')}: {ticket.get('title', '(untitled)')} "
        f"— assignee {ticket.get('assignee', 'unassigned')}"
    )


def _task_bullet(task: Task) -> str:
    """One concise bullet line for a task."""

    status = str(task.get("status", "unknown")).upper()
    priority = str(task.get("priority", "normal")).upper()
    source = task.get("source_ticket_id") or "none"
    return (
        f"- [{status}] [{priority}] {task.get('id', '?')}: {task.get('title', '(untitled)')} "
        f"(from {source})"
    )


def _render_tickets(label: str, tickets: list[Ticket]) -> ToolResult:
    total = len(load_tickets())
    lines = [f"Tickets — {label}: {len(tickets)} of {total} ticket(s)."]
    if not tickets:
        lines += ["", "No matching tickets."]
    else:
        lines += ["", "Tickets:"]
        lines += [_ticket_bullet(ticket) for ticket in tickets]
    return ToolResult(tool=TICKET_TOOL_NAME, content="\n".join(lines))


def _render_tasks(label: str, tasks: list[Task]) -> ToolResult:
    total = len(load_tasks())
    lines = [f"Tasks — {label}: {len(tasks)} of {total} task(s)."]
    if not tasks:
        lines += ["", "No matching tasks."]
    else:
        lines += ["", "Tasks:"]
        lines += [_task_bullet(task) for task in tasks]
    return ToolResult(tool=TICKET_TOOL_NAME, content="\n".join(lines))


def _render_create(query: str) -> ToolResult:
    ticket = _resolve_ticket_from_query(query)
    if ticket is None:
        lines = [
            "Ticket assistant — create task: no matching ticket found.",
            "",
            'Tell me which ticket, e.g. "create a task from TICK-001".',
        ]
        return ToolResult(tool=TICKET_TOOL_NAME, content="\n".join(lines))

    task = build_simulated_task(ticket)
    lines = [
        f"Ticket assistant — created a follow-up task (simulated) from {ticket.get('id', '?')}.",
        "",
        "Created task:",
        f"- {task['id']}: {task['title']}",
        f"  status: {task['status']}, priority: {task['priority']}, owner: {task['owner']}",
        f"  source ticket: {task['source_ticket_id']}",
        "",
        "Note: simulated only — not saved to any system.",
    ]
    return ToolResult(tool=TICKET_TOOL_NAME, content="\n".join(lines))


def handle_ticket_request(query: str) -> ToolResult:
    """Summarize tickets/tasks or simulate task creation for `query`.

    Deterministic and read-only: every view is a pure filter over the mock data,
    and the `create` view returns a simulated task without writing anything.
    """

    view = _select_view(query)

    if view == _VIEW_CREATE:
        return _render_create(query)
    if view == _VIEW_TASKS:
        return _render_tasks(_VIEW_TASKS, load_tasks())
    if view == _VIEW_LINKED:
        linked = [task for task in load_tasks() if task.get("source_ticket_id")]
        return _render_tasks(_VIEW_LINKED, linked)

    return _render_tickets(view, filter_tickets(view))
