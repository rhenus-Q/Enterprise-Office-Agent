"""
Unit tests for the mock Meeting Agent / Meeting Prep tool
(office_agent/tools/meeting.py).

Fully local and deterministic: the tool composes the other tools' pure loaders
over static fictional JSON — no OpenAI/Tavily/Chroma, no mail/calendar/ticket
service, and (critically) no call to the real Enterprise RAG pipeline. Output
must be identical on every run (no system clock) and must never mutate the mock
data.
"""

from office_agent.schemas import INTENT_MEETING_AGENT
from office_agent.tools import calendar, email, meeting, tickets

# Section headers the prep sheet must always contain.
_SECTIONS = [
    "Meeting:",
    "Relevant emails:",
    "Relevant tickets/tasks:",
    "Relevant knowledge areas:",
    "Suggested agenda:",
    "Risks / blockers:",
    "Recommended follow-ups:",
]


def test_next_meeting_is_the_deterministic_earliest_event():
    expected = calendar.next_meeting(calendar.load_events())
    assert expected is not None

    result = meeting.prepare_meeting("prepare me for my next meeting")

    assert result.tool == INTENT_MEETING_AGENT
    assert result.content.startswith(f"Meeting Prep — {expected['title']}")


def test_selects_topic_specific_vpn_meeting():
    result = meeting.prepare_meeting("what should I bring up in the VPN rollout meeting?")
    assert result.content.startswith("Meeting Prep — VPN rollout review")


def test_selects_topic_specific_security_review_board():
    result = meeting.prepare_meeting("prep me for the security review board")
    assert result.content.startswith("Meeting Prep — Security review board")


def test_falls_back_to_next_meeting_when_no_topic_matches():
    # No "next", no matching topic words -> fall back to the next meeting.
    expected = calendar.next_meeting(calendar.load_events())
    result = meeting.prepare_meeting("generate meeting prep")
    assert result.content.startswith(f"Meeting Prep — {expected['title']}")


def test_prep_contains_all_sections():
    content = meeting.prepare_meeting("prepare me for my next meeting").content
    for header in _SECTIONS:
        assert header in content


def test_meeting_section_shows_metadata_of_selected_meeting():
    content = meeting.prepare_meeting("prep me for the security review board").content
    assert "- Title: Security review board" in content
    assert "- Location: Room C" in content
    assert "- Importance: high" in content
    assert "- Time: 2026-07-01 14:00-15:00" in content


def test_relevant_emails_show_subject_and_sender_only_no_body():
    content = meeting.prepare_meeting("what should I bring up in the VPN rollout meeting?").content
    # The VPN-labelled email is surfaced by subject + sender...
    assert "VPN rollout review needed — manager@acmecorp.example" in content
    # ...but its body text must never be dumped.
    assert "sign-off is required" not in content


def test_relevant_tickets_and_tasks_are_surfaced():
    content = meeting.prepare_meeting("what should I bring up in the VPN rollout meeting?").content
    # The high-priority VPN ticket assigned to me is the top relevant item.
    assert "TICK-001:" in content
    assert "[OPEN/HIGH]" in content


def test_knowledge_areas_are_inferred_without_calling_enterprise_rag(monkeypatch):
    # Prove the tool never invokes the RAG engine: if it did, this would raise.
    import enterprise_rag.graph.engine as rag_engine

    def _boom(*args, **kwargs):
        raise AssertionError("Meeting Agent must not call the Enterprise RAG engine")

    monkeypatch.setattr(rag_engine, "answer_question", _boom)

    content = meeting.prepare_meeting("what should I bring up in the VPN rollout meeting?").content

    assert "Relevant knowledge areas:" in content
    assert "- vpn_access" in content
    assert "- security" in content


def test_suggested_agenda_is_a_numbered_list():
    content = meeting.prepare_meeting("prepare me for my next meeting").content
    agenda = content.split("Suggested agenda:", 1)[1]
    assert "1." in agenda


def test_risks_section_reports_schedule_conflict_for_overlapping_meeting():
    # The security review board (14:00-15:00) overlaps the budget workshop
    # (14:30-15:30) in the mock calendar, so a conflict must be reported.
    content = meeting.prepare_meeting("prep me for the security review board").content
    risks = content.split("Risks / blockers:", 1)[1]
    assert "Schedule conflict" in risks


def test_recommended_followups_are_present():
    content = meeting.prepare_meeting("what should I bring up in the VPN rollout meeting?").content
    followups = content.split("Recommended follow-ups:", 1)[1]
    # A response-needed VPN email yields a concrete reply action.
    assert "Reply to" in followups


def test_output_is_deterministic():
    first = meeting.prepare_meeting("prepare me for my next meeting")
    second = meeting.prepare_meeting("prepare me for my next meeting")
    assert first.content == second.content

    # Two "next meeting" phrasings resolve to the same meeting + context.
    third = meeting.prepare_meeting("summarize context for my next meeting")
    assert first.content == third.content


def test_does_not_mutate_mock_data():
    before_emails = email.load_emails()
    before_events = calendar.load_events()
    before_tickets = tickets.load_tickets()
    before_tasks = tickets.load_tasks()

    meeting.prepare_meeting("prepare me for my next meeting")
    meeting.prepare_meeting("prep me for the security review board")

    assert email.load_emails() == before_emails
    assert calendar.load_events() == before_events
    assert tickets.load_tickets() == before_tickets
    assert tickets.load_tasks() == before_tasks
