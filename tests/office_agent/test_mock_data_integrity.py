"""
Cross-file referential-integrity tests for the Office Agent mock datasets.

Fully local and deterministic: these tests only read the static fictional JSON
under office_agent/mock_data/ via the pure loaders — no OpenAI/Tavily/Chroma,
no external services, and no Enterprise RAG call.

They guard the *structural* relationships between datasets (unique ids, valid
cross-file references, and internally consistent approval → ticket → task
chains) so that a stale or inconsistent link is caught in CI. In particular,
check 5 (`test_approval_ticket_task_chain_is_consistent`) reproduces the class
of defect where an approval linked to one ticket but to a task belonging to a
different ticket (e.g. APR-005 → TICK-005 while pointing at TASK-002 → TICK-002).

The checks are generic over all current and future records: no individual id,
record count, or semantic word-match is hardcoded.
"""

import pytest

from office_agent.tools import approvals, calendar, email, tickets

# (dataset label, loader) pairs — one row per mock collection with an `id`.
_ID_DATASETS = [
    ("approvals", approvals.load_approvals),
    ("audit events", approvals.load_audit_log),
    ("tickets", tickets.load_tickets),
    ("tasks", tickets.load_tasks),
    ("emails", email.load_emails),
    ("calendar events", calendar.load_events),
]


@pytest.mark.parametrize(
    "dataset_label, loader",
    _ID_DATASETS,
    ids=[label.replace(" ", "_") for label, _ in _ID_DATASETS],
)
def test_ids_are_unique_within_dataset(dataset_label, loader):
    """Every record in each mock collection must carry a unique `id`."""

    seen: set[str] = set()
    duplicates: list[str] = []
    for record in loader():
        record_id = record.get("id")
        if record_id in seen:
            duplicates.append(str(record_id))
        else:
            seen.add(record_id)

    assert not duplicates, f"Duplicate id(s) in {dataset_label} dataset: {sorted(duplicates)}"


def test_approval_linked_tickets_exist():
    """Every approval's non-null `linked_ticket_id` must resolve to a real ticket."""

    ticket_ids = {ticket["id"] for ticket in tickets.load_tickets()}
    for approval in approvals.load_approvals():
        linked_ticket_id = approval.get("linked_ticket_id")
        if linked_ticket_id is None:
            continue
        assert linked_ticket_id in ticket_ids, (
            f"Approval {approval.get('id')} references missing linked_ticket_id {linked_ticket_id}"
        )


def test_approval_linked_tasks_exist():
    """Every approval's non-null `linked_task_id` must resolve to a real task."""

    task_ids = {task["id"] for task in tickets.load_tasks()}
    for approval in approvals.load_approvals():
        linked_task_id = approval.get("linked_task_id")
        if linked_task_id is None:
            continue
        assert linked_task_id in task_ids, (
            f"Approval {approval.get('id')} references missing linked_task_id {linked_task_id}"
        )


def test_task_source_tickets_exist():
    """Every task's non-null `source_ticket_id` must resolve to a real ticket."""

    ticket_ids = {ticket["id"] for ticket in tickets.load_tickets()}
    for task in tickets.load_tasks():
        source_ticket_id = task.get("source_ticket_id")
        if source_ticket_id is None:
            continue
        assert source_ticket_id in ticket_ids, (
            f"Task {task.get('id')} references missing source_ticket_id {source_ticket_id}"
        )


def test_approval_ticket_task_chain_is_consistent():
    """An approval linked to both a ticket and a task must agree on the ticket.

    When an approval carries a non-null `linked_ticket_id` and a non-null
    `linked_task_id`, the linked task's `source_ticket_id` must equal the
    approval's `linked_ticket_id`. This catches defects like
    APR-005 → TICK-005 while pointing at TASK-002 (whose source is TICK-002).
    """

    tasks_by_id = {task["id"]: task for task in tickets.load_tasks()}
    for approval in approvals.load_approvals():
        linked_ticket_id = approval.get("linked_ticket_id")
        linked_task_id = approval.get("linked_task_id")
        if linked_ticket_id is None or linked_task_id is None:
            continue
        # Missing linked tasks are reported by test_approval_linked_tasks_exist.
        linked_task = tasks_by_id.get(linked_task_id)
        if linked_task is None:
            continue
        task_source_ticket_id = linked_task.get("source_ticket_id")
        assert task_source_ticket_id == linked_ticket_id, (
            f"Approval {approval.get('id')} links ticket {linked_ticket_id} "
            f"but its linked task {linked_task_id} has source ticket "
            f"{task_source_ticket_id}"
        )


def test_audit_events_reference_real_approvals():
    """Every audit event's `approval_id` must resolve to a real approval."""

    approval_ids = {approval["id"] for approval in approvals.load_approvals()}
    for event in approvals.load_audit_log():
        approval_id = event.get("approval_id")
        assert approval_id in approval_ids, (
            f"Audit event {event.get('id')} references missing approval_id {approval_id}"
        )
