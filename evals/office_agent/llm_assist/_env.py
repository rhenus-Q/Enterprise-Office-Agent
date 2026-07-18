"""
evals/office_agent/llm_assist/_env.py — shared environment loading + error
classification for the two standalone Office-assist eval runners (email digest +
briefing narrative).

A deliberately small private helper so the two runners stay consistent without a
broad eval framework. It provides exactly what both need and nothing more:

- `ensure_openai_api_key()` — full-mode-only precondition. Loads the repository
  `.env` using the existing python-dotenv convention (see `tests/conftest.py`,
  `main.py`) *without* overriding an already-exported process variable (process
  env wins), then requires a non-blank `OPENAI_API_KEY`. Raises `ConfigError`
  otherwise. Never prints the key.
- `is_infra_error()` / `infra_reason()` — classify an infrastructure/provider
  failure (auth, connection, timeout, rate limit, service error) using the
  narrowest reliable base class the installed OpenAI SDK exposes (`OpenAIError`),
  so such failures are never reported as model-quality (`EVAL_FAIL`) failures.

Import is side-effect-free and keys-free: nothing here loads `.env`, constructs a
client, or imports `openai` at import time. `.env` is loaded only when
`ensure_openai_api_key()` runs (full mode); `openai` is imported lazily only when
an exception is being classified. This keeps every runner's `--validate-only`
path import-light and offline.
"""

from pathlib import Path

# evals/office_agent/llm_assist/_env.py -> repository root is three parents up.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_ENV_PATH = _PROJECT_ROOT / ".env"

# Values that enable a runtime privacy mode. Matches the parsing in
# enterprise_rag/graph/config.py and office_agent/llm_assist/config.py; duplicated
# rather than imported to keep this helper dependency-free.
_TRUTHY_VALUES = {"true", "1", "yes", "on"}

# Error categories surfaced by the runners. CONFIG_ERROR and INFRA_ERROR both
# mean "the run is invalid" (no model-quality pass rate); EVAL_FAIL is an ordinary
# behavioral failure that still counts toward the pass rate.
CONFIG_ERROR = "CONFIG_ERROR"
INFRA_ERROR = "INFRA_ERROR"

# Process exit codes. Non-zero is all that is strictly required; distinct codes
# make "invalid run" (config/infra) visibly different from "eval assertions failed".
EXIT_OK = 0
EXIT_EVAL_FAIL = 1
EXIT_INVALID_RUN = 2


class ConfigError(Exception):
    """Required runtime configuration is missing or invalid, detected before any
    eval case runs and any client is constructed (e.g. a missing API key)."""


def load_repo_env() -> None:
    """Load the repository `.env` for a full-mode run, without overriding a value
    already present in the process environment (process env wins).

    Uses the repository's existing python-dotenv convention. Safe no-op when
    `.env` is absent. Never called by `--validate-only`.
    """

    from dotenv import load_dotenv

    # override=False → an already-exported OPENAI_API_KEY takes precedence.
    load_dotenv(dotenv_path=_ENV_PATH, override=False)


def ensure_openai_api_key() -> None:
    """Full-mode precondition: load `.env` (process env wins), refuse to run under
    a runtime privacy mode, then require a non-blank `OPENAI_API_KEY`.

    Raises `ConfigError` (with a clear, key-free message) when `OFFLINE_MODE` or
    `PRIVACY_MODE` is active, or when the key is missing or blank, so the caller
    can fail fast — before executing any eval case, constructing any client, or
    making any model call. Never prints the key.

    Both modes refuse because these runners evaluate the two optional Office LLM
    assists, which either mode disables: a full run would measure a capability
    that is switched off. `.env` is loaded first so a mode declared there is
    honored. This refusal is also why the runners need no tracing call — no model
    call can occur under a mode, so no trace can be exported.
    """

    import os

    load_repo_env()

    for mode in ("OFFLINE_MODE", "PRIVACY_MODE"):
        if os.getenv(mode, "false").strip().lower() in _TRUTHY_VALUES:
            raise ConfigError(
                f"{mode} is enabled, which disables the optional Office LLM assists.\n"
                f"Unset {mode} to run a real-model eval, or use --validate-only.\n"
                "No eval cases were executed."
            )

    key = os.getenv("OPENAI_API_KEY")
    if key is None or not key.strip():
        raise ConfigError(
            "OPENAI_API_KEY is not set.\n"
            "Set it in the process environment or the repository .env file.\n"
            "No eval cases were executed."
        )


def is_infra_error(exc: BaseException) -> bool:
    """True when `exc` is an OpenAI/transport infrastructure failure (auth,
    connection, timeout, rate limit, provider service error) rather than a
    model-quality / behavioral failure.

    Classification uses `openai.OpenAIError` — the base class of every OpenAI SDK
    exception and the narrowest reliable seam the installed dependency exposes.
    LangChain lets these propagate unwrapped from `ChatOpenAI.invoke`. `openai`
    is imported lazily so importing this module stays keys-free and light.
    """

    try:
        from openai import OpenAIError
    except Exception:
        return False
    return isinstance(exc, OpenAIError)


def infra_reason(exc: BaseException) -> str:
    """A concise, leak-safe reason for an infrastructure failure, derived only
    from the exception's *type* — never its message, request payload, or provider
    response body. Returns a generic label when the specific subclass is unknown.
    """

    try:
        from openai import (
            APIConnectionError,
            APIError,
            APITimeoutError,
            AuthenticationError,
            RateLimitError,
        )
    except Exception:
        return "OpenAI client error"

    if isinstance(exc, AuthenticationError):
        return "authentication failure"
    if isinstance(exc, APITimeoutError):
        return "request timeout"
    if isinstance(exc, RateLimitError):
        return "rate limited"
    if isinstance(exc, APIConnectionError):
        return "API connection failure"
    if isinstance(exc, APIError):
        return "provider/API error"
    return "OpenAI client error"


def print_config_error(exc: "ConfigError") -> None:
    """Print a standardized `CONFIG ERROR:` block. Message is key-free by
    construction (see `ensure_openai_api_key`)."""

    print(f"CONFIG ERROR: {exc}")


def print_infra_error(exc: BaseException) -> None:
    """Print a standardized `INFRA ERROR:` block showing only safe diagnostics:
    the exception type name and a sanitized category — never keys, payloads, or
    provider response bodies."""

    print("INFRA ERROR: infrastructure/provider failure — this run is invalid.")
    print(f"  category: {infra_reason(exc)}")
    print(f"  exception: {type(exc).__name__}")
    print("No model-quality pass rate was computed; any existing report was left untouched.")


def print_unexpected_error(exc: BaseException) -> None:
    """Print a standardized `UNEXPECTED ERROR:` block for a local programming
    error so it is surfaced clearly rather than mislabeled as a model-quality
    failure. Shows only the exception type name."""

    print("UNEXPECTED ERROR: local error before/around a case — this run is invalid.")
    print(f"  exception: {type(exc).__name__}")
    print("No model-quality pass rate was computed; any existing report was left untouched.")
