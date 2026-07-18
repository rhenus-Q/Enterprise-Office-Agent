"""
runtime_privacy.py

Early-initialization side effects for the runtime privacy modes, kept OUT of
`enterprise_rag/graph/config.py` (whose contract is "no side effects": pure env
reads only). This module's *import* is still side-effect-free — it only reads or
mutates the environment when `enforce_tracing_privacy()` is explicitly called.

The single responsibility here is neutralizing LangSmith tracing under a runtime
privacy mode. Tracing is otherwise independent of WEB_SEARCH_ENABLED and would
export prompts, questions, retrieved document content, and model outputs to an
external service; PRIVACY_MODE / OFFLINE_MODE must turn that off. Both the legacy
(`LANGCHAIN_TRACING_V2`) and current (`LANGSMITH_TRACING`) variable names are set,
so the neutralization holds across langchain versions.
"""

import os

from enterprise_rag.graph.config import privacy_restrictions_active

# LangChain reads the legacy name; recent LangSmith releases read the new one.
# Setting both guarantees tracing is off regardless of the installed version.
_TRACING_ENV_VARS = ("LANGCHAIN_TRACING_V2", "LANGSMITH_TRACING")


def enforce_tracing_privacy() -> None:
    """Neutralize LangSmith tracing when a runtime privacy mode is active.

    When `PRIVACY_MODE` or `OFFLINE_MODE` is set, force both tracing env vars to
    `"false"` before any chain can run, so no trace is exported. Strict no-op when
    neither mode is active (existing tracing configuration is left untouched).
    Idempotent: safe to call at every entry point and multiple times per process.
    """

    if not privacy_restrictions_active():
        return

    for name in _TRACING_ENV_VARS:
        os.environ[name] = "false"
