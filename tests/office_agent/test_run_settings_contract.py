"""
Cross-language contract test for request-scoped Run Settings resolution.

Both this Python test and the frontend Vitest test
(`frontend/src/mocks/run-settings-contract.test.ts`) consume the SAME fixture,
`tests/contracts/run-settings-resolution.json`, so the Python resolver
(`office_agent.run_settings.resolve_run_settings`) and the frontend mock resolver
(`resolveMockRunSettings` in `frontend/src/mocks/fixtures.ts`) cannot silently
drift apart on the precedence rules.

The fixture lives at the neutral repository-level path `tests/contracts/`; this
test lives under `tests/office_agent/` (which owns `office_agent.run_settings`)
so it runs in the existing keys-free `mocked-tests` CI job without any CI change.

Division of labour:

- Both sides consume the same shared fixture and execute **every** contract case
  — no filtering.
- Python is authoritative: it runs each case against the real
  `resolve_run_settings`, which defines the semantics both sides must match.
- TypeScript injects each case's own server policy into `resolveMockRunSettings`,
  so the frontend mock reproduces the same server configurations rather than
  being limited to a single fixed server.

Fully local and deterministic: the resolver is a pure function, so no OpenAI,
Tavily, Chroma, enterprise_rag graph run, or LLM assist is involved.
"""

import json
from pathlib import Path

import pytest

from office_agent.run_settings import OfficeRunOptions, resolve_run_settings

CONTRACT_PATH = Path(__file__).parent.parent / "contracts" / "run-settings-resolution.json"


def _load_cases() -> list[dict]:
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    return data["cases"]


CASES = _load_cases()


def _values(values) -> dict:
    return {
        "privacy_mode": values.privacy_mode,
        "llm_assist": values.llm_assist,
        "web_search": values.web_search,
    }


def test_contract_fixture_is_non_empty_with_unique_names():
    names = [case["name"] for case in CASES]

    assert names, "the contract fixture must define at least one case"
    assert len(names) == len(set(names)), "case names must be unique"


@pytest.mark.parametrize("case", CASES, ids=[case["name"] for case in CASES])
def test_python_resolver_matches_the_contract(case):
    """The real resolver reproduces every case's expected `requested` /
    `effective` / `applicability` / `constraints` exactly."""

    options = OfficeRunOptions(
        privacy_mode=case["options"]["privacy_mode"],
        llm_assist=case["options"]["llm_assist"],
        web_search=case["options"]["web_search"],
    )

    settings = resolve_run_settings(
        case["intent"],
        options,
        server_privacy_mode=case["server"]["server_privacy_mode"],
        server_offline_mode=case["server"]["server_offline_mode"],
        server_llm_assist_available=case["server"]["server_llm_assist_available"],
        server_web_search_available=case["server"]["server_web_search_available"],
    )

    expected = case["expected"]

    assert _values(settings.requested) == expected["requested"]
    assert _values(settings.effective) == expected["effective"]
    assert {
        "llm_assist": settings.applicability.llm_assist,
        "web_search": settings.applicability.web_search,
    } == expected["applicability"]
    assert list(settings.constraints) == expected["constraints"]
