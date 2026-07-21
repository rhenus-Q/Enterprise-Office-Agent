"""
Smoke tests for the Enterprise RAG interactive CLI (enterprise_rag/cli.py).

The engine (`answer_question`), the config mode readers, and `input` are all
mocked at the CLI's import seam, and the load_dotenv / tracing-privacy calls are
neutered, so these tests run keys-free and offline. They verify banner
selection and exit control only — not RAG behavior.
"""

import builtins
from types import SimpleNamespace

from enterprise_rag import cli


def _script_input(monkeypatch, responses):
    it = iter(responses)
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(it))


def _raising_input(monkeypatch, exc):
    """Make the next input() call raise `exc` (e.g. Ctrl+C / EOF at the prompt)."""

    def _raise(_prompt=""):
        raise exc

    monkeypatch.setattr(builtins, "input", _raise)


def _neuter_startup(monkeypatch):
    """Silence the .env load and tracing enforcement side effects."""

    monkeypatch.setattr(cli, "load_dotenv", lambda *a, **k: None)
    monkeypatch.setattr(cli, "enforce_tracing_privacy", lambda: None)


def _set_modes(monkeypatch, *, offline=False, privacy=False, web_search=True):
    monkeypatch.setattr(cli, "offline_mode", lambda: offline)
    monkeypatch.setattr(cli, "privacy_mode", lambda: privacy)
    monkeypatch.setattr(cli, "web_search_enabled", lambda: web_search)


def test_cli_exits_on_exit_word(monkeypatch, capsys):
    _neuter_startup(monkeypatch)
    _set_modes(monkeypatch)
    _script_input(monkeypatch, ["exit"])

    cli.main()
    out = capsys.readouterr().out

    assert "Agentic RAG Assistant for Enterprise Document Q&A" in out
    assert "Bye." in out


def test_cli_offline_banner_takes_precedence(monkeypatch, capsys):
    _neuter_startup(monkeypatch)
    _set_modes(monkeypatch, offline=True, privacy=True, web_search=False)
    _script_input(monkeypatch, ["exit"])

    cli.main()
    out = capsys.readouterr().out

    assert "OFFLINE_MODE is ENABLED" in out
    assert "PRIVACY_MODE is ENABLED" not in out


def test_cli_privacy_banner_when_not_offline(monkeypatch, capsys):
    _neuter_startup(monkeypatch)
    _set_modes(monkeypatch, offline=False, privacy=True, web_search=False)
    _script_input(monkeypatch, ["exit"])

    cli.main()
    out = capsys.readouterr().out

    assert "PRIVACY_MODE is ENABLED" in out
    assert "OFFLINE_MODE is ENABLED" not in out


def test_cli_web_search_disabled_banner(monkeypatch, capsys):
    _neuter_startup(monkeypatch)
    _set_modes(monkeypatch, offline=False, privacy=False, web_search=False)
    _script_input(monkeypatch, ["exit"])

    cli.main()
    out = capsys.readouterr().out

    assert "Web search is DISABLED (WEB_SEARCH_ENABLED=false)." in out


def test_cli_answers_question_and_formats(monkeypatch, capsys):
    _neuter_startup(monkeypatch)
    _set_modes(monkeypatch)
    _script_input(monkeypatch, ["what is the vpn policy?", "exit"])
    monkeypatch.setattr(
        cli,
        "answer_question",
        lambda q: SimpleNamespace(
            raw_state={"generation": "The VPN policy is ...", "documents": []}
        ),
    )

    cli.main()
    out = capsys.readouterr().out

    assert "The VPN policy is ..." in out


def test_cli_engine_exception_is_type_only_and_loop_continues(monkeypatch, capsys):
    # An unexpected engine error must not crash the CLI or leak the exception
    # message: only the exception *type* is surfaced, and the loop survives to
    # the next prompt (here, an explicit exit).
    _neuter_startup(monkeypatch)
    _set_modes(monkeypatch)
    _script_input(monkeypatch, ["trigger failure", "exit"])

    secret = "C:/secrets/api_key.env::sk_live_DO_NOT_ECHO"

    def boom(_question):
        raise RuntimeError(secret)

    monkeypatch.setattr(cli, "answer_question", boom)

    cli.main()  # must not raise
    out = capsys.readouterr().out

    assert "RuntimeError" in out  # the exception type is surfaced
    assert secret not in out  # the full message never printed
    assert "sk_live_DO_NOT_ECHO" not in out  # no secret fragment
    assert "api_key" not in out  # no path fragment
    assert "Traceback" not in out  # no traceback
    assert "Bye." in out  # the loop survived to the explicit exit


def test_cli_exits_cleanly_on_keyboard_interrupt(monkeypatch, capsys):
    # Ctrl+C at the prompt exits like a quit command, with no traceback.
    _neuter_startup(monkeypatch)
    _set_modes(monkeypatch)
    _raising_input(monkeypatch, KeyboardInterrupt())

    cli.main()  # must not raise
    out = capsys.readouterr().out

    assert "Bye." in out
    assert "Traceback" not in out


def test_cli_exits_cleanly_on_eof(monkeypatch, capsys):
    # EOF (piped/closed stdin) exits like a quit command, with no traceback.
    _neuter_startup(monkeypatch)
    _set_modes(monkeypatch)
    _raising_input(monkeypatch, EOFError())

    cli.main()  # must not raise
    out = capsys.readouterr().out

    assert "Bye." in out
    assert "Traceback" not in out
