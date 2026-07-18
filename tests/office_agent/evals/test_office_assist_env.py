"""
Unit tests for evals/office_agent/llm_assist/_env.py — the shared env-loading and
error-classification helper for the two Office-assist eval runners.

Fully keys-free and offline: no OpenAI client is constructed and no network call
is made. `.env` loading is exercised only through a fake `load_dotenv`.
"""

import openai
import pytest

import evals.office_agent.llm_assist._env as env


def test_ensure_openai_api_key_missing_raises_config_error(monkeypatch):
    # Do not load the real repository .env; simulate an environment with no key.
    monkeypatch.setattr(env, "load_repo_env", lambda: None)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(env.ConfigError) as excinfo:
        env.ensure_openai_api_key()

    message = str(excinfo.value)
    assert "OPENAI_API_KEY is not set" in message
    assert "No eval cases were executed" in message


def test_ensure_openai_api_key_blank_raises_config_error(monkeypatch):
    monkeypatch.setattr(env, "load_repo_env", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "   ")

    with pytest.raises(env.ConfigError):
        env.ensure_openai_api_key()


def test_ensure_openai_api_key_present_passes(monkeypatch):
    monkeypatch.setattr(env, "load_repo_env", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")

    # Must not raise.
    env.ensure_openai_api_key()


@pytest.mark.parametrize("mode", ["OFFLINE_MODE", "PRIVACY_MODE"])
def test_runtime_privacy_mode_raises_config_error_even_with_a_key(monkeypatch, mode):
    # Either mode disables the assists these runners evaluate, so a full run must
    # fail closed before any client is constructed -- even with a valid key set.
    monkeypatch.setattr(env, "load_repo_env", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.delenv("OFFLINE_MODE", raising=False)
    monkeypatch.delenv("PRIVACY_MODE", raising=False)
    monkeypatch.setenv(mode, "true")

    with pytest.raises(env.ConfigError) as excinfo:
        env.ensure_openai_api_key()

    message = str(excinfo.value)
    assert mode in message
    assert "No eval cases were executed" in message


def test_non_truthy_mode_values_do_not_block_the_run(monkeypatch):
    monkeypatch.setattr(env, "load_repo_env", lambda: None)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-not-real")
    monkeypatch.setenv("OFFLINE_MODE", "false")
    monkeypatch.setenv("PRIVACY_MODE", "bogus")

    # Must not raise: only an explicit truthy value activates a mode.
    env.ensure_openai_api_key()


def test_load_repo_env_uses_override_false(monkeypatch):
    """`.env` must never override an already-exported process variable."""

    captured = {}

    import dotenv

    def _fake_load_dotenv(*args, **kwargs):
        captured["override"] = kwargs.get("override")
        return True

    monkeypatch.setattr(dotenv, "load_dotenv", _fake_load_dotenv)
    env.load_repo_env()
    assert captured["override"] is False


def test_is_infra_error_true_for_openai_error():
    class _SimulatedInfra(openai.OpenAIError):
        pass

    assert env.is_infra_error(_SimulatedInfra("boom")) is True


def test_is_infra_error_false_for_value_error():
    assert env.is_infra_error(ValueError("grounding failure")) is False
    assert env.is_infra_error(KeyError("oops")) is False


def test_infra_reason_maps_known_subclasses():
    # Subclass with a no-op __init__ so we do not depend on the SDK exception
    # constructors' (response/body) signatures.
    class _Auth(openai.AuthenticationError):
        def __init__(self):
            pass

    class _Timeout(openai.APITimeoutError):
        def __init__(self):
            pass

    assert env.infra_reason(_Auth()) == "authentication failure"
    assert env.infra_reason(_Timeout()) == "request timeout"
    # Unknown OpenAIError subclass falls back to the generic label.
    assert env.infra_reason(openai.OpenAIError("x")) == "OpenAI client error"
