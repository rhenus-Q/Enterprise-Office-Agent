"""
Unit tests for `POST /api/agent/run` (api/app.py).

The engine is mocked at the seam the adapter imported
(`api.app.answer_office_request`), so the real Office Agent never runs and no
API keys, Chroma index, web search, or other external service is required —
mirroring the `tests/office_agent/` style.

Covered: 1:1 field mapping, verbatim content, adapter-measured duration, the
exhaustive execution_mode matrix, type-name-only error handling, and the exact
`text` validation boundaries.
"""

import pytest
from fastapi.testclient import TestClient

from api import app as app_module
from enterprise_rag.graph.consts import STOP_REASON_OFFLINE_MODE
from office_agent.llm_assist.config import STOP_REASON_LLM_ASSIST_ERROR
from office_agent.run_settings import (
    CONSTRAINT_SERVER_PRIVACY_MODE,
    CONSTRAINT_WEB_SEARCH_NOT_APPLICABLE,
    LLM_ASSIST_INTENTS,
    OfficeRunOptions,
    ResolvedRunSettings,
    RunSettingsApplicability,
    RunSettingsValues,
)
from office_agent.schemas import (
    INTENT_CALENDAR_LOOKUP,
    INTENT_DAILY_BRIEFING,
    INTENT_EMAIL_SUMMARY,
    INTENT_KNOWLEDGE_QA,
    INTENT_MEETING_AGENT,
    INTENT_TICKET_ASSISTANT,
    INTENT_UNKNOWN,
    INTENT_WORKFLOW_APPROVAL,
    OFFICE_INTENTS,
    KnowledgeObservability,
    NodeTiming,
    OfficeAgentResponse,
)

RUN_URL = "/api/agent/run"


def _client(monkeypatch, response, *, llm_enabled=False):
    """Patch the engine seam to return `response`, and the assist flag reader."""

    monkeypatch.setattr(app_module, "office_llm_enabled", lambda: llm_enabled)
    monkeypatch.setattr(app_module, "answer_office_request", lambda _text, _options=None: response)
    return TestClient(app_module.create_app())


def _run(client, text="anything"):
    return client.post(RUN_URL, json={"text": text})


# --- 1:1 field mapping ------------------------------------------------------


def test_every_office_agent_response_field_maps_one_to_one(monkeypatch):
    engine_response = OfficeAgentResponse(
        intent=INTENT_KNOWLEDGE_QA,
        content="ANSWER TEXT",
        tool=INTENT_KNOWLEDGE_QA,
        stop_reason="web_search_disabled",
        sources=["VPN Policy", "Onboarding Guide"],
        run_id="run-123",
    )
    client = _client(monkeypatch, engine_response)

    payload = _run(client).json()

    assert payload["intent"] == INTENT_KNOWLEDGE_QA
    assert payload["tool"] == INTENT_KNOWLEDGE_QA
    assert payload["content"] == "ANSWER TEXT"
    assert payload["stop_reason"] == "web_search_disabled"
    assert payload["sources"] == ["VPN Policy", "Onboarding Guide"]
    assert payload["run_id"] == "run-123"


def test_content_is_returned_verbatim(monkeypatch):
    """Whitespace, blank lines, and section markers must survive untouched."""

    content = "  Line one\n\nLine two\n\nSources:\n- Doc A  "
    client = _client(
        monkeypatch,
        OfficeAgentResponse(intent=INTENT_EMAIL_SUMMARY, content=content, tool="email_summary"),
    )

    assert _run(client).json()["content"] == content


def test_unknown_intent_maps_null_tool_and_empty_defaults(monkeypatch):
    client = _client(
        monkeypatch,
        OfficeAgentResponse(intent=INTENT_UNKNOWN, content="UNSUPPORTED", tool=None),
    )

    payload = _run(client).json()

    assert payload["tool"] is None
    assert payload["stop_reason"] == ""
    assert payload["sources"] == []
    assert payload["run_id"] is None


def test_user_text_is_passed_to_the_engine_unmodified(monkeypatch):
    seen = []
    monkeypatch.setattr(app_module, "office_llm_enabled", lambda: False)

    def fake_engine(text, _options=None):
        seen.append(text)
        return OfficeAgentResponse(intent=INTENT_UNKNOWN, content="X", tool=None)

    monkeypatch.setattr(app_module, "answer_office_request", fake_engine)
    client = TestClient(app_module.create_app())

    _run(client, "  Summarize my unread emails  ")

    assert seen == ["  Summarize my unread emails  "]


def test_duration_ms_is_non_negative(monkeypatch):
    client = _client(
        monkeypatch,
        OfficeAgentResponse(intent=INTENT_CALENDAR_LOOKUP, content="C", tool="calendar_lookup"),
    )

    assert _run(client).json()["duration_ms"] >= 0


# --- observability pass-through (Phase 4) -----------------------------------


def _knowledge_observability():
    return KnowledgeObservability(
        run_id="run-123",
        node_path=["retrieve", "grade_documents", "generate"],
        node_timings_ms=[
            NodeTiming(node="retrieve", duration_ms=12.5),
            NodeTiming(node="grade_documents", duration_ms=340.0),
            NodeTiming(node="generate", duration_ms=1180.75),
        ],
        total_duration_ms=1533.25,
        retries=1,
        tracked_llm_calls=4,
        web_search_count=2,
        web_result_grading_count=6,
        web_search_enabled=True,
        web_fallback_policy="conservative",
        caveat="Web search was disabled for this run.",
    )


def test_knowledge_observability_is_passed_through_field_for_field(monkeypatch):
    client = _client(
        monkeypatch,
        OfficeAgentResponse(
            intent=INTENT_KNOWLEDGE_QA,
            content="A",
            tool="knowledge_qa",
            run_id="run-123",
            observability=_knowledge_observability(),
        ),
    )

    observability = _run(client).json()["observability"]

    assert observability == {
        "run_id": "run-123",
        "node_path": ["retrieve", "grade_documents", "generate"],
        "node_timings_ms": [
            {"node": "retrieve", "duration_ms": 12.5},
            {"node": "grade_documents", "duration_ms": 340.0},
            {"node": "generate", "duration_ms": 1180.75},
        ],
        "total_duration_ms": 1533.25,
        "retries": 1,
        "tracked_llm_calls": 4,
        "web_search_count": 2,
        "web_result_grading_count": 6,
        "web_search_enabled": True,
        "web_fallback_policy": "conservative",
        "caveat": "Web search was disabled for this run.",
    }


def test_observability_is_null_when_the_engine_reports_none(monkeypatch):
    """Not fabricated: a knowledge response without metadata stays null."""

    client = _client(
        monkeypatch,
        OfficeAgentResponse(
            intent=INTENT_KNOWLEDGE_QA, content="A", tool="knowledge_qa", run_id="r1"
        ),
    )

    assert _run(client).json()["observability"] is None


@pytest.mark.parametrize(
    "intent",
    [
        INTENT_EMAIL_SUMMARY,
        INTENT_CALENDAR_LOOKUP,
        INTENT_TICKET_ASSISTANT,
        INTENT_DAILY_BRIEFING,
        INTENT_MEETING_AGENT,
        INTENT_WORKFLOW_APPROVAL,
        INTENT_UNKNOWN,
    ],
)
def test_non_knowledge_intents_report_null_observability(monkeypatch, intent):
    client = _client(
        monkeypatch,
        OfficeAgentResponse(intent=intent, content="X", tool=None),
    )

    assert _run(client).json()["observability"] is None


# --- run settings: request parsing and response shape -----------------------


def _settings(
    *,
    requested=("standard", True, True),
    effective=("strict", False, False),
    applicability=(True, False),
    constraints=(CONSTRAINT_SERVER_PRIVACY_MODE, CONSTRAINT_WEB_SEARCH_NOT_APPLICABLE),
):
    return ResolvedRunSettings(
        requested=RunSettingsValues(*requested),
        effective=RunSettingsValues(*effective),
        applicability=RunSettingsApplicability(*applicability),
        constraints=tuple(constraints),
    )


def _capturing_client(monkeypatch, response, *, llm_enabled=False):
    """Patch the engine seam and record the options object it was handed."""

    seen: list[object] = []

    def fake_engine(_text, options=None):
        seen.append(options)
        return response

    monkeypatch.setattr(app_module, "office_llm_enabled", lambda: llm_enabled)
    monkeypatch.setattr(app_module, "answer_office_request", fake_engine)
    return TestClient(app_module.create_app()), seen


def test_omitting_options_sends_none_to_the_engine(monkeypatch):
    """Backward compatibility: no options means no per-run options at all."""

    client, seen = _capturing_client(
        monkeypatch,
        OfficeAgentResponse(intent=INTENT_EMAIL_SUMMARY, content="X", tool="email_summary"),
    )

    payload = client.post(RUN_URL, json={"text": "hi"}).json()

    assert seen == [None]
    assert payload["run_settings"] is None


def test_request_options_are_converted_to_office_run_options(monkeypatch):
    client, seen = _capturing_client(
        monkeypatch,
        OfficeAgentResponse(intent=INTENT_EMAIL_SUMMARY, content="X", tool="email_summary"),
    )

    client.post(
        RUN_URL,
        json={
            "text": "hi",
            "options": {"privacy_mode": "strict", "llm_assist": True, "web_search": True},
        },
    )

    assert seen == [OfficeRunOptions(privacy_mode="strict", llm_assist=True, web_search=True)]


def test_partial_options_default_to_the_conservative_values(monkeypatch):
    client, seen = _capturing_client(
        monkeypatch,
        OfficeAgentResponse(intent=INTENT_EMAIL_SUMMARY, content="X", tool="email_summary"),
    )

    client.post(RUN_URL, json={"text": "hi", "options": {"llm_assist": True}})

    assert seen == [OfficeRunOptions(privacy_mode="standard", llm_assist=True, web_search=False)]


@pytest.mark.parametrize(
    "options",
    [
        {"privacy_mode": "paranoid"},
        {"privacy_mode": 1},
        {"privacy_mode": None},
        {"llm_assist": "maybe"},
        {"web_search": 7},
        {"unknown_field": True},
    ],
)
def test_invalid_options_are_rejected_with_422(monkeypatch, options):
    client, _ = _capturing_client(
        monkeypatch,
        OfficeAgentResponse(intent=INTENT_EMAIL_SUMMARY, content="X", tool="email_summary"),
    )

    assert client.post(RUN_URL, json={"text": "hi", "options": options}).status_code == 422


def test_standard_boolean_coercion_applies_to_the_toggles(monkeypatch):
    """Pydantic's usual lax bool parsing is kept deliberately.

    Coercion here is unambiguous ("true"/"yes" -> True, anything ambiguous is a
    422), and it cannot weaken anything: server policy is applied after parsing
    regardless of how the toggle arrived.
    """

    client, seen = _capturing_client(
        monkeypatch,
        OfficeAgentResponse(intent=INTENT_EMAIL_SUMMARY, content="X", tool="email_summary"),
    )

    client.post(RUN_URL, json={"text": "hi", "options": {"llm_assist": "true"}})

    assert seen == [OfficeRunOptions(privacy_mode="standard", llm_assist=True, web_search=False)]


def test_run_settings_are_returned_field_for_field(monkeypatch):
    client, _ = _capturing_client(
        monkeypatch,
        OfficeAgentResponse(
            intent=INTENT_EMAIL_SUMMARY,
            content="X",
            tool="email_summary",
            run_settings=_settings(),
        ),
    )

    payload = client.post(RUN_URL, json={"text": "hi", "options": {}}).json()

    assert payload["run_settings"] == {
        "requested": {"privacy_mode": "standard", "llm_assist": True, "web_search": True},
        "effective": {"privacy_mode": "strict", "llm_assist": False, "web_search": False},
        "applicability": {"llm_assist": True, "web_search": False},
        "constraints": ["server_privacy_mode", "web_search_not_applicable"],
    }


def test_effective_settings_come_from_the_backend_not_the_adapter(monkeypatch):
    """The adapter transports whatever the engine resolved — it re-derives nothing."""

    client, _ = _capturing_client(
        monkeypatch,
        OfficeAgentResponse(
            intent=INTENT_KNOWLEDGE_QA,
            content="A",
            tool="knowledge_qa",
            run_settings=_settings(
                requested=("standard", False, True),
                effective=("standard", False, True),
                applicability=(False, True),
                constraints=(),
            ),
        ),
    )

    payload = client.post(RUN_URL, json={"text": "hi", "options": {"web_search": True}}).json()

    assert payload["run_settings"]["effective"]["web_search"] is True
    assert payload["run_settings"]["constraints"] == []


def test_execution_mode_respects_a_request_that_disabled_the_assist(monkeypatch):
    """Server flag on, request off: reporting "llm_assisted" would be a lie."""

    client, _ = _capturing_client(
        monkeypatch,
        OfficeAgentResponse(
            intent=INTENT_EMAIL_SUMMARY,
            content="X",
            tool="email_summary",
            run_settings=_settings(
                requested=("strict", False, False),
                effective=("strict", False, False),
                applicability=(True, False),
                constraints=(),
            ),
        ),
        llm_enabled=True,
    )

    payload = client.post(
        RUN_URL, json={"text": "hi", "options": {"privacy_mode": "strict"}}
    ).json()

    assert payload["execution_mode"] == "deterministic"


def test_execution_mode_is_llm_assisted_when_the_assist_actually_ran(monkeypatch):
    client, _ = _capturing_client(
        monkeypatch,
        OfficeAgentResponse(
            intent=INTENT_EMAIL_SUMMARY,
            content="X",
            tool="email_summary",
            run_settings=_settings(
                requested=("standard", True, False),
                effective=("standard", True, False),
                applicability=(True, False),
                constraints=(),
            ),
        ),
        llm_enabled=True,
    )

    payload = client.post(RUN_URL, json={"text": "hi", "options": {"llm_assist": True}}).json()

    assert payload["execution_mode"] == "llm_assisted"


# --- execution_mode matrix (spec §8.2, exhaustive) --------------------------


def test_unknown_intent_execution_mode_is_none(monkeypatch):
    client = _client(
        monkeypatch,
        OfficeAgentResponse(intent=INTENT_UNKNOWN, content="U", tool=None),
    )

    assert _run(client).json()["execution_mode"] == "none"


@pytest.mark.parametrize(
    "intent",
    [
        INTENT_CALENDAR_LOOKUP,
        INTENT_TICKET_ASSISTANT,
        INTENT_MEETING_AGENT,
        INTENT_WORKFLOW_APPROVAL,
    ],
)
@pytest.mark.parametrize("llm_enabled", [True, False])
def test_always_deterministic_capabilities(monkeypatch, intent, llm_enabled):
    """These four never have an LLM path, whatever the assist flag says."""

    client = _client(
        monkeypatch,
        OfficeAgentResponse(intent=intent, content="X", tool=intent),
        llm_enabled=llm_enabled,
    )

    assert _run(client).json()["execution_mode"] == "deterministic"


@pytest.mark.parametrize("intent", [INTENT_EMAIL_SUMMARY, INTENT_DAILY_BRIEFING])
def test_assist_capable_intents_are_deterministic_when_flag_off(monkeypatch, intent):
    client = _client(
        monkeypatch,
        OfficeAgentResponse(intent=intent, content="X", tool=intent),
        llm_enabled=False,
    )

    assert _run(client).json()["execution_mode"] == "deterministic"


@pytest.mark.parametrize("intent", [INTENT_EMAIL_SUMMARY, INTENT_DAILY_BRIEFING])
def test_assist_capable_intents_are_llm_assisted_when_flag_on(monkeypatch, intent):
    client = _client(
        monkeypatch,
        OfficeAgentResponse(intent=intent, content="X", tool=intent),
        llm_enabled=True,
    )

    assert _run(client).json()["execution_mode"] == "llm_assisted"


@pytest.mark.parametrize("intent", [INTENT_EMAIL_SUMMARY, INTENT_DAILY_BRIEFING])
def test_llm_assist_error_maps_to_fallback_mode(monkeypatch, intent):
    client = _client(
        monkeypatch,
        OfficeAgentResponse(
            intent=intent, content="X", tool=intent, stop_reason="llm_assist_error"
        ),
        llm_enabled=True,
    )

    assert _run(client).json()["execution_mode"] == "llm_assist_fallback"


@pytest.mark.parametrize("intent", [INTENT_EMAIL_SUMMARY, INTENT_DAILY_BRIEFING])
def test_llm_assist_error_with_flag_off_stays_deterministic(monkeypatch, intent):
    """The flag-off branch wins: no assist ran, so the mode is deterministic."""

    client = _client(
        monkeypatch,
        OfficeAgentResponse(
            intent=intent, content="X", tool=intent, stop_reason="llm_assist_error"
        ),
        llm_enabled=False,
    )

    assert _run(client).json()["execution_mode"] == "deterministic"


def test_knowledge_normal_run_is_rag_llm(monkeypatch):
    client = _client(
        monkeypatch,
        OfficeAgentResponse(intent=INTENT_KNOWLEDGE_QA, content="A", tool="knowledge_qa"),
    )

    assert _run(client).json()["execution_mode"] == "rag_llm"


def test_knowledge_offline_mode_is_rag_blocked_offline(monkeypatch):
    """The only knowledge stop reason with its own mode: no graph, no LLM ran.

    Uses the repository constant rather than a literal so this test and the
    adapter cannot drift together if the upstream value ever changes.
    """

    client = _client(
        monkeypatch,
        OfficeAgentResponse(
            intent=INTENT_KNOWLEDGE_QA,
            content="A",
            tool="knowledge_qa",
            stop_reason=STOP_REASON_OFFLINE_MODE,
        ),
    )

    assert _run(client).json()["execution_mode"] == "rag_blocked_offline"


@pytest.mark.parametrize(
    "stop_reason",
    [
        "retrieval_error",
        "web_search_error",
        "generation_error",
        "tool_error",
        "web_search_disabled",
        "web_fallback_disabled",
        "max_retries_not_grounded",
        "max_retries_not_useful",
        "budget_exhausted",
    ],
)
def test_other_knowledge_stop_reasons_stay_rag_llm(monkeypatch, stop_reason):
    """Degradation is conveyed by stop_reason, not by a different mode."""

    client = _client(
        monkeypatch,
        OfficeAgentResponse(
            intent=INTENT_KNOWLEDGE_QA, content="A", tool="knowledge_qa", stop_reason=stop_reason
        ),
    )

    payload = _run(client).json()

    assert payload["execution_mode"] == "rag_llm"
    assert payload["stop_reason"] == stop_reason


# --- lockstep: adapter classification vs the authoritative Office vocabulary --
#
# `derive_execution_mode()` keeps its own private intent sets
# (`_ALWAYS_DETERMINISTIC_INTENTS`, `_LLM_ASSIST_INTENTS`). These tests drive the
# real adapter function from the office-owned sources of truth — `OFFICE_INTENTS`
# (every routable intent) and `LLM_ASSIST_INTENTS` (the assist-capable ones) — so
# the classification cannot silently drift from that vocabulary: a new intent, or
# an intent becoming assist-capable, without a matching adapter update fails here.
# `office_llm_enabled` is patched through the same seam the endpoint tests use.


def _expected_execution_mode(intent, *, llm_enabled, stop_reason):
    """Oracle over the authoritative Office Agent vocabulary, not the adapter's
    private copies."""

    if intent == INTENT_UNKNOWN:
        return "none"
    if intent == INTENT_KNOWLEDGE_QA:
        return "rag_blocked_offline" if stop_reason == STOP_REASON_OFFLINE_MODE else "rag_llm"
    if intent in LLM_ASSIST_INTENTS:
        if not llm_enabled:
            return "deterministic"
        return (
            "llm_assist_fallback" if stop_reason == STOP_REASON_LLM_ASSIST_ERROR else "llm_assisted"
        )
    # Every remaining supported capability is deterministic. A brand-new intent
    # with no adapter branch would fall through the adapter to "none", diverging
    # from this expectation and failing the test.
    return "deterministic"


@pytest.mark.parametrize("intent", OFFICE_INTENTS)
@pytest.mark.parametrize("llm_enabled", [True, False])
@pytest.mark.parametrize(
    "stop_reason", ["", STOP_REASON_OFFLINE_MODE, STOP_REASON_LLM_ASSIST_ERROR]
)
def test_execution_mode_matches_the_office_vocabulary(
    monkeypatch, intent, llm_enabled, stop_reason
):
    """Every OFFICE_INTENTS member is classified exactly as the authoritative
    vocabulary dictates, across the full assist-flag x stop-reason matrix."""

    monkeypatch.setattr(app_module, "office_llm_enabled", lambda: llm_enabled)

    assert app_module.derive_execution_mode(intent, stop_reason) == _expected_execution_mode(
        intent, llm_enabled=llm_enabled, stop_reason=stop_reason
    )


def test_only_unknown_is_ever_classified_none(monkeypatch):
    """A supported intent must never silently fall through to "none" — which is
    exactly what an unclassified new intent would do."""

    monkeypatch.setattr(app_module, "office_llm_enabled", lambda: True)

    for intent in OFFICE_INTENTS:
        mode = app_module.derive_execution_mode(intent, "")
        if intent == INTENT_UNKNOWN:
            assert mode == "none"
        else:
            assert mode != "none", f"{intent} was silently classified as 'none'"


def test_adapter_reflects_every_office_owned_assist_intent(monkeypatch):
    """If an intent becomes assist-capable in the office-owned LLM_ASSIST_INTENTS,
    the adapter must route it through the assist branch (assisted / fallback), not
    treat it as a plain deterministic capability."""

    monkeypatch.setattr(app_module, "office_llm_enabled", lambda: True)

    for intent in LLM_ASSIST_INTENTS:
        assert app_module.derive_execution_mode(intent, "") == "llm_assisted"
        assert (
            app_module.derive_execution_mode(intent, STOP_REASON_LLM_ASSIST_ERROR)
            == "llm_assist_fallback"
        )


# --- error handling ---------------------------------------------------------


def test_engine_exception_returns_500_with_type_name_only(monkeypatch):
    monkeypatch.setattr(app_module, "office_llm_enabled", lambda: False)

    def boom(_text, _options=None):
        raise RuntimeError("secret path C:/keys/openai.txt leaked in the message")

    monkeypatch.setattr(app_module, "answer_office_request", boom)
    client = TestClient(app_module.create_app(), raise_server_exceptions=False)

    response = _run(client)

    assert response.status_code == 500
    assert response.json() == {"error": "RuntimeError"}


def test_engine_exception_message_is_not_exposed(monkeypatch):
    monkeypatch.setattr(app_module, "office_llm_enabled", lambda: False)

    def boom(_text, _options=None):
        raise ValueError("C:/secrets/api_key.env")

    monkeypatch.setattr(app_module, "answer_office_request", boom)
    client = TestClient(app_module.create_app(), raise_server_exceptions=False)

    body = _run(client).text

    assert "secrets" not in body
    assert "api_key" not in body
    assert body == '{"error":"ValueError"}'


# --- request validation boundaries ------------------------------------------


def _validation_client(monkeypatch):
    return _client(
        monkeypatch,
        OfficeAgentResponse(intent=INTENT_EMAIL_SUMMARY, content="OK", tool="email_summary"),
    )


def test_empty_text_is_rejected_with_422(monkeypatch):
    client = _validation_client(monkeypatch)

    assert client.post(RUN_URL, json={"text": ""}).status_code == 422


def test_exactly_4000_characters_is_accepted(monkeypatch):
    client = _validation_client(monkeypatch)

    response = client.post(RUN_URL, json={"text": "a" * 4000})

    assert response.status_code == 200


def test_4001_characters_is_rejected_with_422(monkeypatch):
    client = _validation_client(monkeypatch)

    assert client.post(RUN_URL, json={"text": "a" * 4001}).status_code == 422


def test_missing_text_field_is_rejected_with_422(monkeypatch):
    client = _validation_client(monkeypatch)

    assert client.post(RUN_URL, json={}).status_code == 422


def test_wrong_text_type_is_rejected_with_422(monkeypatch):
    client = _validation_client(monkeypatch)

    assert client.post(RUN_URL, json={"text": 42}).status_code == 422


def test_malformed_body_is_rejected_with_422(monkeypatch):
    client = _validation_client(monkeypatch)

    response = client.post(
        RUN_URL, content="not json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
