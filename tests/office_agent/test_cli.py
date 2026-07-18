"""
Unit tests for the Office Agent interactive CLI (office_agent/cli.py).

`answer_office_request` is mocked at the CLI's import seam
(`office_agent.cli.answer_office_request`) and `input` is scripted via
monkeypatch, so these tests never route a real request, touch enterprise_rag,
or hit any external service. They verify presentation and loop control only.
"""

import builtins

from office_agent import cli
from office_agent.schemas import INTENT_UNKNOWN, INTENT_WORKFLOW_APPROVAL, OfficeAgentResponse


def _script_input(monkeypatch, responses):
    """Feed `responses` to successive input() calls."""

    it = iter(responses)
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(it))


def test_cli_renders_intent_tool_and_content(monkeypatch, capsys):
    _script_input(monkeypatch, ["show pending approvals", "exit"])
    monkeypatch.setattr(
        cli,
        "answer_office_request",
        lambda _req: OfficeAgentResponse(
            intent=INTENT_WORKFLOW_APPROVAL,
            content="Pending approvals: 2",
            tool="approvals",
        ),
    )

    cli.main()
    out = capsys.readouterr().out

    assert "Intent : workflow_approval" in out
    assert "Tool   : approvals" in out
    assert "Pending approvals: 2" in out
    assert "Bye." in out


def test_cli_renders_observability_fields_when_set(monkeypatch, capsys):
    _script_input(monkeypatch, ["what is the vpn policy?", "quit"])
    monkeypatch.setattr(
        cli,
        "answer_office_request",
        lambda _req: OfficeAgentResponse(
            intent="knowledge_qa",
            content="The VPN policy is ...",
            tool="knowledge",
            stop_reason="web_search_disabled",
            sources=["- Local corpus: VPN Access Policy"],
            run_id="run-123",
        ),
    )

    cli.main()
    out = capsys.readouterr().out

    assert "Stop reason: web_search_disabled" in out
    assert "Sources:" in out
    assert "- Local corpus: VPN Access Policy" in out
    assert "Run id : run-123" in out


def test_cli_shows_dash_for_unknown_intent_without_tool(monkeypatch, capsys):
    _script_input(monkeypatch, ["order lunch", "q"])
    monkeypatch.setattr(
        cli,
        "answer_office_request",
        lambda _req: OfficeAgentResponse(
            intent=INTENT_UNKNOWN,
            content="Unsupported request.",
            tool=None,
        ),
    )

    cli.main()
    out = capsys.readouterr().out

    assert "Intent : unknown" in out
    assert "Tool   : -" in out
    assert "Stop reason:" not in out
    assert "Run id :" not in out


def test_cli_skips_empty_input_and_exits(monkeypatch, capsys):
    _script_input(monkeypatch, ["", "exit"])
    calls = []
    monkeypatch.setattr(
        cli,
        "answer_office_request",
        lambda req: (
            calls.append(req) or OfficeAgentResponse(intent=INTENT_UNKNOWN, content="", tool=None)
        ),
    )

    cli.main()

    assert calls == []  # empty input never dispatched


def test_root_main_delegates_to_office_cli():
    """Root main.py is the repository-level Office Agent entry point.

    `main.main` is `office_agent.cli.main` itself (via
    `from office_agent.cli import main`), so `uv run python main.py` runs the
    Office Agent CLI. Importing `main` must not pull in `enterprise_rag`.
    """

    import main as root_main

    assert root_main.main is cli.main
