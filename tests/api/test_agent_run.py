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
from office_agent.schemas import (
    INTENT_CALENDAR_LOOKUP,
    INTENT_DAILY_BRIEFING,
    INTENT_EMAIL_SUMMARY,
    INTENT_KNOWLEDGE_QA,
    INTENT_MEETING_AGENT,
    INTENT_TICKET_ASSISTANT,
    INTENT_UNKNOWN,
    INTENT_WORKFLOW_APPROVAL,
    OfficeAgentResponse,
)

RUN_URL = "/api/agent/run"


def _client(monkeypatch, response, *, llm_enabled=False):
    """Patch the engine seam to return `response`, and the assist flag reader."""

    monkeypatch.setattr(app_module, "office_llm_enabled", lambda: llm_enabled)
    monkeypatch.setattr(app_module, "answer_office_request", lambda _text: response)
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

    def fake_engine(text):
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


def test_observability_is_null_in_phase_2(monkeypatch):
    """Phase 4 adds the office-agent carry-through; until then, never fabricated."""

    client = _client(
        monkeypatch,
        OfficeAgentResponse(
            intent=INTENT_KNOWLEDGE_QA, content="A", tool="knowledge_qa", run_id="r1"
        ),
    )

    assert _run(client).json()["observability"] is None


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


# --- error handling ---------------------------------------------------------


def test_engine_exception_returns_500_with_type_name_only(monkeypatch):
    monkeypatch.setattr(app_module, "office_llm_enabled", lambda: False)

    def boom(_text):
        raise RuntimeError("secret path C:/keys/openai.txt leaked in the message")

    monkeypatch.setattr(app_module, "answer_office_request", boom)
    client = TestClient(app_module.create_app(), raise_server_exceptions=False)

    response = _run(client)

    assert response.status_code == 500
    assert response.json() == {"error": "RuntimeError"}


def test_engine_exception_message_is_not_exposed(monkeypatch):
    monkeypatch.setattr(app_module, "office_llm_enabled", lambda: False)

    def boom(_text):
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
