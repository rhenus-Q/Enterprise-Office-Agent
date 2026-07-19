"""
Unit tests for the Office Agent interactive CLI (office_agent/cli.py).

`answer_office_request` is mocked at the CLI's import seam
(`office_agent.cli.answer_office_request`) and `input` is scripted via
monkeypatch, so these tests never route a real request, touch enterprise_rag,
or hit any external service. They verify presentation and loop control only.
"""

import builtins
import runpy
import sys
from pathlib import Path

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


def test_cli_strips_the_request_and_exit_is_case_insensitive(monkeypatch, capsys):
    """Input is `.strip()`ed before dispatch and exit words match case-insensitively.

    The tests above only feed already-trimmed text and lowercase exit words, so
    neither `input().strip()` nor the `request.lower()` exit comparison is
    pinned by them.
    """

    _script_input(monkeypatch, ["   show pending approvals   ", "EXIT"])
    seen = []
    monkeypatch.setattr(
        cli,
        "answer_office_request",
        lambda req: (
            seen.append(req)
            or OfficeAgentResponse(
                intent=INTENT_WORKFLOW_APPROVAL,
                content="Pending approvals: 2",
                tool="approvals",
            )
        ),
    )

    cli.main()

    assert seen == ["show pending approvals"]  # surrounding whitespace dropped
    assert "Bye." in capsys.readouterr().out  # uppercase EXIT still ends the loop


def test_root_main_delegates_to_office_cli():
    """Root main.py is the repository-level Office Agent entry point.

    `main.main` is `office_agent.cli.main` itself (via
    `from office_agent.cli import main`), so `uv run python main.py` runs the
    Office Agent CLI. Importing `main` must not pull in `enterprise_rag`.
    """

    import main as root_main

    assert root_main.main is cli.main


def test_main_py_script_execution_invokes_the_office_cli(monkeypatch):
    """`uv run python main.py` must actually start the Office Agent CLI.

    The delegation test above pins the *binding*; this pins the
    `if __name__ == "__main__"` guard that turns that binding into a run.
    `main.py` resolves `main` at import time via
    `from office_agent.cli import main`, so patching the attribute on
    `office_agent.cli` before executing the file is sufficient.
    """

    calls = []
    monkeypatch.setattr(cli, "main", lambda: calls.append("called"))
    # Execute a fresh copy under __main__ semantics, keeping sys.modules clean so
    # this test neither depends on nor disturbs the plain `import main` above.
    monkeypatch.delitem(sys.modules, "main", raising=False)

    repo_root = Path(__file__).resolve().parents[2]
    runpy.run_path(str(repo_root / "main.py"), run_name="__main__")

    assert calls == ["called"]
