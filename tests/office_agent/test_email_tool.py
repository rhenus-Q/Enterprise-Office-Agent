"""
Unit tests for the mock Email Summary tool (office_agent/tools/email.py).

Fully local and deterministic: the tool reads static fictional JSON from
office_agent/mock_data/ — no OpenAI/Tavily/Chroma and no mail service. Expected
counts are derived from the loaded data (not hard-coded), so the tests stay
correct if the mock inbox is edited.
"""

from office_agent.schemas import INTENT_EMAIL_SUMMARY
from office_agent.tools import email

REQUIRED_FIELDS = {
    "id",
    "from",
    "to",
    "subject",
    "body",
    "received_at",
    "is_read",
    "importance",
    "requires_response",
    "labels",
}


def test_load_emails_returns_realistic_dataset():
    emails = email.load_emails()

    assert 8 <= len(emails) <= 12
    for message in emails:
        assert REQUIRED_FIELDS <= set(message)

    # Dataset is useful for testing per the Phase 2 spec.
    assert sum(1 for m in emails if m["importance"] == "high") >= 2
    assert sum(1 for m in emails if not m["is_read"]) >= 2
    assert sum(1 for m in emails if m["requires_response"]) >= 2


def test_load_emails_returns_independent_copies():
    first = email.load_emails()
    first[0]["subject"] = "MUTATED"
    assert email.load_emails()[0]["subject"] != "MUTATED"


def test_summarize_all_emails():
    emails = email.load_emails()
    result = email.summarize_emails("summarize my emails")

    assert result.tool == INTENT_EMAIL_SUMMARY
    assert f"{len(emails)} of {len(emails)}" in result.content
    assert "all messages" in result.content


def test_summarize_unread_emails():
    unread = [m for m in email.load_emails() if not m["is_read"]]

    label, matched = email.filter_for_query("summarize unread emails")
    result = email.summarize_emails("summarize unread emails")

    assert label == "unread"
    assert len(matched) == len(unread)
    assert all(not m["is_read"] for m in matched)
    assert f"{len(unread)} of {len(email.load_emails())}" in result.content


def test_summarize_important_emails():
    important = [m for m in email.load_emails() if m["importance"] == "high"]

    label, matched = email.filter_for_query("show important emails")

    assert label == "high-priority"
    assert len(matched) == len(important)
    assert all(m["importance"] == "high" for m in matched)


def test_summarize_response_needed_emails():
    needs_response = [m for m in email.load_emails() if m["requires_response"]]

    label, matched = email.filter_for_query("which emails need my response?")
    result = email.summarize_emails("which emails need my response?")

    assert label == "response needed"
    assert len(matched) == len(needs_response)
    assert all(m["requires_response"] for m in matched)
    # Response-needed messages are surfaced as explicit action items.
    assert "Action items (response needed):" in result.content


def test_summarize_todays_emails_uses_latest_day_not_system_clock():
    emails = email.load_emails()
    latest_day = max(m["received_at"][:10] for m in emails)
    todays = [m for m in emails if m["received_at"][:10] == latest_day]

    label, matched = email.filter_for_query("what emails came in today?")

    assert label == "today"
    assert len(matched) == len(todays)
    assert matched  # the spec dataset has emails on the latest day


def test_summary_is_newest_first():
    _label, matched = email.filter_for_query("summarize my emails")
    received = [m["received_at"] for m in matched]
    assert received == sorted(received, reverse=True)
