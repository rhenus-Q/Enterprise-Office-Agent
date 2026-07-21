"""
Unit tests for the mock Daily Briefing aggregator (office_agent/tools/briefing.py).

Fully local and deterministic: the briefing reuses the other tools' pure loaders
over static fictional JSON — no OpenAI/Tavily/Chroma and no mail/calendar/ticket
service. The briefing must be identical on every run (no system clock) and must
never mutate the mock data.
"""

import os
from unittest.mock import Mock

from office_agent.llm_assist import briefing_narrative
from office_agent.schemas import INTENT_DAILY_BRIEFING
from office_agent.tools import briefing, calendar, email, tickets
from tests.conftest import isolate_ordinary_test_environment


def test_briefing_day_is_calendar_today_not_system_clock():
    events = calendar.load_events()
    expected_today, _tomorrow = calendar.resolve_days(events)

    # The briefing day is anchored to the mock calendar data, never the clock,
    # so it equals the calendar tool's resolved "today" on every run.
    assert briefing.briefing_day() == expected_today
    assert briefing.briefing_day() == expected_today  # stable across calls


def test_briefing_is_deterministic(monkeypatch):
    """A contaminated parent flag cannot activate the assist in ordinary pytest."""

    monkeypatch.setenv("OFFICE_LLM_ENABLED", "true")
    isolate_ordinary_test_environment(os.environ)

    model_factory = Mock(
        side_effect=AssertionError("real LLM factory must not be called by an ordinary test")
    )
    monkeypatch.setattr(
        briefing_narrative,
        "get_briefing_narrative_chain",
        model_factory,
    )

    first = briefing.generate_daily_briefing("give me my daily briefing")
    second = briefing.generate_daily_briefing("morning briefing")

    assert first.tool == INTENT_DAILY_BRIEFING
    assert first.content.encode("utf-8") == second.content.encode("utf-8")
    model_factory.assert_not_called()


def test_briefing_has_all_sections_with_the_briefing_day():
    result = briefing.generate_daily_briefing("daily briefing")
    content = result.content

    assert f"Daily briefing — {briefing.briefing_day()}" in content
    assert "Priority emails:" in content
    assert "Calendar (" in content
    assert "Tickets and tasks:" in content
    assert "Recommended focus:" in content


def test_email_section_counts_match_mock_data():
    emails = email.load_emails()
    unread = sum(1 for e in emails if not e["is_read"])
    important = sum(1 for e in emails if e["importance"] == "high")
    needs_response = sum(1 for e in emails if e["requires_response"])

    content = briefing.generate_daily_briefing("daily briefing").content

    assert f"- {unread} unread email(s)." in content
    assert f"- {important} high-priority email(s)." in content
    assert f"- {needs_response} email(s) need a response." in content


def test_calendar_section_counts_todays_events_and_next():
    events = calendar.load_events()
    today, _tomorrow = calendar.resolve_days(events)
    todays = [e for e in events if e["start_at"][:10] == today]
    nxt = calendar.next_meeting(todays)

    content = briefing.generate_daily_briefing("daily briefing").content

    assert f"- {len(todays)} meeting(s) today." in content
    assert nxt is not None
    assert nxt["title"] in content  # the next meeting's title is surfaced


def test_tickets_section_counts_match_mock_data():
    all_tickets = tickets.load_tickets()
    open_count = sum(1 for t in all_tickets if t["status"] == "open")
    blocked_count = sum(1 for t in all_tickets if t["status"] == "blocked")

    content = briefing.generate_daily_briefing("daily briefing").content

    assert f"- {open_count} open ticket(s)." in content
    assert f"- {blocked_count} blocked ticket(s)." in content


def test_focus_section_is_a_numbered_list():
    content = briefing.generate_daily_briefing("daily briefing").content
    focus = content.split("Recommended focus:", 1)[1]

    # At least one numbered recommendation follows the header.
    assert "1." in focus


def test_briefing_does_not_mutate_mock_data():
    before_emails = email.load_emails()
    before_events = calendar.load_events()
    before_tickets = tickets.load_tickets()
    before_tasks = tickets.load_tasks()

    briefing.generate_daily_briefing("daily briefing")

    assert email.load_emails() == before_emails
    assert calendar.load_events() == before_events
    assert tickets.load_tickets() == before_tickets
    assert tickets.load_tasks() == before_tasks


# --- collect_briefing_facts: critical-fact preservation + enrichment ----------


def _meeting_ids(facts):
    return [f["id"] for f in facts if f["source_type"] == "meeting"]


def test_collect_facts_keeps_first_five_meetings_plus_conflict_counterpart():
    """The base cap keeps the first five meetings; cal-006 is additionally
    preserved because it overlaps the selected cal-005."""

    facts = briefing.collect_briefing_facts()
    meeting_ids = _meeting_ids(facts)

    assert meeting_ids[:5] == ["cal-001", "cal-002", "cal-003", "cal-004", "cal-005"]
    assert "cal-006" in meeting_ids  # soft-cap overflow for the conflict counterpart
    assert meeting_ids == ["cal-001", "cal-002", "cal-003", "cal-004", "cal-005", "cal-006"]


def test_collect_facts_excludes_ordinary_sixth_meeting(monkeypatch):
    """Without a conflict, a sixth meeting past the cap stays excluded."""

    day = "2026-07-01"
    events = [
        {
            "id": f"m{i}",
            "title": f"Meeting {i}",
            "importance": "normal",
            "start_at": f"{day}T{8 + i:02d}:00:00",
            "end_at": f"{day}T{8 + i:02d}:30:00",  # non-overlapping 30-min slots
        }
        for i in range(6)
    ] + [
        {
            "id": "tmw",
            "title": "Tomorrow",
            "importance": "normal",
            "start_at": "2026-07-02T09:00:00",
            "end_at": "2026-07-02T09:30:00",
        }
    ]
    monkeypatch.setattr(calendar, "load_events", lambda: [dict(e) for e in events])

    meeting_ids = _meeting_ids(briefing.collect_briefing_facts())
    assert meeting_ids == ["m0", "m1", "m2", "m3", "m4"]  # sixth (m5) excluded


def test_collect_facts_has_no_duplicate_pairs():
    facts = briefing.collect_briefing_facts()
    pairs = [(f["source_type"], f["id"]) for f in facts]
    assert len(pairs) == len(set(pairs))


def test_collect_facts_is_deterministic():
    assert briefing.collect_briefing_facts() == briefing.collect_briefing_facts()


def test_conflict_counterparts_reference_each_other():
    facts = briefing.collect_briefing_facts()
    by_id = {f["id"]: f for f in facts if f["source_type"] == "meeting"}

    assert "cal-006" in by_id["cal-005"]["conflicts_with"]
    assert "cal-005" in by_id["cal-006"]["conflicts_with"]
    assert "schedule_conflict" in by_id["cal-005"]["critical_reasons"]
    assert "schedule_conflict" in by_id["cal-006"]["critical_reasons"]
    # cal-005 is a high-importance meeting, so it also flags high_importance.
    assert "high_importance" in by_id["cal-005"]["critical_reasons"]


def test_ticket_fact_exposes_priority_status_and_reasons():
    facts = briefing.collect_briefing_facts()
    tick = next(f for f in facts if f["source_type"] == "ticket" and f["id"] == "TICK-004")

    assert tick["priority"] == "high"
    assert tick["status"] == "blocked"
    assert "high_priority" in tick["critical_reasons"]
    assert "blocked" in tick["critical_reasons"]
