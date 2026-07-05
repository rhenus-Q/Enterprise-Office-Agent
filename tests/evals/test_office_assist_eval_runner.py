"""
Keys-free tests for evals/office_agent/llm_assist/run_email_digest_eval.py — the
standalone email-digest eval runner's environment loading and CONFIG/INFRA/EVAL_FAIL
classification.

Fully offline: OpenAI is never called and no API key is required. The digest chain
and env preconditions are patched at their seams; the deterministic dataset
validation and grounding checks run for real.
"""

import openai

import evals.office_agent.llm_assist._env as env
import evals.office_agent.llm_assist.run_email_digest_eval as runner


class _SimulatedInfra(openai.OpenAIError):
    """A stand-in for any OpenAI SDK / transport failure."""


class _Item:
    def __init__(self, email_id, deadline=None):
        self.email_id = email_id
        self.deadline = deadline


class _Digest:
    def __init__(self, action_items=None, priority_order=None):
        self.action_items = action_items or []
        self.priority_order = priority_order or []


def _run_main(monkeypatch, argv):
    monkeypatch.setattr("sys.argv", ["run_email_digest_eval.py", *argv])
    return runner.main()


# ---------------------------------------------------------------------------
# --validate-only stays offline and keys-free
# ---------------------------------------------------------------------------


def test_validate_only_succeeds_without_key(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # If full mode or any .env load were reached, these would blow up.
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
    # Never load the real repository .env; simulate a keyless environment.
    monkeypatch.setattr(env, "load_repo_env", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    # If office_agent's LLM stack were imported / called, this would surface.
    import office_agent.llm_assist.email_digest as email_digest

    def _boom(*args, **kwargs):
        raise AssertionError("no case may run when the key is missing")

    monkeypatch.setattr(email_digest, "digest_emails", _boom)

    output = tmp_path / "results.md"
    exit_code = runner._run_full(str(output))

    out = capsys.readouterr().out
    assert exit_code != 0
    assert "CONFIG ERROR" in out
    assert "OPENAI_API_KEY is not set" in out
    # No misleading model-quality summary and no report file written.
    assert "case(s) passed" not in out
    assert not output.exists()


# ---------------------------------------------------------------------------
# Full mode: an infrastructure failure is INFRA_ERROR, not an ordinary FAIL
# ---------------------------------------------------------------------------


def test_full_mode_infra_error_is_not_eval_fail(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(env, "ensure_openai_api_key", lambda: None)

    import office_agent.llm_assist.email_digest as email_digest
    import office_agent.tools.email as email

    monkeypatch.setattr(email, "filter_for_query", lambda q: ("label", [{"id": "email-001"}]))

    def _raise_infra(_matched):
        raise _SimulatedInfra("simulated provider outage")

    monkeypatch.setattr(email_digest, "digest_emails", _raise_infra)

    output = tmp_path / "results.md"
    exit_code = runner._run_full(str(output))

    out = capsys.readouterr().out
    assert exit_code != 0
    assert "INFRA ERROR" in out
    # Never reported as an ordinary model-quality result.
    assert "case(s) passed" not in out
    assert "FAIL (eval assertion" not in out
    assert not output.exists()


# ---------------------------------------------------------------------------
# Full mode: a successful call that fails recall is an ordinary EVAL_FAIL
# ---------------------------------------------------------------------------


def test_full_mode_recall_failure_is_eval_fail(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(env, "ensure_openai_api_key", lambda: None)

    import office_agent.llm_assist.email_digest as email_digest
    import office_agent.tools.email as email

    monkeypatch.setattr(
        runner,
        "load_cases",
        lambda: [
            {
                "id": "t1",
                "query": "q",
                "expected_action_item_email_ids": ["email-001"],
                "must_not_invent_deadline_for": [],
            }
        ],
    )
    monkeypatch.setattr(email, "filter_for_query", lambda q: ("label", [{"id": "email-001"}]))
    # Grounded but empty digest → recall against the expected id is 0.0.
    monkeypatch.setattr(email_digest, "digest_emails", lambda _m: _Digest())

    output = tmp_path / "results.md"
    exit_code = runner._run_full(str(output))

    out = capsys.readouterr().out
    assert exit_code == env.EXIT_EVAL_FAIL
    # The model-quality pass rate IS reported for a genuine eval failure.
    assert "0/1 case(s) passed." in out
    assert "INFRA ERROR" not in out
    assert "CONFIG ERROR" not in out
    assert output.exists()


def test_full_mode_grounding_failure_is_eval_fail(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(env, "ensure_openai_api_key", lambda: None)

    import office_agent.llm_assist.email_digest as email_digest
    import office_agent.tools.email as email

    monkeypatch.setattr(
        runner,
        "load_cases",
        lambda: [
            {
                "id": "t1",
                "query": "q",
                "expected_action_item_email_ids": [],
                "must_not_invent_deadline_for": [],
            }
        ],
    )
    monkeypatch.setattr(email, "filter_for_query", lambda q: ("label", [{"id": "email-001"}]))
    # References an id not in the filtered set → real validate_digest raises ValueError.
    monkeypatch.setattr(
        email_digest,
        "digest_emails",
        lambda _m: _Digest(action_items=[_Item("email-999")]),
    )

    output = tmp_path / "results.md"
    exit_code = runner._run_full(str(output))

    out = capsys.readouterr().out
    assert exit_code == env.EXIT_EVAL_FAIL
    assert "FAIL (eval assertion: ValueError)" in out
    assert "INFRA ERROR" not in out
    assert output.exists()


# ---------------------------------------------------------------------------
# Dataset --validate-only behavior is unchanged
# ---------------------------------------------------------------------------


def test_real_dataset_validates(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert _run_main(monkeypatch, ["--validate-only"]) == 0
    out = capsys.readouterr().out
    assert "passed schema validation" in out
