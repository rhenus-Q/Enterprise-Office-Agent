"""Regression tests for pytest's keys-free environment boundary."""

import os

import pytest

from office_agent.llm_assist import config as llm_config
from tests.conftest import isolate_ordinary_test_environment, real_model_skip_reason

# Captured during test-module import, before fixtures or test bodies can alter
# the process. This guards the collection-time boundary explicitly.
_OFFICE_LLM_ENABLED_DURING_IMPORT = llm_config.office_llm_enabled()


def test_ordinary_bootstrap_forces_authoritative_office_reader_off(monkeypatch):
    monkeypatch.setenv("OFFICE_LLM_ENABLED", "true")
    isolate_ordinary_test_environment(os.environ)

    assert os.environ["OFFICE_LLM_ENABLED"] == "false"
    assert llm_config.office_llm_enabled() is False


def test_office_config_is_not_contaminated_during_test_module_import():
    assert _OFFICE_LLM_ENABLED_DURING_IMPORT is False


def test_ordinary_pytest_disables_later_dotenv_loading():
    assert os.environ["PYTHON_DOTENV_DISABLED"] == "1"


@pytest.mark.parametrize("opt_in", [None, "", "0", "false", "no", "off"])
def test_credentials_alone_do_not_authorize_real_model_tests(opt_in):
    env = {"OPENAI_API_KEY": "sk-test-not-a-real-key"}
    if opt_in is not None:
        env["RUN_REAL_MODEL_TESTS"] = opt_in

    reason = real_model_skip_reason(environ=env)

    assert reason is not None
    assert "RUN_REAL_MODEL_TESTS=1" in reason


def test_real_model_opt_in_without_credentials_has_clear_skip_reason():
    reason = real_model_skip_reason(environ={"RUN_REAL_MODEL_TESTS": "1"})

    assert reason == "missing required credential(s): OPENAI_API_KEY"


def test_real_model_opt_in_and_credentials_authorize_collection():
    reason = real_model_skip_reason(
        environ={
            "RUN_REAL_MODEL_TESTS": "1",
            "OPENAI_API_KEY": "sk-test-not-a-real-key",
        }
    )

    assert reason is None


def test_offline_mode_still_blocks_an_authorized_real_model_test():
    reason = real_model_skip_reason(
        environ={
            "RUN_REAL_MODEL_TESTS": "1",
            "OPENAI_API_KEY": "sk-test-not-a-real-key",
            "OFFLINE_MODE": "true",
        }
    )

    assert reason is not None
    assert "OFFLINE_MODE" in reason
