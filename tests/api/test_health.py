"""
Unit tests for `GET /api/health` (api/app.py).

Every flag reader is monkeypatched at the seam `api.app` imported, so these
tests need no API keys, no Chroma, no web search, and never touch the real
environment.

Scope note: these tests deliberately do NOT re-test the enterprise_rag privacy
floor (that `web_search_enabled()` returns False under a mode). That logic is
owned and tested by `tests/enterprise_rag/`. The adapter's only responsibility —
and all that is asserted here — is that it reports whatever the existing
effective reader returns.
"""

import pytest
from fastapi.testclient import TestClient

from api import app as app_module

HEALTH_FIELDS = {
    "status",
    "privacy_mode",
    "offline_mode",
    "office_llm_enabled",
    "web_search_effective",
}


def _client(monkeypatch, *, privacy, offline, llm_enabled, web_search):
    """Build a TestClient with all four flag readers patched to fixed values."""

    monkeypatch.setattr(app_module, "privacy_mode", lambda: privacy)
    monkeypatch.setattr(app_module, "offline_mode", lambda: offline)
    monkeypatch.setattr(app_module, "office_llm_enabled", lambda: llm_enabled)
    monkeypatch.setattr(app_module, "web_search_enabled", lambda: web_search)
    return TestClient(app_module.create_app())


def test_health_reports_all_flags_false(monkeypatch):
    client = _client(monkeypatch, privacy=False, offline=False, llm_enabled=False, web_search=False)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "privacy_mode": False,
        "offline_mode": False,
        "office_llm_enabled": False,
        "web_search_effective": False,
    }


def test_health_reports_all_flags_true(monkeypatch):
    client = _client(monkeypatch, privacy=True, offline=True, llm_enabled=True, web_search=True)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "privacy_mode": True,
        "offline_mode": True,
        "office_llm_enabled": True,
        "web_search_effective": True,
    }


def test_health_response_has_exactly_the_contract_fields(monkeypatch):
    client = _client(monkeypatch, privacy=False, offline=False, llm_enabled=False, web_search=True)

    payload = client.get("/api/health").json()

    assert set(payload) == HEALTH_FIELDS


@pytest.mark.parametrize("value", [True, False])
def test_privacy_mode_is_mapped_from_the_reader(monkeypatch, value):
    client = _client(monkeypatch, privacy=value, offline=False, llm_enabled=False, web_search=True)

    assert client.get("/api/health").json()["privacy_mode"] is value


@pytest.mark.parametrize("value", [True, False])
def test_offline_mode_is_mapped_from_the_reader(monkeypatch, value):
    client = _client(monkeypatch, privacy=False, offline=value, llm_enabled=False, web_search=True)

    assert client.get("/api/health").json()["offline_mode"] is value


@pytest.mark.parametrize("value", [True, False])
def test_office_llm_enabled_is_mapped_from_the_reader(monkeypatch, value):
    client = _client(monkeypatch, privacy=False, offline=False, llm_enabled=value, web_search=True)

    assert client.get("/api/health").json()["office_llm_enabled"] is value


@pytest.mark.parametrize("value", [True, False])
def test_web_search_effective_is_mapped_from_the_effective_reader(monkeypatch, value):
    """The adapter reports the existing effective reader's value, unmodified."""

    client = _client(monkeypatch, privacy=False, offline=False, llm_enabled=False, web_search=value)

    assert client.get("/api/health").json()["web_search_effective"] is value


def test_web_search_effective_is_false_when_the_reader_returns_false(monkeypatch):
    """Explicit coverage of the falsy case at the `api.app.web_search_enabled` seam.

    The reader itself applies the privacy floor; the adapter must neither
    re-derive it nor override it.
    """

    monkeypatch.setattr(app_module, "web_search_enabled", lambda: False)
    monkeypatch.setattr(app_module, "privacy_mode", lambda: True)
    monkeypatch.setattr(app_module, "offline_mode", lambda: False)
    monkeypatch.setattr(app_module, "office_llm_enabled", lambda: False)
    client = TestClient(app_module.create_app())

    payload = client.get("/api/health").json()

    assert payload["web_search_effective"] is False
    assert payload["status"] == "ok"


def test_status_is_always_ok(monkeypatch):
    client = _client(monkeypatch, privacy=True, offline=False, llm_enabled=False, web_search=False)

    assert client.get("/api/health").json()["status"] == "ok"
