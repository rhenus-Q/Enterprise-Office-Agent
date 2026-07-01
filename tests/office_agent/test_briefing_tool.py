"""
Unit tests for the mock Daily Briefing aggregator (office_agent/tools/briefing.py).

Fully local and deterministic: the briefing reuses the other tools' pure loaders
over static fictional JSON — no OpenAI/Tavily/Chroma and no mail/calendar/ticket
service. The briefing must be identical on every run (no system clock) and must
never mutate the mock data.
"""

from office_agent.schemas import INTENT_DAILY_BRIEFING
from office_agent.tools import briefing, calendar, email, tickets


def test_briefing_day_is_calendar_today_not_system_clock():
    events = calendar.load_events()
    expected_today, _tomorrow = calendar.resolve_days(events)

    # The briefing day is anchored to the mock calendar data, never the clock,
    # so it equals the calendar tool's resolved "today" on every run.
    assert briefing.briefing_day() == expected_today
    assert briefing.briefing_day() == expected_today  # stable across calls


def test_briefing_is_deterministic():
    first = briefing.generate_daily_briefing("give me my daily briefing")
    second = briefing.generate_daily_briefing("morning briefing")

    assert first.tool == INTENT_DAILY_BRIEFING
    assert first.content == second.content


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
