"""
Unit tests for the mock Task / Ticket Assistant (office_agent/tools/tickets.py).

Fully local and deterministic: the tool reads static fictional JSON from
office_agent/mock_data/ — no OpenAI/Tavily/Chroma and no ticketing service.
Task creation is simulated; the persistence seam is exercised only against
pytest's tmp_path, never the repo mock_data files.
"""

import json

from office_agent.schemas import INTENT_TICKET_ASSISTANT
from office_agent.tools import tickets

TICKET_FIELDS = {
    "id",
    "title",
    "description",
    "status",
    "priority",
    "assignee",
    "requester",
    "created_at",
    "due_at",
    "labels",
    "linked_policy_area",
}

TASK_FIELDS = {
    "id",
    "title",
    "description",
    "status",
    "priority",
    "source_ticket_id",
    "owner",
    "created_at",
    "due_at",
    "labels",
}


def test_load_tickets_returns_realistic_dataset():
    all_tickets = tickets.load_tickets()

    assert 8 <= len(all_tickets) <= 12
    for ticket in all_tickets:
        assert TICKET_FIELDS <= set(ticket)

    assert sum(1 for t in all_tickets if t["status"] == "open") >= 3
    assert sum(1 for t in all_tickets if t["priority"] in ("high", "urgent")) >= 2
    assert sum(1 for t in all_tickets if t["assignee"] == tickets.ASSIGNEE_ME) >= 2
    assert sum(1 for t in all_tickets if t["status"] == "blocked") >= 1
    assert sum(1 for t in all_tickets if t["status"] == "closed") >= 1
    assert any({"vpn", "security"} & set(t["labels"]) for t in all_tickets)
    assert any("expenses" in t["labels"] for t in all_tickets)


def test_load_tasks_returns_realistic_dataset():
    all_tasks = tickets.load_tasks()

    assert 4 <= len(all_tasks) <= 6
    for task in all_tasks:
        assert TASK_FIELDS <= set(task)
    assert any(t.get("source_ticket_id") for t in all_tasks)


def test_loaders_return_independent_copies():
    first_ticket = tickets.load_tickets()
    first_ticket[0]["title"] = "MUTATED"
    assert tickets.load_tickets()[0]["title"] != "MUTATED"

    first_task = tickets.load_tasks()
    first_task[0]["title"] = "MUTATED"
    assert tickets.load_tasks()[0]["title"] != "MUTATED"


def test_summarize_all_tickets():
    total = len(tickets.load_tickets())
    result = tickets.handle_ticket_request("summarize all tickets")

    assert result.tool == INTENT_TICKET_ASSISTANT
    assert f"{total} of {total}" in result.content


def test_summarize_open_tickets():
    expected = [t for t in tickets.load_tickets() if t["status"] == "open"]
    matched = tickets.filter_tickets("open tickets")

    assert {t["id"] for t in matched} == {t["id"] for t in expected}
    assert all(t["status"] == "open" for t in matched)


def test_summarize_urgent_tickets():
    expected = [t for t in tickets.load_tickets() if t["priority"] in ("high", "urgent")]
    matched = tickets.filter_tickets("high-priority tickets")

    assert {t["id"] for t in matched} == {t["id"] for t in expected}
    result = tickets.handle_ticket_request("summarize urgent tickets")
    assert "high-priority tickets" in result.content


def test_summarize_blocked_tickets():
    expected = [t for t in tickets.load_tickets() if t["status"] == "blocked"]
    matched = tickets.filter_tickets("blocked tickets")

    assert {t["id"] for t in matched} == {t["id"] for t in expected}
    assert matched  # the spec dataset has at least one blocked ticket


def test_summarize_tickets_assigned_to_me():
    expected = [t for t in tickets.load_tickets() if t["assignee"] == tickets.ASSIGNEE_ME]
    matched = tickets.filter_tickets("assigned to me")

    assert {t["id"] for t in matched} == {t["id"] for t in expected}
    assert all(t["assignee"] == tickets.ASSIGNEE_ME for t in matched)
    result = tickets.handle_ticket_request("which tickets are assigned to me?")
    assert "assigned to me" in result.content


def test_summarize_existing_tasks():
    total_tasks = len(tickets.load_tasks())
    result = tickets.handle_ticket_request("show my tasks")

    assert result.tool == INTENT_TICKET_ASSISTANT
    assert "existing tasks" in result.content
    assert f"of {total_tasks} task(s)" in result.content


def test_creates_deterministic_simulated_task_from_ticket_id():
    result = tickets.handle_ticket_request("create a task from TICK-001")

    assert "TASK-SIM-TICK-001" in result.content
    assert "simulated only" in result.content

    # Deterministic and pure — same ticket always yields the same task.
    ticket = tickets.find_ticket("TICK-001")
    task_a = tickets.build_simulated_task(ticket)
    task_b = tickets.build_simulated_task(ticket)
    assert task_a == task_b
    assert task_a["id"] == "TASK-SIM-TICK-001"
    assert task_a["source_ticket_id"] == "TICK-001"
    assert task_a["owner"] == tickets.ASSIGNEE_ME


def test_create_task_resolves_ticket_by_label():
    # "the VPN ticket" (no explicit id) resolves to a vpn-labelled ticket.
    result = tickets.handle_ticket_request("create a follow-up task for the VPN ticket")
    assert "Created task:" in result.content
    assert "TASK-SIM-" in result.content


def test_create_task_handles_unknown_ticket_id_safely():
    result = tickets.handle_ticket_request("create a task from TICK-999")

    assert "no matching ticket found" in result.content
    assert tickets.create_task_from_ticket("TICK-999") is None


def test_persistence_seam_writes_only_to_given_path(tmp_path):
    target = tmp_path / "created_tasks.json"

    baseline_task_count = len(tickets.load_tasks())

    task = tickets.create_task_from_ticket("TICK-001", persist_path=target)

    assert task is not None
    assert target.exists()
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved[0]["id"] == "TASK-SIM-TICK-001"

    # The repo mock_data tasks file is never touched by the seam.
    assert len(tickets.load_tasks()) == baseline_task_count
    assert not any(t["id"] == "TASK-SIM-TICK-001" for t in tickets.load_tasks())
