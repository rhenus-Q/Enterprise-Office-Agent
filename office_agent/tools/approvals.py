"""
office_agent.tools.approvals — deterministic mock Workflow / Approval Agent.

Reads an entirely fictional AcmeCorp approval queue and audit log from
`office_agent/mock_data/approvals.json` and `.../audit_log.json` and produces
concise, deterministic summaries. There is NO LLM and NO connection to Jira /
Linear / Asana / Trello / Slack / Gmail / Outlook / Google Calendar or any
service — Phase 7 (Office Agent v1.6) is local-only and CI-safe. It never calls
the Enterprise RAG engine.

Supported views (case-insensitive; deterministic precedence in `_select_view`):
`approve APR-001` / `reject APR-002` (simulate a decision), `create a follow-up
task for APR-001` (simulate a task), `audit log for APR-001`, status for a
specific id (any `APR-<n>`), `pending`, `assigned` (to me), `urgent`/`high`,
`approved`, `rejected`, a topic filter (e.g. "expense approvals", "VPN
approvals"), otherwise all approvals.

Simulated actions are exactly that: `handle_approval_request` NEVER writes to
disk, and the source mock JSON files are immutable by default.
`build_simulated_decision` and `build_simulated_followup_task` are pure (no
wall-clock — timestamps mirror the source approval), so the same request always
yields the same result. `record_decision` exposes an optional `persist_path`
seam for tests only — it writes solely to the caller-provided path (e.g. pytest's
`tmp_path`) and never to the repo's `mock_data/` files.

Import is side-effect-free: the JSON files are read lazily on first use (cached),
never at import time.
"""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from office_agent.schemas import INTENT_WORKFLOW_APPROVAL, ToolResult
from office_agent.tools import tickets

Approval = dict[str, Any]
AuditEvent = dict[str, Any]

# Tool name recorded on the ToolResult / response for observability.
APPROVAL_TOOL_NAME = INTENT_WORKFLOW_APPROVAL

# The identity that "me"/"my" resolves to (matches the ticket tool + mock data).
ASSIGNEE_ME = tickets.ASSIGNEE_ME

_APPROVALS_PATH = Path(__file__).resolve().parent.parent / "mock_data" / "approvals.json"
_AUDIT_LOG_PATH = Path(__file__).resolve().parent.parent / "mock_data" / "audit_log.json"

_APPROVAL_ID_PATTERN = re.compile(r"apr-\d+", re.IGNORECASE)

# Priorities treated as high-priority / urgent.
_HIGH_PRIORITIES = ("high", "urgent")

# How many bullets to show in a list view (keeps output concise).
_MAX_BULLETS = 10

# View labels (also shown in the summary header).
_VIEW_APPROVE = "approve"
_VIEW_REJECT = "reject"
_VIEW_CREATE_TASK = "create_task"
_VIEW_AUDIT = "audit"
_VIEW_STATUS = "status"
_VIEW_PENDING = "pending approvals"
_VIEW_ASSIGNED = "assigned to me"
_VIEW_HIGH = "high-priority approvals"
_VIEW_APPROVED = "approved approvals"
_VIEW_REJECTED = "rejected approvals"
_VIEW_TOPIC = "topic approvals"
_VIEW_ALL = "all approvals"

# Topic words -> the label/policy signal they filter on. Lets "show expense
# approvals" / "show VPN approvals" narrow the queue deterministically.
_TOPIC_TERMS = (
    "expense",
    "reimbursement",
    "vpn",
    "security",
    "onboarding",
    "incident",
    "on-call",
    "retention",
    "compliance",
    "procurement",
    "travel",
)


@lru_cache(maxsize=1)
def _read_approvals() -> tuple[Approval, ...]:
    """Read and cache the raw mock approval queue as an immutable tuple."""

    return tuple(json.loads(_APPROVALS_PATH.read_text(encoding="utf-8")))


@lru_cache(maxsize=1)
def _read_audit_log() -> tuple[AuditEvent, ...]:
    """Read and cache the raw mock audit log as an immutable tuple."""

    return tuple(json.loads(_AUDIT_LOG_PATH.read_text(encoding="utf-8")))


def load_approvals() -> list[Approval]:
    """Return a fresh copy of the mock approvals (callers may filter/sort freely)."""

    return [dict(approval) for approval in _read_approvals()]


def load_audit_log() -> list[AuditEvent]:
    """Return a fresh copy of the mock audit log (callers may filter/sort freely)."""

    return [dict(event) for event in _read_audit_log()]


def find_approval(approval_id: str) -> Approval | None:
    """Return the approval with `approval_id` (case-insensitive), or None."""

    wanted = (approval_id or "").strip().upper()
    for approval in load_approvals():
        if str(approval.get("id", "")).upper() == wanted:
            return approval
    return None


def audit_events_for(approval_id: str) -> list[AuditEvent]:
    """Return the audit events for an approval, sorted by timestamp (deterministic)."""

    wanted = (approval_id or "").strip().upper()
    events = [e for e in load_audit_log() if str(e.get("approval_id", "")).upper() == wanted]
    events.sort(key=lambda e: str(e.get("timestamp", "")))
    return events


def build_simulated_decision(approval: Approval, action: str) -> AuditEvent:
    """Build a deterministic simulated approve/reject audit event (pure).

    No wall-clock is used — the timestamp mirrors the approval's `due_at` — so the
    same approval + action always yields the same event. Nothing is persisted.
    """

    approval_id = str(approval.get("id", ""))
    new_status = "approved" if action == _VIEW_APPROVE else "rejected"
    return {
        "id": f"AUD-SIM-{approval_id}-{new_status}",
        "approval_id": approval_id,
        "action": new_status,
        "actor": ASSIGNEE_ME,
        "timestamp": approval.get("due_at", ""),
        "note": f"Simulated {action} of {approval_id}.",
        "previous_status": approval.get("status", "unknown"),
        "new_status": new_status,
    }


def build_simulated_followup_task(approval: Approval) -> dict[str, Any]:
    """Build a deterministic simulated follow-up task from an approval (pure)."""

    approval_id = str(approval.get("id", ""))
    return {
        "id": f"TASK-SIM-{approval_id}",
        "title": f"Follow up on {approval.get('title', '(untitled)')}",
        "description": f"Auto-created follow-up task for approval {approval_id}.",
        "status": "open",
        "priority": approval.get("priority", "normal"),
        "source_approval_id": approval_id,
        "owner": ASSIGNEE_ME,
        "created_at": approval.get("created_at", ""),
        "due_at": approval.get("due_at", ""),
        "labels": list(approval.get("labels", [])),
    }


def record_decision(
    approval_id: str, action: str, *, persist_path: Path | None = None
) -> AuditEvent | None:
    """Simulate a decision on an approval; return None if the id is unknown.

    Persistence is opt-in and test-only: when `persist_path` is given the
    simulated audit event is appended to THAT file (e.g. pytest `tmp_path`). With
    the default `persist_path=None` nothing is written, and the repo's
    `mock_data/` files are never touched.
    """

    approval = find_approval(approval_id)
    if approval is None:
        return None

    event = build_simulated_decision(approval, action)
    if persist_path is not None:
        _append_json(event, persist_path)
    return event


def _append_json(record: dict[str, Any], path: Path) -> None:
    """Append a record to a JSON-list file at `path` (creating it if needed)."""

    path = Path(path)
    existing: list[dict[str, Any]] = []
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    existing.append(record)
    path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def _extract_approval_id(query: str) -> str | None:
    """Return the first explicit approval id in `query` (upper-cased), or None."""

    match = _APPROVAL_ID_PATTERN.search(query or "")
    return match.group(0).upper() if match else None


def _select_view(query: str, approval_id: str | None) -> str:
    """Map a free-text query to one view label (deterministic precedence)."""

    normalized = (query or "").casefold()

    if approval_id is not None:
        # Actions require an explicit id, which keeps them distinct from the
        # "approved"/"rejected" list views (those carry no id).
        if "approve" in normalized:
            return _VIEW_APPROVE
        if "reject" in normalized:
            return _VIEW_REJECT
        if "follow-up" in normalized or "follow up" in normalized or "task" in normalized:
            return _VIEW_CREATE_TASK
        if "audit" in normalized:
            return _VIEW_AUDIT
        return _VIEW_STATUS

    if "pending" in normalized:
        return _VIEW_PENDING
    if "assigned" in normalized or "assigned to me" in normalized or "my approval" in normalized:
        return _VIEW_ASSIGNED
    if any(word in normalized for word in ("urgent", "high", "priority", "important")):
        return _VIEW_HIGH
    if "approved" in normalized:
        return _VIEW_APPROVED
    if "rejected" in normalized:
        return _VIEW_REJECTED
    if any(term in normalized for term in _TOPIC_TERMS):
        return _VIEW_TOPIC
    return _VIEW_ALL


def _matches_topic(approval: Approval, normalized_query: str) -> bool:
    """True if the approval's labels / policy area match a topic term in the query."""

    haystack = {str(label).casefold() for label in approval.get("labels", [])}
    haystack.add(str(approval.get("policy_area", "")).casefold())
    haystack.add(str(approval.get("request_type", "")).casefold())
    for term in _TOPIC_TERMS:
        if term in normalized_query and any(term in item for item in haystack):
            return True
    return False


def filter_approvals(view: str, query: str = "") -> list[Approval]:
    """Return the approvals matching a list view, sorted by id (deterministic)."""

    approvals = load_approvals()
    if view == _VIEW_PENDING:
        matched = [a for a in approvals if a.get("status") == "pending"]
    elif view == _VIEW_ASSIGNED:
        matched = [a for a in approvals if a.get("approver") == ASSIGNEE_ME]
    elif view == _VIEW_HIGH:
        matched = [a for a in approvals if a.get("priority") in _HIGH_PRIORITIES]
    elif view == _VIEW_APPROVED:
        matched = [a for a in approvals if a.get("status") == "approved"]
    elif view == _VIEW_REJECTED:
        matched = [a for a in approvals if a.get("status") == "rejected"]
    elif view == _VIEW_TOPIC:
        normalized = (query or "").casefold()
        matched = [a for a in approvals if _matches_topic(a, normalized)]
    else:
        matched = list(approvals)
    matched.sort(key=lambda item: str(item.get("id", "")))
    return matched


def _approval_bullet(approval: Approval) -> str:
    """One concise bullet line for an approval."""

    status = str(approval.get("status", "unknown")).upper()
    priority = str(approval.get("priority", "normal")).upper()
    return (
        f"- [{status}] [{priority}] {approval.get('id', '?')}: "
        f"{approval.get('title', '(untitled)')} — approver {approval.get('approver', 'unassigned')}"
    )


def _render_list(view: str, approvals: list[Approval]) -> ToolResult:
    total = len(load_approvals())
    lines = [f"Approvals — {view}: {len(approvals)} of {total} approval(s)."]
    if not approvals:
        lines += ["", "No matching approvals."]
    else:
        lines += ["", "Approvals:"]
        lines += [_approval_bullet(a) for a in approvals[:_MAX_BULLETS]]
        if len(approvals) > _MAX_BULLETS:
            lines.append(f"- … and {len(approvals) - _MAX_BULLETS} more.")
    return ToolResult(tool=APPROVAL_TOOL_NAME, content="\n".join(lines))


def _fmt_amount(approval: Approval) -> str:
    """Amount + currency, or '—' when the approval has no monetary amount."""

    amount = approval.get("amount")
    if amount is None:
        return "—"
    currency = approval.get("currency") or ""
    return f"{amount} {currency}".strip()


def _render_status(approval_id: str) -> ToolResult:
    approval = find_approval(approval_id)
    if approval is None:
        lines = [
            f"Workflow / Approval — no approval found for {approval_id}.",
            "",
            'Tell me a known approval id, e.g. "what is the status of APR-001?".',
        ]
        return ToolResult(tool=APPROVAL_TOOL_NAME, content="\n".join(lines))

    lines = [
        f"Approval status — {approval.get('id', '?')}: {approval.get('title', '(untitled)')}",
        "",
        f"- Status: {str(approval.get('status', 'unknown')).upper()}",
        f"- Priority: {str(approval.get('priority', 'normal')).upper()}",
        f"- Requester: {approval.get('requester', 'unknown')}",
        f"- Approver (owner): {approval.get('approver', 'unassigned')}",
        f"- Due: {approval.get('due_at', '—')}",
        f"- Amount: {_fmt_amount(approval)}",
        f"- Linked ticket: {approval.get('linked_ticket_id') or 'none'}",
        f"- Linked task: {approval.get('linked_task_id') or 'none'}",
        f"- Policy area: {approval.get('policy_area', '—')}",
    ]
    return ToolResult(tool=APPROVAL_TOOL_NAME, content="\n".join(lines))


def _render_decision(approval_id: str, action: str) -> ToolResult:
    approval = find_approval(approval_id)
    if approval is None:
        lines = [
            f"Workflow / Approval — cannot {action}: no approval found for {approval_id}.",
        ]
        return ToolResult(tool=APPROVAL_TOOL_NAME, content="\n".join(lines))

    event = build_simulated_decision(approval, action)
    lines = [
        f"Workflow / Approval — {action} {approval.get('id', '?')} (simulated).",
        "",
        "Simulated action:",
        f"- Approval: {approval.get('id', '?')}: {approval.get('title', '(untitled)')}",
        f"- Status change: {event['previous_status'].upper()} -> {event['new_status'].upper()}",
        f"- Actor: {event['actor']}",
        f"- Recorded at: {event['timestamp'] or '—'}",
        f"- Note: {event['note']}",
        "",
        "Note: simulated only — mock data is unchanged and nothing was saved.",
    ]
    return ToolResult(tool=APPROVAL_TOOL_NAME, content="\n".join(lines))


def _render_create_task(approval_id: str) -> ToolResult:
    approval = find_approval(approval_id)
    if approval is None:
        lines = [
            f"Workflow / Approval — cannot create a follow-up task: "
            f"no approval found for {approval_id}.",
        ]
        return ToolResult(tool=APPROVAL_TOOL_NAME, content="\n".join(lines))

    task = build_simulated_followup_task(approval)
    lines = [
        f"Workflow / Approval — created a follow-up task (simulated) for {approval.get('id', '?')}.",
        "",
        "Simulated follow-up task:",
        f"- {task['id']}: {task['title']}",
        f"  status: {task['status']}, priority: {task['priority']}, owner: {task['owner']}",
        f"  source approval: {task['source_approval_id']}",
        "",
        "Note: simulated only — not saved to any system.",
    ]
    return ToolResult(tool=APPROVAL_TOOL_NAME, content="\n".join(lines))


def _render_audit(approval_id: str) -> ToolResult:
    approval = find_approval(approval_id)
    if approval is None:
        lines = [f"Workflow / Approval — no approval found for {approval_id}."]
        return ToolResult(tool=APPROVAL_TOOL_NAME, content="\n".join(lines))

    events = audit_events_for(approval_id)
    lines = [f"Audit log — {approval_id}: {len(events)} event(s)."]
    if not events:
        lines += ["", "No audit events recorded."]
    else:
        lines += ["", "Events:"]
        lines += [
            f"- {e.get('timestamp', '?')} [{str(e.get('action', 'event')).upper()}] "
            f"{e.get('actor', 'unknown')}: {e.get('note', '')}"
            for e in events
        ]
    return ToolResult(tool=APPROVAL_TOOL_NAME, content="\n".join(lines))


def handle_approval_request(query: str) -> ToolResult:
    """Summarize approvals or simulate a workflow action for `query`.

    Deterministic and read-only: every list/status view is a pure filter over the
    mock data, and the approve/reject/create-task views return simulated results
    without writing anything. Never calls an LLM or any external service.
    """

    approval_id = _extract_approval_id(query)
    view = _select_view(query, approval_id)

    if view == _VIEW_APPROVE:
        assert approval_id is not None  # _select_view only returns this with an id
        return _render_decision(approval_id, _VIEW_APPROVE)
    if view == _VIEW_REJECT:
        assert approval_id is not None
        return _render_decision(approval_id, _VIEW_REJECT)
    if view == _VIEW_CREATE_TASK:
        assert approval_id is not None
        return _render_create_task(approval_id)
    if view == _VIEW_AUDIT:
        assert approval_id is not None
        return _render_audit(approval_id)
    if view == _VIEW_STATUS:
        assert approval_id is not None
        return _render_status(approval_id)

    return _render_list(view, filter_approvals(view, query))
