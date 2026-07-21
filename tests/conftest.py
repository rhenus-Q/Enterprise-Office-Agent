"""Shared pytest bootstrap and real-model test gating.

Ordinary tests must be independent of a developer's local ``.env``. This file
is loaded before test-module collection, so it establishes the safe environment
before any project module can read feature flags or call ``load_dotenv()``.

Real-model tests are marked ``real_model`` and require two independent signals:
``RUN_REAL_MODEL_TESTS=1`` plus every credential named by the marker. A key by
itself is never authorization to make a paid provider request.
"""

import os
from collections.abc import Mapping, MutableMapping, Sequence

import pytest

_TRUTHY_VALUES = {"true", "1", "yes", "on"}
_REAL_MODEL_OPT_IN = "RUN_REAL_MODEL_TESTS"
_DEFAULT_REAL_MODEL_CREDENTIALS = ("OPENAI_API_KEY",)


def isolate_ordinary_test_environment(environ: MutableMapping[str, str]) -> None:
    """Force the keys-free pytest defaults into ``environ``.

    These assignments deliberately overwrite inherited values. ``setdefault``
    would preserve a contaminated parent process. ``PYTHON_DOTENV_DISABLED`` is
    python-dotenv's supported process switch, so later production-entry-point
    calls to ``load_dotenv()`` are harmless no-ops during ordinary pytest.
    """

    environ["OFFICE_LLM_ENABLED"] = "false"
    environ["PYTHON_DOTENV_DISABLED"] = "1"


isolate_ordinary_test_environment(os.environ)


def _is_truthy(value: str | None) -> bool:
    return value is not None and value.strip().lower() in _TRUTHY_VALUES


def real_model_skip_reason(
    required_credentials: Sequence[str] = _DEFAULT_REAL_MODEL_CREDENTIALS,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """Return why a paid test is disabled, or ``None`` when it may run.

    ``environ`` makes the authorization matrix directly testable without
    mutating the real test process or spawning a provider-backed test.
    """

    env = os.environ if environ is None else environ

    if not _is_truthy(env.get(_REAL_MODEL_OPT_IN)):
        return f"set {_REAL_MODEL_OPT_IN}=1 to authorize real-model tests (may incur cost)"

    if _is_truthy(env.get("OFFLINE_MODE")):
        return "OFFLINE_MODE is enabled; real-model tests must not call external services"

    missing = [name for name in required_credentials if not env.get(name, "").strip()]
    if missing:
        return f"missing required credential(s): {', '.join(missing)}"

    return None


# Backward-compatible decorator name used by the existing OpenAI integration
# tests. It now classifies tests with the canonical marker; the collection hook
# below owns the opt-in and credential gate in one place.
requires_openai = pytest.mark.real_model("OPENAI_API_KEY")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip every marked paid test unless its full authorization gate passes."""

    for item in items:
        marker = item.get_closest_marker("real_model")
        if marker is None:
            continue

        required_credentials = tuple(str(name) for name in marker.args)
        reason = real_model_skip_reason(required_credentials or _DEFAULT_REAL_MODEL_CREDENTIALS)
        if reason is not None:
            item.add_marker(pytest.mark.skip(reason=reason))
