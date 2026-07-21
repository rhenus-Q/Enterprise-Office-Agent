"""
Unit tests for request-scoped run settings (office_agent/run_settings.py) and
their threading through the engine (office_agent/engine.py).

Fully mocked / local: the resolver is pure, the engine tests patch the tool
seams, and the byte-for-byte tests run the real deterministic mock tools. No
OpenAI, Tavily, Chroma, enterprise_rag graph run, or LLM assist is involved.

The central property under test is the precedence rule: a request may only ever
make a run *stricter*. It can never re-enable something server policy disabled.
"""

import os
from concurrent.futures import ThreadPoolExecutor

import pytest

from office_agent import engine
from office_agent.llm_assist import config as llm_config
from office_agent.run_settings import (
    CONSTRAINT_LLM_ASSIST_NOT_APPLICABLE,
    CONSTRAINT_REQUEST_PRIVACY_STRICT,
    CONSTRAINT_SERVER_LLM_ASSIST_DISABLED,
    CONSTRAINT_SERVER_OFFLINE_MODE,
    CONSTRAINT_SERVER_PRIVACY_MODE,
    CONSTRAINT_SERVER_WEB_SEARCH_DISABLED,
    CONSTRAINT_WEB_SEARCH_NOT_APPLICABLE,
    PRIVACY_STANDARD,
    PRIVACY_STRICT,
    OfficeRunOptions,
    resolve_run_settings,
)
from office_agent.schemas import (
    INTENT_CALENDAR_LOOKUP,
    INTENT_DAILY_BRIEFING,
    INTENT_EMAIL_SUMMARY,
    INTENT_KNOWLEDGE_QA,
    INTENT_TICKET_ASSISTANT,
    INTENT_UNKNOWN,
    ToolResult,
)
from office_agent.tools import briefing, email, knowledge

# A permissive server: nothing is restricted, so the request alone decides.
_OPEN_SERVER = {
    "server_privacy_mode": False,
    "server_offline_mode": False,
    "server_llm_assist_available": True,
    "server_web_search_available": True,
}


def _resolve(intent, options, **overrides):
    return resolve_run_settings(intent, options, **{**_OPEN_SERVER, **overrides})


# --- 3. Standard + requested On works when server policy permits ------------


def test_standard_privacy_with_requested_assist_enables_it_for_assist_capability():
    settings = _resolve(
        INTENT_EMAIL_SUMMARY,
        OfficeRunOptions(privacy_mode=PRIVACY_STANDARD, llm_assist=True),
    )

    assert settings.effective.llm_assist is True
    assert settings.effective.privacy_mode == PRIVACY_STANDARD
    assert settings.constraints == ()


def test_standard_privacy_with_requested_web_search_enables_it_for_knowledge():
    settings = _resolve(
        INTENT_KNOWLEDGE_QA,
        OfficeRunOptions(privacy_mode=PRIVACY_STANDARD, web_search=True),
    )

    assert settings.effective.web_search is True
    assert settings.constraints == ()


# --- 4/5. Server modes override requested external services -----------------


@pytest.mark.parametrize(
    "mode_kwargs, expected_constraint",
    [
        ({"server_privacy_mode": True}, CONSTRAINT_SERVER_PRIVACY_MODE),
        ({"server_offline_mode": True}, CONSTRAINT_SERVER_OFFLINE_MODE),
    ],
)
def test_server_mode_overrides_requested_llm_assist(mode_kwargs, expected_constraint):
    settings = _resolve(
        INTENT_EMAIL_SUMMARY,
        OfficeRunOptions(llm_assist=True),
        server_llm_assist_available=False,  # the real readers already force this
        **mode_kwargs,
    )

    assert settings.requested.llm_assist is True
    assert settings.effective.llm_assist is False
    assert settings.effective.privacy_mode == PRIVACY_STRICT
    assert expected_constraint in settings.constraints


@pytest.mark.parametrize(
    "mode_kwargs, expected_constraint",
    [
        ({"server_privacy_mode": True}, CONSTRAINT_SERVER_PRIVACY_MODE),
        ({"server_offline_mode": True}, CONSTRAINT_SERVER_OFFLINE_MODE),
    ],
)
def test_server_mode_overrides_requested_web_search(mode_kwargs, expected_constraint):
    settings = _resolve(
        INTENT_KNOWLEDGE_QA,
        OfficeRunOptions(web_search=True),
        server_web_search_available=False,
        **mode_kwargs,
    )

    assert settings.requested.web_search is True
    assert settings.effective.web_search is False
    assert expected_constraint in settings.constraints


def test_server_mode_escalates_privacy_even_when_request_asked_for_standard():
    settings = _resolve(
        INTENT_KNOWLEDGE_QA,
        OfficeRunOptions(privacy_mode=PRIVACY_STANDARD),
        server_privacy_mode=True,
    )

    assert settings.requested.privacy_mode == PRIVACY_STANDARD
    assert settings.effective.privacy_mode == PRIVACY_STRICT
    assert CONSTRAINT_SERVER_PRIVACY_MODE in settings.constraints


def test_a_request_can_never_re_enable_a_server_disabled_service():
    """The core precedence property: requesting On against a disabled server loses."""

    settings = _resolve(
        INTENT_KNOWLEDGE_QA,
        OfficeRunOptions(web_search=True),
        server_web_search_available=False,
    )

    assert settings.effective.web_search is False
    assert CONSTRAINT_SERVER_WEB_SEARCH_DISABLED in settings.constraints


def test_server_assist_flag_off_blocks_a_requested_assist():
    settings = _resolve(
        INTENT_DAILY_BRIEFING,
        OfficeRunOptions(llm_assist=True),
        server_llm_assist_available=False,
    )

    assert settings.effective.llm_assist is False
    assert CONSTRAINT_SERVER_LLM_ASSIST_DISABLED in settings.constraints


# --- 6. Request-level strict privacy restricts without touching the server ---


def test_request_privacy_strict_disables_both_external_paths():
    llm = _resolve(INTENT_EMAIL_SUMMARY, OfficeRunOptions(PRIVACY_STRICT, llm_assist=True))
    web = _resolve(INTENT_KNOWLEDGE_QA, OfficeRunOptions(PRIVACY_STRICT, web_search=True))

    assert llm.effective.llm_assist is False
    assert CONSTRAINT_REQUEST_PRIVACY_STRICT in llm.constraints
    assert web.effective.web_search is False
    assert CONSTRAINT_REQUEST_PRIVACY_STRICT in web.constraints


# --- 7. Requested Off always stays Off --------------------------------------


@pytest.mark.parametrize("intent", [INTENT_EMAIL_SUMMARY, INTENT_DAILY_BRIEFING])
def test_requested_assist_off_stays_off_even_when_server_allows_it(intent):
    settings = _resolve(intent, OfficeRunOptions(llm_assist=False))

    assert settings.effective.llm_assist is False
    # Nothing was overridden — the user asked for off and got off.
    assert settings.constraints == ()


def test_requested_web_search_off_stays_off_even_when_server_allows_it():
    settings = _resolve(INTENT_KNOWLEDGE_QA, OfficeRunOptions(web_search=False))

    assert settings.effective.web_search is False
    assert settings.constraints == ()


# --- 8/9. Applicability -----------------------------------------------------


@pytest.mark.parametrize(
    "intent", [INTENT_KNOWLEDGE_QA, INTENT_CALENDAR_LOOKUP, INTENT_TICKET_ASSISTANT, INTENT_UNKNOWN]
)
def test_llm_assist_is_not_applicable_outside_email_and_briefing(intent):
    settings = _resolve(intent, OfficeRunOptions(llm_assist=True))

    assert settings.applicability.llm_assist is False
    assert settings.effective.llm_assist is False
    assert CONSTRAINT_LLM_ASSIST_NOT_APPLICABLE in settings.constraints


@pytest.mark.parametrize(
    "intent", [INTENT_EMAIL_SUMMARY, INTENT_DAILY_BRIEFING, INTENT_CALENDAR_LOOKUP, INTENT_UNKNOWN]
)
def test_web_search_is_not_applicable_outside_knowledge_qa(intent):
    settings = _resolve(intent, OfficeRunOptions(web_search=True))

    assert settings.applicability.web_search is False
    assert settings.effective.web_search is False
    assert CONSTRAINT_WEB_SEARCH_NOT_APPLICABLE in settings.constraints


def test_applicability_is_reported_even_when_nothing_was_requested():
    """Not-applicable is a property of the capability, not of the request."""

    settings = _resolve(INTENT_CALENDAR_LOOKUP, OfficeRunOptions())

    assert settings.applicability.llm_assist is False
    assert settings.applicability.web_search is False
    # Requested and effective agree, so there is nothing to explain.
    assert settings.constraints == ()


# --- 10. requested / effective / applicability / constraints are accurate ----


def test_full_shape_matches_the_documented_example():
    """Server privacy blocks an applicable assist; web search never applied."""

    settings = _resolve(
        INTENT_EMAIL_SUMMARY,
        OfficeRunOptions(privacy_mode=PRIVACY_STANDARD, llm_assist=True, web_search=True),
        server_privacy_mode=True,
        server_llm_assist_available=False,
        server_web_search_available=False,
    )

    assert settings.requested.privacy_mode == PRIVACY_STANDARD
    assert settings.requested.llm_assist is True
    assert settings.requested.web_search is True
    assert settings.effective.privacy_mode == PRIVACY_STRICT
    assert settings.effective.llm_assist is False
    assert settings.effective.web_search is False
    assert settings.applicability.llm_assist is True
    assert settings.applicability.web_search is False
    assert settings.constraints == (
        CONSTRAINT_SERVER_PRIVACY_MODE,
        CONSTRAINT_WEB_SEARCH_NOT_APPLICABLE,
    )


def test_constraints_are_deterministically_ordered():
    settings = _resolve(
        INTENT_CALENDAR_LOOKUP,
        OfficeRunOptions(llm_assist=True, web_search=True),
        server_offline_mode=True,
    )

    # Canonical order: server mode first, then the two not-applicable reasons.
    assert settings.constraints == (
        CONSTRAINT_SERVER_OFFLINE_MODE,
        CONSTRAINT_LLM_ASSIST_NOT_APPLICABLE,
        CONSTRAINT_WEB_SEARCH_NOT_APPLICABLE,
    )


def test_an_unrecognized_privacy_level_falls_back_to_standard():
    settings = _resolve(INTENT_EMAIL_SUMMARY, OfficeRunOptions(privacy_mode="bogus"))

    assert settings.requested.privacy_mode == PRIVACY_STANDARD


# --- Engine threading -------------------------------------------------------


def _record_tool(recorded, tool_name):
    def _tool(_text, **kwargs):
        recorded.append(kwargs)
        return ToolResult(tool=tool_name, content="X")

    return _tool


def _open_policy(monkeypatch):
    """Patch every server-policy reader the engine consults to 'permissive'."""

    monkeypatch.setattr(llm_config, "privacy_mode", lambda: False)
    monkeypatch.setattr(llm_config, "offline_mode", lambda: False)
    monkeypatch.setattr(llm_config, "office_llm_enabled", lambda: True)
    monkeypatch.setattr(knowledge, "web_search_available", lambda: True)


# --- 1. Omitting options preserves existing behavior exactly ----------------


def test_engine_passes_none_to_tools_when_options_are_omitted(monkeypatch):
    recorded = []
    monkeypatch.setattr(email, "summarize_emails", _record_tool(recorded, INTENT_EMAIL_SUMMARY))

    response = engine.answer_office_request("summarize my unread emails")

    assert recorded == [{"llm_assist_enabled": None}]
    assert response.run_settings is None


def test_engine_passes_none_to_knowledge_when_options_are_omitted(monkeypatch):
    recorded = []
    monkeypatch.setattr(knowledge, "run_knowledge_qa", _record_tool(recorded, INTENT_KNOWLEDGE_QA))

    engine.answer_office_request("What is the VPN access policy?")

    assert recorded == [{"web_search_enabled": None}]


# --- Engine threads the *effective* decision, not the raw request -----------


def test_engine_threads_effective_assist_decision_into_the_email_tool(monkeypatch):
    _open_policy(monkeypatch)
    recorded = []
    monkeypatch.setattr(email, "summarize_emails", _record_tool(recorded, INTENT_EMAIL_SUMMARY))

    engine.answer_office_request("summarize my unread emails", OfficeRunOptions(llm_assist=True))

    assert recorded == [{"llm_assist_enabled": True}]


def test_engine_threads_effective_assist_decision_into_the_briefing_tool(monkeypatch):
    _open_policy(monkeypatch)
    recorded = []
    monkeypatch.setattr(
        briefing, "generate_daily_briefing", _record_tool(recorded, INTENT_DAILY_BRIEFING)
    )

    engine.answer_office_request("brief me on my day", OfficeRunOptions(llm_assist=True))

    assert recorded == [{"llm_assist_enabled": True}]


def test_engine_threads_effective_web_search_decision_into_knowledge(monkeypatch):
    _open_policy(monkeypatch)
    recorded = []
    monkeypatch.setattr(knowledge, "run_knowledge_qa", _record_tool(recorded, INTENT_KNOWLEDGE_QA))

    engine.answer_office_request("What is the VPN policy?", OfficeRunOptions(web_search=True))

    assert recorded == [{"web_search_enabled": True}]


def test_engine_sends_false_when_server_policy_blocks_a_requested_service(monkeypatch):
    """The tool receives the restricted decision — not the optimistic request."""

    _open_policy(monkeypatch)
    monkeypatch.setattr(knowledge, "web_search_available", lambda: False)
    recorded = []
    monkeypatch.setattr(knowledge, "run_knowledge_qa", _record_tool(recorded, INTENT_KNOWLEDGE_QA))

    response = engine.answer_office_request(
        "What is the VPN policy?", OfficeRunOptions(web_search=True)
    )

    assert recorded == [{"web_search_enabled": False}]
    assert response.run_settings is not None
    assert response.run_settings.effective.web_search is False


def test_unknown_intent_still_reports_run_settings(monkeypatch):
    _open_policy(monkeypatch)

    response = engine.answer_office_request(
        "order lunch for the team", OfficeRunOptions(llm_assist=True)
    )

    assert response.run_settings is not None
    assert response.run_settings.applicability.llm_assist is False


def test_options_do_not_influence_routing(monkeypatch):
    """Routing runs before resolution and must be identical either way."""

    _open_policy(monkeypatch)
    monkeypatch.setattr(email, "summarize_emails", _record_tool([], INTENT_EMAIL_SUMMARY))

    baseline = engine.answer_office_request("summarize my unread emails")
    strict = engine.answer_office_request(
        "summarize my unread emails", OfficeRunOptions(PRIVACY_STRICT)
    )

    assert baseline.intent == strict.intent == INTENT_EMAIL_SUMMARY


# --- 12. No environment variable or module global is mutated ----------------


def test_a_strict_run_mutates_no_environment_variable(monkeypatch):
    _open_policy(monkeypatch)
    monkeypatch.setattr(email, "summarize_emails", _record_tool([], INTENT_EMAIL_SUMMARY))
    before = dict(os.environ)

    engine.answer_office_request(
        "summarize my unread emails",
        OfficeRunOptions(privacy_mode=PRIVACY_STRICT, llm_assist=True, web_search=True),
    )

    assert dict(os.environ) == before


def test_a_strict_run_does_not_change_the_server_policy_readers(monkeypatch):
    """Server policy is read, never written: the readers answer the same after."""

    _open_policy(monkeypatch)
    monkeypatch.setattr(knowledge, "run_knowledge_qa", _record_tool([], INTENT_KNOWLEDGE_QA))

    engine.answer_office_request(
        "What is the VPN policy?", OfficeRunOptions(privacy_mode=PRIVACY_STRICT)
    )

    assert llm_config.office_llm_enabled() is True
    assert knowledge.web_search_available() is True


# --- 11. Concurrent requests with opposite settings stay isolated -----------


def test_two_concurrent_requests_with_opposite_settings_do_not_interfere(monkeypatch):
    _open_policy(monkeypatch)
    seen: dict[bool, list[bool | None]] = {True: [], False: []}

    def _tool(_text, *, llm_assist_enabled=None):
        # Yield the GIL mid-call so the two runs genuinely interleave.
        for _ in range(200):
            pass
        seen[bool(llm_assist_enabled)].append(llm_assist_enabled)
        return ToolResult(tool=INTENT_EMAIL_SUMMARY, content=f"assist={llm_assist_enabled}")

    monkeypatch.setattr(email, "summarize_emails", _tool)

    def _run(enabled):
        return engine.answer_office_request(
            "summarize my unread emails", OfficeRunOptions(llm_assist=enabled)
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_run, [True, False] * 25))

    enabled_runs = [r for r in results if r.run_settings.effective.llm_assist]
    disabled_runs = [r for r in results if not r.run_settings.effective.llm_assist]

    assert len(enabled_runs) == len(disabled_runs) == 25
    assert all(r.content == "assist=True" for r in enabled_runs)
    assert all(r.content == "assist=False" for r in disabled_runs)


# --- 13. Deterministic capabilities keep byte-for-byte identical output ------


@pytest.mark.parametrize(
    "request_text",
    [
        "what meetings do I have today?",
        "show my open tickets",
        "prepare me for my next meeting",
        "what approvals are pending?",
    ],
)
def test_deterministic_capabilities_are_byte_for_byte_unchanged(request_text):
    """Real mock tools, no patching: options must not alter their output."""

    baseline = engine.answer_office_request(request_text)
    with_options = engine.answer_office_request(
        request_text,
        OfficeRunOptions(privacy_mode=PRIVACY_STRICT, llm_assist=True, web_search=True),
    )

    assert with_options.content == baseline.content
    assert with_options.intent == baseline.intent
    assert with_options.stop_reason == baseline.stop_reason


def test_email_output_is_unchanged_when_the_assist_is_not_effective(monkeypatch):
    """With the assist off, the real email tool's text is identical either way."""

    monkeypatch.setattr(llm_config, "office_llm_enabled", lambda: False)

    baseline = engine.answer_office_request("summarize my unread emails")
    strict = engine.answer_office_request(
        "summarize my unread emails",
        OfficeRunOptions(privacy_mode=PRIVACY_STRICT, llm_assist=True),
    )

    assert strict.content == baseline.content
    assert strict.stop_reason == baseline.stop_reason == ""


# --- 14. Knowledge Q&A uses the existing AnswerOptions seam -----------------


def test_knowledge_adapter_passes_an_answer_options_instance(monkeypatch):
    from enterprise_rag.graph.engine import AnswerOptions

    captured = []

    def fake_answer_question(question, options=None):
        captured.append(options)
        return _minimal_answer_result()

    monkeypatch.setattr(knowledge, "answer_question", fake_answer_question)

    knowledge.run_knowledge_qa("What is the VPN policy?", web_search_enabled=True)

    assert len(captured) == 1
    assert isinstance(captured[0], AnswerOptions)
    assert captured[0].web_search_enabled is True


def test_knowledge_adapter_forwards_a_disabled_web_search(monkeypatch):
    captured = []

    def fake_answer_question(question, options=None):
        captured.append(options)
        return _minimal_answer_result()

    monkeypatch.setattr(knowledge, "answer_question", fake_answer_question)

    knowledge.run_knowledge_qa("What is the VPN policy?", web_search_enabled=False)

    assert captured[0].web_search_enabled is False


def test_knowledge_adapter_omits_options_entirely_when_unset(monkeypatch):
    """No per-run override means the engine's own default path, untouched."""

    captured = []

    def fake_answer_question(question, *args):
        captured.append(args)
        return _minimal_answer_result()

    monkeypatch.setattr(knowledge, "answer_question", fake_answer_question)

    knowledge.run_knowledge_qa("What is the VPN policy?")

    assert captured == [()]


def _minimal_answer_result():
    from types import SimpleNamespace

    return SimpleNamespace(
        raw_state={"generation": "ANSWER", "stop_reason": "", "documents": []},
        stop_reason="",
        sources=[],
        run_id="run-1",
        node_path=[],
        node_timings_ms=[],
        total_duration_ms=0.0,
        retries=0,
        tracked_llm_calls=0,
        web_search_count=0,
        web_result_grading_count=0,
        web_search_enabled=False,
        web_fallback_policy="conservative",
    )
