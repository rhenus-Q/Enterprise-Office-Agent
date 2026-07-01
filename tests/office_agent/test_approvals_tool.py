"""
Unit tests for the mock Workflow / Approval Agent (office_agent/tools/approvals.py).

Fully local and deterministic: the tool reads static fictional JSON from
office_agent/mock_data/ — no OpenAI/Tavily/Chroma, no Jira/Linear/Asana/Trello/
Slack/Gmail/Outlook, and no call to the real Enterprise RAG pipeline. Simulated
actions are computed in the response; the persistence seam is exercised only
against pytest's tmp_path, never the repo mock_data files.
"""

import json

from office_agent.schemas import INTENT_WORKFLOW_APPROVAL
from office_agent.tools import approvals

APPROVAL_FIELDS = {
    "id",
    "title",
    "description",
    "request_type",
    "status",
    "priority",
    "requester",
    "approver",
    "created_at",
    "due_at",
    "amount",
    "currency",
    "linked_ticket_id",
    "linked_task_id",
    "labels",
    "policy_area",
}

AUDIT_FIELDS = {
    "id",
    "approval_id",
    "action",
    "actor",
    "timestamp",
    "note",
}


def test_load_approvals_returns_realistic_dataset():
    all_approvals = approvals.load_approvals()

    assert 8 <= len(all_approvals) <= 12
    for approval in all_approvals:
        assert APPROVAL_FIELDS <= set(approval)

    assert sum(1 for a in all_approvals if a["status"] == "pending") >= 3
    assert sum(1 for a in all_approvals if a["priority"] in ("high", "urgent")) >= 2
    assert sum(1 for a in all_approvals if a["status"] == "approved") >= 1
    assert sum(1 for a in all_approvals if a["status"] == "rejected") >= 1
    assert any(a["policy_area"] == "expense_reimbursement" for a in all_approvals)
    assert any({"vpn", "security"} & set(a["labels"]) for a in all_approvals)
    assert any("onboarding" in a["labels"] for a in all_approvals)
    assert any(a["linked_ticket_id"] for a in all_approvals)
    assert any(a["linked_task_id"] for a in all_approvals)
    assert sum(1 for a in all_approvals if a["approver"] == approvals.ASSIGNEE_ME) >= 1


def test_load_audit_log_returns_realistic_dataset():
    events = approvals.load_audit_log()

    assert 5 <= len(events) <= 8
    for event in events:
        assert AUDIT_FIELDS <= set(event)

    actions = {e["action"] for e in events}
    for important in ("created", "approved", "rejected"):
        assert important in actions


def test_loaders_return_independent_copies():
    first = approvals.load_approvals()
    first[0]["title"] = "MUTATED"
    assert approvals.load_approvals()[0]["title"] != "MUTATED"

    first_log = approvals.load_audit_log()
    first_log[0]["note"] = "MUTATED"
    assert approvals.load_audit_log()[0]["note"] != "MUTATED"


def test_summarize_all_approvals():
    total = len(approvals.load_approvals())
    result = approvals.handle_approval_request("summarize all approvals")

    assert result.tool == INTENT_WORKFLOW_APPROVAL
    assert f"{total} of {total}" in result.content


def test_summarize_pending_approvals():
    expected = [a for a in approvals.load_approvals() if a["status"] == "pending"]
    matched = approvals.filter_approvals("pending approvals")

    assert {a["id"] for a in matched} == {a["id"] for a in expected}
    assert all(a["status"] == "pending" for a in matched)
    result = approvals.handle_approval_request("show pending approvals")
    assert "pending approvals" in result.content


def test_summarize_approvals_assigned_to_me():
    expected = [a for a in approvals.load_approvals() if a["approver"] == approvals.ASSIGNEE_ME]
    matched = approvals.filter_approvals("assigned to me")

    assert {a["id"] for a in matched} == {a["id"] for a in expected}
    assert all(a["approver"] == approvals.ASSIGNEE_ME for a in matched)
    result = approvals.handle_approval_request("which approvals are assigned to me?")
    assert "assigned to me" in result.content


def test_summarize_high_priority_approvals():
    expected = [a for a in approvals.load_approvals() if a["priority"] in ("high", "urgent")]
    matched = approvals.filter_approvals("high-priority approvals")

    assert {a["id"] for a in matched} == {a["id"] for a in expected}
    result = approvals.handle_approval_request("show urgent approvals")
    assert "high-priority approvals" in result.content


def test_summarize_approved_and_rejected_approvals():
    approved = approvals.filter_approvals("approved approvals")
    rejected = approvals.filter_approvals("rejected approvals")

    assert approved and all(a["status"] == "approved" for a in approved)
    assert rejected and all(a["status"] == "rejected" for a in rejected)

    approved_result = approvals.handle_approval_request("show approved approvals")
    assert "approved approvals" in approved_result.content
    rejected_result = approvals.handle_approval_request("show rejected approvals")
    assert "rejected approvals" in rejected_result.content


def test_topic_filter_narrows_to_expense_approvals():
    result = approvals.handle_approval_request("show expense approvals")
    assert result.tool == INTENT_WORKFLOW_APPROVAL
    # Every listed approval id is an expense-related one.
    expense_ids = {
        a["id"]
        for a in approvals.load_approvals()
        if a["policy_area"] == "expense_reimbursement" or "expenses" in a["labels"]
    }
    assert expense_ids
    for approval_id in expense_ids:
        assert approval_id in result.content


def test_status_for_specific_approval_id():
    result = approvals.handle_approval_request("what is the status of APR-001?")

    assert "APR-001" in result.content
    assert "Status:" in result.content
    assert "Approver (owner):" in result.content
    assert "Due:" in result.content
    assert "Policy area:" in result.content
    assert "Linked ticket:" in result.content


def test_status_for_unknown_approval_id_is_safe():
    result = approvals.handle_approval_request("what is the status of APR-999?")

    assert result.tool == INTENT_WORKFLOW_APPROVAL
    assert "no approval found for APR-999" in result.content
    assert approvals.find_approval("APR-999") is None


def test_simulated_approve_is_deterministic():
    result = approvals.handle_approval_request("approve APR-001")

    assert "Simulated action:" in result.content
    assert "APPROVED" in result.content
    assert "simulated only" in result.content

    approval = approvals.find_approval("APR-001")
    event_a = approvals.build_simulated_decision(approval, "approve")
    event_b = approvals.build_simulated_decision(approval, "approve")
    assert event_a == event_b
    assert event_a["new_status"] == "approved"
    assert event_a["actor"] == approvals.ASSIGNEE_ME


def test_simulated_reject_is_deterministic():
    result = approvals.handle_approval_request("reject APR-002")

    assert "Simulated action:" in result.content
    assert "REJECTED" in result.content

    approval = approvals.find_approval("APR-002")
    event = approvals.build_simulated_decision(approval, "reject")
    assert event["new_status"] == "rejected"
    assert event["previous_status"] == approval["status"]


def test_approved_view_is_not_treated_as_an_approve_action():
    # "show approved approvals" (no id) must be a list view, not a simulated action.
    result = approvals.handle_approval_request("show approved approvals")
    assert "Simulated action:" not in result.content
    assert "approved approvals" in result.content


def test_simulated_followup_task_is_deterministic():
    result = approvals.handle_approval_request("create a follow-up task for APR-001")

    assert "Simulated follow-up task:" in result.content
    assert "TASK-SIM-APR-001" in result.content
    assert "simulated only" in result.content

    approval = approvals.find_approval("APR-001")
    task_a = approvals.build_simulated_followup_task(approval)
    task_b = approvals.build_simulated_followup_task(approval)
    assert task_a == task_b
    assert task_a["source_approval_id"] == "APR-001"
    assert task_a["owner"] == approvals.ASSIGNEE_ME


def test_audit_log_for_specific_approval_is_sorted_by_timestamp():
    result = approvals.handle_approval_request("show audit log for APR-001")

    assert "Audit log — APR-001" in result.content

    events = approvals.audit_events_for("APR-001")
    assert events
    timestamps = [e["timestamp"] for e in events]
    assert timestamps == sorted(timestamps)
    assert all(e["approval_id"] == "APR-001" for e in events)


def test_handle_request_does_not_mutate_mock_data():
    before_approvals = approvals.load_approvals()
    before_audit = approvals.load_audit_log()

    approvals.handle_approval_request("approve APR-001")
    approvals.handle_approval_request("reject APR-002")
    approvals.handle_approval_request("create a follow-up task for APR-001")
    approvals.handle_approval_request("show pending approvals")

    assert approvals.load_approvals() == before_approvals
    assert approvals.load_audit_log() == before_audit


def test_record_decision_returns_none_for_unknown_id():
    assert approvals.record_decision("APR-999", "approve") is None


def test_persistence_seam_writes_only_to_given_path(tmp_path):
    target = tmp_path / "decisions.json"

    event = approvals.record_decision("APR-001", "approve", persist_path=target)

    assert event is not None
    assert target.exists()
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert saved[0]["approval_id"] == "APR-001"
    assert saved[0]["new_status"] == "approved"

    # The repo mock_data files are never touched by the seam.
    assert not any(e["id"] == event["id"] for e in approvals.load_audit_log())
    assert approvals.find_approval("APR-001")["status"] == "pending"
