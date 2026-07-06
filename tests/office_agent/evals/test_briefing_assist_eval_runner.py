"""
Keys-free tests for evals/office_agent/llm_assist/run_briefing_narrative_eval.py —
the standalone briefing-narrative eval runner's environment loading and
CONFIG/INFRA/EVAL_FAIL classification.

Fully offline: OpenAI is never called and no API key is required. The narrative
chain and env preconditions are patched at their seams; the deterministic dataset
validation and grounding checks run for real.
"""

import openai

import evals.office_agent.llm_assist._env as env
import evals.office_agent.llm_assist.run_briefing_narrative_eval as runner


class _SimulatedInfra(openai.OpenAIError):
    """A stand-in for any OpenAI SDK / transport failure."""


class _Ref:
    def __init__(self, source_type, id):
        self.source_type = source_type
        self.id = id


class _Narrative:
    def __init__(self, references=None, narrative="today"):
        self.references = references or []
        self.narrative = narrative


def _run_main(monkeypatch, argv):
    monkeypatch.setattr("sys.argv", ["run_briefing_narrative_eval.py", *argv])
    return runner.main()


# ---------------------------------------------------------------------------
# --validate-only stays offline and keys-free
# ---------------------------------------------------------------------------


def test_validate_only_succeeds_without_key(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def _boom(*args, **kwargs):
        raise AssertionError("validate-only must not enter full mode / load env")

    monkeypatch.setattr(runner, "_run_full", _boom)
    monkeypatch.setattr(env, "load_repo_env", _boom)

    assert _run_main(monkeypatch, ["--validate-only"]) == 0
    assert "VALID" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Full mode: missing key is a CONFIG_ERROR, not a model-quality failure
# ---------------------------------------------------------------------------


def test_full_mode_missing_key_is_config_error(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(env, "load_repo_env", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    import office_agent.llm_assist.briefing_narrative as briefing_narrative

    def _boom(*args, **kwargs):
        raise AssertionError("no model call may happen when the key is missing")

    monkeypatch.setattr(briefing_narrative, "narrate_briefing", _boom)

    output = tmp_path / "briefing_narrative_results.md"
    exit_code = runner._run_full(str(output))

    out = capsys.readouterr().out
    assert exit_code != 0
    assert "CONFIG ERROR" in out
    assert "OPENAI_API_KEY is not set" in out
    assert "case(s) passed" not in out
    assert not output.exists()


# ---------------------------------------------------------------------------
# Full mode: an infrastructure failure is INFRA_ERROR, not an ordinary FAIL
# ---------------------------------------------------------------------------


def test_full_mode_infra_error_is_not_eval_fail(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(env, "ensure_openai_api_key", lambda: None)

    import office_agent.llm_assist.briefing_narrative as briefing_narrative

    def _raise_infra(_facts):
        raise _SimulatedInfra("simulated provider outage")

    monkeypatch.setattr(briefing_narrative, "narrate_briefing", _raise_infra)

    output = tmp_path / "briefing_narrative_results.md"
    exit_code = runner._run_full(str(output))

    out = capsys.readouterr().out
    assert exit_code != 0
    assert "INFRA ERROR" in out
    assert "case(s) passed" not in out
    assert "grounding error" not in out
    assert not output.exists()


# ---------------------------------------------------------------------------
# Full mode: obtained-but-ungrounded output is an ordinary EVAL_FAIL
# ---------------------------------------------------------------------------


def test_full_mode_grounding_failure_is_eval_fail(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(env, "ensure_openai_api_key", lambda: None)

    import office_agent.llm_assist.briefing_narrative as briefing_narrative

    # References an id absent from the collected facts → real validate_narrative
    # raises ValueError.
    monkeypatch.setattr(
        briefing_narrative,
        "narrate_briefing",
        lambda _facts: _Narrative(references=[_Ref("email", "nonexistent-id")]),
    )

    output = tmp_path / "briefing_narrative_results.md"
    exit_code = runner._run_full(str(output))

    out = capsys.readouterr().out
    assert exit_code == env.EXIT_EVAL_FAIL
    assert "grounding error: ValueError" in out
    assert "INFRA ERROR" not in out
    assert output.exists()


def test_full_mode_recall_failure_is_eval_fail(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(env, "ensure_openai_api_key", lambda: None)

    import office_agent.llm_assist.briefing_narrative as briefing_narrative

    monkeypatch.setattr(
        runner,
        "load_cases",
        lambda: [
            {
                "id": "b1",
                "query": "q",
                "expected_reference_ids": ["email-001"],
                "must_reference_source_types": [],
            }
        ],
    )
    # Grounded (empty) narrative → recall against the expected id is 0.0.
    monkeypatch.setattr(
        briefing_narrative, "narrate_briefing", lambda _facts: _Narrative(references=[])
    )

    output = tmp_path / "briefing_narrative_results.md"
    exit_code = runner._run_full(str(output))

    out = capsys.readouterr().out
    assert exit_code == env.EXIT_EVAL_FAIL
    assert "0/1 case(s) passed." in out
    assert "INFRA ERROR" not in out
    assert "CONFIG ERROR" not in out
    assert output.exists()


def test_full_mode_recall_failure_reports_reference_diagnostics(monkeypatch, capsys, tmp_path):
    """A recall shortfall records sorted expected/actual/missing/unexpected ids and
    still classifies as an ordinary EVAL_FAIL."""

    monkeypatch.setattr(env, "ensure_openai_api_key", lambda: None)

    import office_agent.llm_assist.briefing_narrative as briefing_narrative

    monkeypatch.setattr(
        runner,
        "load_cases",
        lambda: [
            {
                "id": "b1",
                "query": "q",
                # Expect two ids; the model will produce only one of them.
                "expected_reference_ids": ["TICK-004", "email-001"],
                "must_reference_source_types": [],
            }
        ],
    )
    # Grounded narrative (email-001 is in the real collected facts) that covers only
    # one expected id → recall 0.5, so the diagnostics block is emitted.
    monkeypatch.setattr(
        briefing_narrative,
        "narrate_briefing",
        lambda _facts: _Narrative(references=[_Ref("email", "email-001")]),
    )

    output = tmp_path / "briefing_narrative_results.md"
    exit_code = runner._run_full(str(output))

    out = capsys.readouterr().out
    assert exit_code == env.EXIT_EVAL_FAIL
    assert "expected_references: ['TICK-004', 'email-001']" in out
    assert "actual_references: ['email-001']" in out
    assert "missing_references: ['TICK-004']" in out
    assert "unexpected_references: []" in out


# ---------------------------------------------------------------------------
# Dataset --validate-only behavior is unchanged
# ---------------------------------------------------------------------------


def test_real_dataset_validates(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert _run_main(monkeypatch, ["--validate-only"]) == 0
    out = capsys.readouterr().out
    assert "passed schema validation" in out
