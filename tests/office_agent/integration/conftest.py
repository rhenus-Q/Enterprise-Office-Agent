"""Scoped environment for explicitly authorized Office real-model tests."""

import pytest


@pytest.fixture(autouse=True)
def enable_office_llm_for_real_model_test(request, monkeypatch):
    """Enable the assist only inside a marked test; monkeypatch restores it."""

    if request.node.get_closest_marker("real_model") is not None:
        monkeypatch.setenv("OFFICE_LLM_ENABLED", "true")
