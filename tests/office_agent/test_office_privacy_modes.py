"""
Tests for the Office Agent under the hierarchical runtime privacy modes
(PRIVACY_MODE / OFFLINE_MODE).

Fully mocked and keys-free: the assist seams are poisoned so any LLM call fails
the test, the Knowledge Q&A adapter's engine call is patched, and no external
service is ever contacted.

The guarantees asserted here are:
- either mode forces both optional LLM assists off, reproducing the existing
  byte-for-byte flag-off output even with OFFICE_LLM_ENABLED=true;
- the deterministic local capabilities are completely unaffected by either mode;
- an OFFLINE_MODE Knowledge Q&A result reaches the user through the unchanged
  adapter, carrying the engine's stop reason and caveat.
"""

import pytest

from enterprise_rag.graph.consts import STOP_REASON_OFFLINE_MODE
from enterprise_rag.graph.formatting import OFFLINE_MODE_NOTE
from office_agent.llm_assist import briefing_narrative, email_digest
from office_agent.llm_assist import config as llm_config
from office_agent.tools import briefing as briefing_tool
from office_agent.tools import calendar, knowledge
from office_agent.tools import email as email_tool

MODE_VARS = ("PRIVACY_MODE", "OFFLINE_MODE")


@pytest.fixture
def modes_off(monkeypatch):
    for name in MODE_VARS:
        monkeypatch.delenv(name, raising=False)


def _enable(monkeypatch, mode):
    for name in MODE_VARS:
        monkeypatch.setenv(name, "true" if name == mode else "false")


def _poison_assists(monkeypatch):
    """Any assist call (either assist) must fail the test loudly."""

    def _boom(*args, **kwargs):
        raise AssertionError("no LLM assist may run under a runtime privacy mode")

    monkeypatch.setattr(email_digest, "digest_emails", _boom)
    monkeypatch.setattr(email_digest, "get_email_digest_chain", _boom)
    monkeypatch.setattr(briefing_narrative, "narrate_briefing", _boom)


# ---------------------------------------------------------------------------
# office_llm_enabled() gating
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", MODE_VARS)
def test_mode_forces_assists_off_over_explicit_true(monkeypatch, mode):
    # A mode can only restrict: an explicit OFFICE_LLM_ENABLED=true loses.
    monkeypatch.setenv("OFFICE_LLM_ENABLED", "true")
    _enable(monkeypatch, mode)

    assert llm_config.office_llm_enabled() is False


def test_assist_flag_still_works_when_modes_off(modes_off, monkeypatch):
    monkeypatch.setenv("OFFICE_LLM_ENABLED", "true")
    assert llm_config.office_llm_enabled() is True

    monkeypatch.setenv("OFFICE_LLM_ENABLED", "false")
    assert llm_config.office_llm_enabled() is False


# ---------------------------------------------------------------------------
# Byte-for-byte flag-off equivalence under a mode
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", MODE_VARS)
def test_email_summary_is_byte_identical_to_flag_off(monkeypatch, mode):
    monkeypatch.delenv("OFFICE_LLM_ENABLED", raising=False)
    for name in MODE_VARS:
        monkeypatch.delenv(name, raising=False)
    baseline = email_tool.summarize_emails("summarize my emails")

    # Assist explicitly requested, but the mode overrides it.
    monkeypatch.setenv("OFFICE_LLM_ENABLED", "true")
    _enable(monkeypatch, mode)
    _poison_assists(monkeypatch)

    result = email_tool.summarize_emails("summarize my emails")

    assert result.content == baseline.content
    assert result.stop_reason == baseline.stop_reason


@pytest.mark.parametrize("mode", MODE_VARS)
def test_daily_briefing_is_byte_identical_to_flag_off(monkeypatch, mode):
    monkeypatch.delenv("OFFICE_LLM_ENABLED", raising=False)
    for name in MODE_VARS:
        monkeypatch.delenv(name, raising=False)
    baseline = briefing_tool.generate_daily_briefing("daily briefing")

    monkeypatch.setenv("OFFICE_LLM_ENABLED", "true")
    _enable(monkeypatch, mode)
    _poison_assists(monkeypatch)

    result = briefing_tool.generate_daily_briefing("daily briefing")

    assert result.content == baseline.content
    assert result.stop_reason == baseline.stop_reason


# ---------------------------------------------------------------------------
# Deterministic local capabilities are unaffected
# ---------------------------------------------------------------------------


def test_deterministic_capability_output_is_unchanged_offline(monkeypatch):
    for name in MODE_VARS:
        monkeypatch.delenv(name, raising=False)
    baseline = calendar.lookup_calendar("what is on my calendar today")

    _enable(monkeypatch, "OFFLINE_MODE")
    offline = calendar.lookup_calendar("what is on my calendar today")

    # Local, mock-data-backed capabilities keep working with zero difference.
    assert offline.content == baseline.content
    assert offline.stop_reason == baseline.stop_reason


# ---------------------------------------------------------------------------
# Knowledge Q&A adapter surfaces the engine's offline outcome unchanged
# ---------------------------------------------------------------------------


def test_knowledge_adapter_passes_through_offline_stop_reason(monkeypatch):
    """The adapter is unchanged: it carries the engine's offline stop reason and
    the engine's own formatted caveat straight to the Office Agent user."""

    class _OfflineResult:
        raw_state = {"generation": "", "stop_reason": STOP_REASON_OFFLINE_MODE, "documents": []}
        stop_reason = STOP_REASON_OFFLINE_MODE
        sources: list[str] = []
        run_id = "run-offline"
        # The engine short-circuits before the graph, so it still returns a
        # complete AnswerResult — with an empty node path and zeroed counters.
        node_path: list[str] = []
        node_timings_ms: list[dict[str, object]] = []
        total_duration_ms = 0.0
        retries = 0
        tracked_llm_calls = 0
        web_search_count = 0
        web_result_grading_count = 0
        web_search_enabled = False
        web_fallback_policy = "conservative"

    monkeypatch.setattr(knowledge, "answer_question", lambda question: _OfflineResult())

    result = knowledge.run_knowledge_qa("What is the VPN policy?")

    assert result.stop_reason == STOP_REASON_OFFLINE_MODE
    assert OFFLINE_MODE_NOTE in result.content
    assert result.sources == []
    # No graph ran, so the carried-through metadata is genuinely empty — and the
    # caveat is still the engine's own offline note.
    assert result.observability is not None
    assert result.observability.node_path == []
    assert result.observability.node_timings_ms == []
    assert result.observability.tracked_llm_calls == 0
    assert result.observability.caveat == OFFLINE_MODE_NOTE
