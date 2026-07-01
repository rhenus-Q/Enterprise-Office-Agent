"""
Unit tests for the mock Calendar Lookup tool (office_agent/tools/calendar.py).

Fully local and deterministic: the tool reads static fictional JSON from
office_agent/mock_data/ — no OpenAI/Tavily/Chroma and no calendar service.
Expected values are derived from the loaded data (not hard-coded dates), so the
tests stay correct if the mock calendar is edited.
"""

from office_agent.schemas import INTENT_CALENDAR_LOOKUP
from office_agent.tools import calendar

REQUIRED_FIELDS = {
    "id",
    "title",
    "description",
    "start_at",
    "end_at",
    "attendees",
    "location",
    "meeting_type",
    "importance",
    "labels",
}

EMAIL_THEME_LABELS = {"vpn", "security", "onboarding", "expenses"}


def _day(event):
    return event["start_at"][:10]


def test_load_events_returns_realistic_dataset():
    events = calendar.load_events()

    assert 8 <= len(events) <= 12
    for event in events:
        assert REQUIRED_FIELDS <= set(event)

    today, tomorrow = calendar.resolve_days(events)
    assert sum(1 for e in events if _day(e) == today) >= 3
    assert sum(1 for e in events if _day(e) == tomorrow) >= 2
    assert sum(1 for e in events if e["importance"] == "high") >= 1
    assert len(calendar.find_conflicts(events)) >= 1
    assert any(EMAIL_THEME_LABELS & set(e["labels"]) for e in events)


def test_load_events_returns_independent_copies():
    first = calendar.load_events()
    first[0]["title"] = "MUTATED"
    assert calendar.load_events()[0]["title"] != "MUTATED"


def test_resolve_days_are_consecutive_and_data_driven():
    from datetime import date, timedelta

    events = calendar.load_events()
    today, tomorrow = calendar.resolve_days(events)

    assert date.fromisoformat(today) + timedelta(days=1) == date.fromisoformat(tomorrow)
    # "tomorrow" is the latest populated day; "today" is the day before.
    assert tomorrow == max(_day(e) for e in events)


def test_summarizes_todays_events():
    events = calendar.load_events()
    today, _tomorrow = calendar.resolve_days(events)
    expected = {e["id"] for e in events if _day(e) == today}

    view, matched = calendar.filter_for_query("what meetings do I have today?")

    assert view == "today"
    assert {e["id"] for e in matched} == expected
    assert len(matched) >= 3


def test_summarizes_tomorrows_events():
    events = calendar.load_events()
    _today, tomorrow = calendar.resolve_days(events)
    expected = {e["id"] for e in events if _day(e) == tomorrow}

    view, matched = calendar.filter_for_query("do I have any meetings tomorrow?")

    assert view == "tomorrow"
    assert {e["id"] for e in matched} == expected
    assert len(matched) >= 2


def test_next_meeting_is_earliest_event():
    events = calendar.load_events()
    earliest = min(events, key=lambda e: e["start_at"])

    view, matched = calendar.filter_for_query("what is my next meeting?")

    assert view == "next meeting"
    assert len(matched) == 1
    assert matched[0]["id"] == earliest["id"]
    assert calendar.next_meeting(events)["id"] == earliest["id"]


def test_detects_schedule_conflicts():
    conflicts = calendar.find_conflicts(calendar.load_events())
    result = calendar.lookup_calendar("do I have schedule conflicts?")

    assert result.tool == INTENT_CALENDAR_LOOKUP
    assert conflicts  # the spec dataset has at least one overlapping pair
    assert "Schedule conflicts:" in result.content
    # Both titles of a conflicting pair appear in the summary.
    first, second = conflicts[0]
    assert first["title"] in result.content
    assert second["title"] in result.content


def test_summarizes_important_meetings():
    important = [e for e in calendar.load_events() if e["importance"] == "high"]

    view, matched = calendar.filter_for_query("show important meetings")

    assert view == "high-priority"
    assert {e["id"] for e in matched} == {e["id"] for e in important}
    assert all(e["importance"] == "high" for e in matched)


def test_summary_is_sorted_by_start_time():
    _view, matched = calendar.filter_for_query("show my full calendar")
    starts = [e["start_at"] for e in matched]
    assert starts == sorted(starts)
