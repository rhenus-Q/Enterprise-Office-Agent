"""
Tests for the OFFLINE_MODE fail-closed guard in evals/enterprise_rag/run_eval.py.

Keys-free and offline: `run_eval` (the only function that touches the real graph)
is poisoned, so a guard regression fails the test instead of attempting an API
call. `--validate-only` must stay usable under any mode.
"""

import pytest

import evals.enterprise_rag.run_eval as run_eval_module

MODE_VARS = ("PRIVACY_MODE", "OFFLINE_MODE")


@pytest.fixture(autouse=True)
def _no_graph_run(monkeypatch):
    """Any attempt to actually run the eval fails loudly."""

    def _boom(*args, **kwargs):
        raise AssertionError("run_eval must not execute under the offline guard")

    monkeypatch.setattr(run_eval_module, "run_eval", _boom)


@pytest.fixture
def modes_off(monkeypatch):
    for name in MODE_VARS:
        monkeypatch.delenv(name, raising=False)


def test_offline_mode_refuses_full_run_before_executing_rows(monkeypatch, capsys):
    monkeypatch.setenv("PRIVACY_MODE", "false")
    monkeypatch.setenv("OFFLINE_MODE", "true")

    exit_code = run_eval_module.main([])

    assert exit_code == run_eval_module.EXIT_INVALID_RUN
    out = capsys.readouterr().out
    assert "CONFIG ERROR" in out
    assert "OFFLINE_MODE" in out
    # The guard must promise it changed nothing.
    assert "left untouched" in out


def test_validate_only_still_works_under_offline_mode(monkeypatch, capsys):
    # --validate-only makes no API call, so a mode must never block it.
    monkeypatch.setenv("OFFLINE_MODE", "true")

    exit_code = run_eval_module.main(["--validate-only"])

    assert exit_code == 0
    assert "Dataset OK" in capsys.readouterr().out


def test_privacy_mode_does_not_block_the_full_run(monkeypatch):
    # PRIVACY_MODE preserves the OpenAI path, so the eval is allowed to run --
    # proven by the poisoned run_eval being reached.
    monkeypatch.setenv("OFFLINE_MODE", "false")
    monkeypatch.setenv("PRIVACY_MODE", "true")

    with pytest.raises(AssertionError, match="must not execute"):
        run_eval_module.main([])
