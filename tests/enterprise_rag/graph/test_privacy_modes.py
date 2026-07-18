"""
Tests for the hierarchical runtime privacy modes (PRIVACY_MODE / OFFLINE_MODE).

Covers four layers, all fully mocked -- no API keys, no network, no client ever
constructed:
1. enterprise_rag.graph.config mode parsing and the web_search_enabled() floor.
2. enterprise_rag.runtime_privacy.enforce_tracing_privacy() env neutralization.
3. enterprise_rag.ingestion fail-closed guards (script entry + get_retriever).
4. The engine's OFFLINE_MODE short-circuit, proven by poisoning the compiled
   graph so any attempt to run it fails the test.

Modes are manipulated only via monkeypatch, so nothing leaks into other tests.
"""

import json
import os
from types import SimpleNamespace

import pytest

import enterprise_rag.graph.graph as graph_module
import enterprise_rag.ingestion as ingestion
from enterprise_rag.graph.config import (
    WEB_FALLBACK_AGGRESSIVE,
    offline_mode,
    privacy_mode,
    privacy_restrictions_active,
    web_search_enabled,
)
from enterprise_rag.graph.consts import STOP_REASON_OFFLINE_MODE
from enterprise_rag.graph.engine import AnswerOptions, answer_question, seed_state
from enterprise_rag.graph.formatting import OFFLINE_MODE_NOTE, format_answer
from enterprise_rag.runtime_privacy import _TRACING_ENV_VARS, enforce_tracing_privacy

MODE_VARS = ("PRIVACY_MODE", "OFFLINE_MODE")


@pytest.fixture
def modes_off(monkeypatch):
    """Both modes explicitly unset -- the default, pre-feature behavior."""

    for name in MODE_VARS:
        monkeypatch.delenv(name, raising=False)


def _enable(monkeypatch, mode, value="true"):
    """Enable one mode and explicitly disable the other, isolating precedence."""

    for name in MODE_VARS:
        monkeypatch.setenv(name, value if name == mode else "false")


# ---------------------------------------------------------------------------
# Mode parsing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", MODE_VARS)
@pytest.mark.parametrize("value", ["true", "True", "TRUE", " true ", "1", "yes", "on", "ON"])
def test_truthy_values_enable_a_mode(monkeypatch, mode, value):
    _enable(monkeypatch, mode, value)

    reader = privacy_mode if mode == "PRIVACY_MODE" else offline_mode
    assert reader() is True
    assert privacy_restrictions_active() is True


@pytest.mark.parametrize("mode", MODE_VARS)
@pytest.mark.parametrize("value", ["false", "0", "no", "off", "", "bogus", "TRUEISH"])
def test_non_truthy_values_leave_a_mode_off(monkeypatch, mode, value):
    # Default-off parsing: only an explicit truthy value activates a restriction,
    # so a typo can never silently turn a mode on (or off, once on).
    for name in MODE_VARS:
        monkeypatch.setenv(name, value)

    reader = privacy_mode if mode == "PRIVACY_MODE" else offline_mode
    assert reader() is False
    assert privacy_restrictions_active() is False


def test_modes_default_to_off_when_unset(modes_off):
    assert privacy_mode() is False
    assert offline_mode() is False
    assert privacy_restrictions_active() is False


def test_offline_mode_alone_activates_restrictions(monkeypatch):
    # Hierarchy: OFFLINE_MODE implies every PRIVACY_MODE restriction, even with
    # PRIVACY_MODE explicitly false.
    _enable(monkeypatch, "OFFLINE_MODE")

    assert privacy_mode() is False
    assert privacy_restrictions_active() is True


# ---------------------------------------------------------------------------
# web_search_enabled() floor
# ---------------------------------------------------------------------------


def test_web_search_enabled_unchanged_when_modes_off(modes_off, monkeypatch):
    monkeypatch.delenv("WEB_SEARCH_ENABLED", raising=False)
    assert web_search_enabled() is True

    monkeypatch.setenv("WEB_SEARCH_ENABLED", "false")
    assert web_search_enabled() is False


@pytest.mark.parametrize("mode", MODE_VARS)
def test_mode_forces_web_search_off_over_explicit_true(monkeypatch, mode):
    # A mode can only restrict: an explicit WEB_SEARCH_ENABLED=true loses.
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "true")
    _enable(monkeypatch, mode)

    assert web_search_enabled() is False


# ---------------------------------------------------------------------------
# seed_state floor (applies to every caller, including explicit per-run options)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", MODE_VARS)
def test_seed_state_forces_web_search_off_over_explicit_option(monkeypatch, mode):
    _enable(monkeypatch, mode)

    state = seed_state("Q", web_search_enabled=True)

    assert state["web_search_enabled"] is False


@pytest.mark.parametrize("mode", MODE_VARS)
def test_seed_state_leaves_fallback_policy_untouched(monkeypatch, mode):
    # Modes govern egress, not the fallback policy: policy resolution is unchanged.
    _enable(monkeypatch, mode)

    state = seed_state("Q", web_fallback_policy="aggressive")

    assert state["web_fallback_policy"] == WEB_FALLBACK_AGGRESSIVE


def test_seed_state_respects_explicit_option_when_modes_off(modes_off, monkeypatch):
    monkeypatch.setenv("WEB_SEARCH_ENABLED", "false")

    # Existing behavior preserved: without a mode, an explicit True still wins.
    assert seed_state("Q", web_search_enabled=True)["web_search_enabled"] is True


# ---------------------------------------------------------------------------
# enforce_tracing_privacy()
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("mode", MODE_VARS)
def test_enforce_tracing_privacy_disables_both_tracing_vars(monkeypatch, mode):
    # Both the legacy and current LangSmith variable names must be neutralized,
    # so tracing is off regardless of the installed langchain version.
    for name in _TRACING_ENV_VARS:
        monkeypatch.setenv(name, "true")
    _enable(monkeypatch, mode)

    enforce_tracing_privacy()

    for name in _TRACING_ENV_VARS:
        assert os.environ[name] == "false"


def test_enforce_tracing_privacy_is_a_no_op_when_modes_off(modes_off, monkeypatch):
    for name in _TRACING_ENV_VARS:
        monkeypatch.setenv(name, "true")

    enforce_tracing_privacy()

    for name in _TRACING_ENV_VARS:
        assert os.environ[name] == "true"  # existing configuration untouched


def test_enforce_tracing_privacy_is_idempotent(monkeypatch):
    _enable(monkeypatch, "PRIVACY_MODE")

    enforce_tracing_privacy()
    enforce_tracing_privacy()

    for name in _TRACING_ENV_VARS:
        assert os.environ[name] == "false"


# ---------------------------------------------------------------------------
# Ingestion fail-closed guards
# ---------------------------------------------------------------------------


def _poison_embeddings(monkeypatch):
    """Make any embeddings/Chroma construction fail the test loudly."""

    def _boom(*args, **kwargs):
        raise AssertionError("no external client may be constructed under OFFLINE_MODE")

    monkeypatch.setattr(ingestion, "OpenAIEmbeddings", _boom)
    monkeypatch.setattr(ingestion, "Chroma", _boom)


def test_get_retriever_refuses_offline_without_constructing_a_client(monkeypatch):
    _enable(monkeypatch, "OFFLINE_MODE")
    _poison_embeddings(monkeypatch)
    ingestion.get_retriever.cache_clear()

    with pytest.raises(RuntimeError) as excinfo:
        ingestion.get_retriever()

    assert "OFFLINE_MODE" in str(excinfo.value)
    ingestion.get_retriever.cache_clear()


def test_ingestion_script_entry_exits_before_building_anything(monkeypatch, capsys):
    _enable(monkeypatch, "OFFLINE_MODE")
    monkeypatch.setattr(
        ingestion,
        "build_vectorstore",
        lambda: (_ for _ in ()).throw(AssertionError("build_vectorstore must not run offline")),
    )

    with pytest.raises(SystemExit) as excinfo:
        ingestion.main()

    assert excinfo.value.code == ingestion.OFFLINE_EXIT_CODE
    assert "OFFLINE_MODE" in capsys.readouterr().out


def test_ingestion_guards_do_not_fire_when_modes_off(modes_off, monkeypatch):
    built = {"count": 0}
    monkeypatch.setattr(ingestion, "build_vectorstore", lambda: built.__setitem__("count", 1))

    ingestion.main()

    assert built["count"] == 1  # normal ingestion path is unchanged


# ---------------------------------------------------------------------------
# Engine OFFLINE_MODE short-circuit
# ---------------------------------------------------------------------------


def _poison_graph(monkeypatch):
    """Replace the compiled graph so ANY execution attempt fails the test."""

    def _boom(*args, **kwargs):
        raise AssertionError("the graph must not run under OFFLINE_MODE")

    monkeypatch.setattr(graph_module, "app", SimpleNamespace(stream=_boom, invoke=_boom))


def test_answer_question_offline_returns_deterministic_result_without_the_graph(monkeypatch):
    _enable(monkeypatch, "OFFLINE_MODE")
    _poison_graph(monkeypatch)

    result = answer_question("What is the VPN policy?")

    assert result.stop_reason == STOP_REASON_OFFLINE_MODE
    assert result.answer == ""
    assert result.sources == []
    assert result.node_path == []
    assert result.web_search_enabled is False
    # Counters stay zero: nothing was called, so nothing was spent.
    assert result.tracked_llm_calls == 0
    assert result.web_search_count == 0
    assert result.retries == 0
    # Observability is still populated for a refused run.
    assert result.run_id
    assert result.question_sha256


def test_offline_result_renders_the_honest_caveat(monkeypatch):
    _enable(monkeypatch, "OFFLINE_MODE")
    _poison_graph(monkeypatch)

    result = answer_question("Q")

    assert OFFLINE_MODE_NOTE in format_answer(result.raw_state)


def test_offline_run_still_redacts_secrets_from_the_question(monkeypatch):
    _enable(monkeypatch, "OFFLINE_MODE")
    _poison_graph(monkeypatch)

    result = answer_question("my key is sk-live-CONFIRMEDSECRET0123")

    assert result.input_redacted is True
    assert "CONFIRMEDSECRET" not in result.question


def test_offline_run_still_writes_a_metadata_only_trace(monkeypatch, tmp_path):
    _enable(monkeypatch, "OFFLINE_MODE")
    _poison_graph(monkeypatch)
    trace_path = tmp_path / "trace.json"

    answer_question("Q", AnswerOptions(trace_path=trace_path))

    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace["stop_reason"] == STOP_REASON_OFFLINE_MODE
    assert trace["web_search_enabled"] is False
    assert trace["sources"] == []


def test_privacy_mode_alone_still_runs_the_graph(monkeypatch):
    # PRIVACY_MODE preserves the OpenAI RAG path: only OFFLINE_MODE short-circuits.
    _enable(monkeypatch, "PRIVACY_MODE")

    calls = []

    def _fake_invoke(state):
        calls.append(state)
        return {**state, "generation": "LOCAL ANSWER", "stop_reason": ""}

    # No `stream` attribute -> the engine falls back to invoke().
    monkeypatch.setattr(graph_module, "app", SimpleNamespace(invoke=_fake_invoke))

    result = answer_question("Q", AnswerOptions(web_search_enabled=True))

    assert result.answer == "LOCAL ANSWER"
    assert result.stop_reason == ""
    assert len(calls) == 1
    # ...but web search is still forced off for the run.
    assert calls[0]["web_search_enabled"] is False
    assert result.web_search_enabled is False
