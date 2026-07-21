"""App-factory privacy regressions, using the real environment readers/guard."""

import os

import pytest
from fastapi import FastAPI

from api.app import create_app
from enterprise_rag.graph.config import offline_mode, privacy_mode
from enterprise_rag.runtime_privacy import _TRACING_ENV_VARS

_API_ROUTES = {("/api/health", "GET"), ("/api/agent/run", "POST")}
_SUPPORTED_TRACING_ENV_VARS = ("LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING")


def _route_inventory(app: FastAPI) -> set[tuple[str, str]]:
    return {(route.path, method) for route in app.routes for method in (route.methods or set())}


def test_factory_regression_covers_every_supported_tracing_variable():
    assert _TRACING_ENV_VARS == _SUPPORTED_TRACING_ENV_VARS


@pytest.mark.parametrize(
    ("privacy_enabled", "offline_enabled"),
    [(True, False), (False, True)],
    ids=["server-privacy-mode", "offline-mode"],
)
def test_create_app_forces_tracing_off_when_privacy_restrictions_are_active(
    monkeypatch, privacy_enabled, offline_enabled
):
    monkeypatch.setenv("PRIVACY_MODE", str(privacy_enabled).lower())
    monkeypatch.setenv("OFFLINE_MODE", str(offline_enabled).lower())
    for name in _SUPPORTED_TRACING_ENV_VARS:
        monkeypatch.setenv(name, "true")

    assert os.environ["PYTHON_DOTENV_DISABLED"] == "1"
    assert privacy_mode() is privacy_enabled
    assert offline_mode() is offline_enabled

    app = create_app()

    assert isinstance(app, FastAPI)
    assert _API_ROUTES <= _route_inventory(app)
    for name in _SUPPORTED_TRACING_ENV_VARS:
        assert os.environ[name] == "false"


def test_create_app_leaves_tracing_configuration_untouched_when_modes_are_off(monkeypatch):
    monkeypatch.setenv("PRIVACY_MODE", "false")
    monkeypatch.setenv("OFFLINE_MODE", "false")
    for name in _SUPPORTED_TRACING_ENV_VARS:
        monkeypatch.setenv(name, "true")

    assert privacy_mode() is False
    assert offline_mode() is False

    app = create_app()

    assert _API_ROUTES <= _route_inventory(app)
    for name in _SUPPORTED_TRACING_ENV_VARS:
        assert os.environ[name] == "true"
