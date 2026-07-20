"""
api.app — the thin FastAPI adapter's application factory.

`create_app()` mirrors the CLI entry-point pattern (`office_agent/cli.py`,
`enterprise_rag/cli.py`): `.env` loading and tracing-privacy enforcement happen
inside the factory, so importing this module stays side-effect-free and no
module-level `app` object exists.

Run it with:

    uv run uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8000

Bind configuration belongs to that command, not to this module. There is no
CORS middleware (the Vite dev server proxies `/api`) and no authentication —
this is a localhost-only demo surface.

The single engine boundary is `answer_office_request()`. This module never
calls `enterprise_rag.graph.engine.answer_question()` and contains no routing,
formatting, date, privacy, fallback, or tool logic.

The names imported below (`answer_office_request`, `office_llm_enabled`,
`web_search_enabled`, ...) are the seams the mocked tests in `tests/api/`
monkeypatch, so they are imported into this module's namespace on purpose.
"""

import time

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from api.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    ErrorResponse,
    ExecutionMode,
    HealthResponse,
)
from enterprise_rag.graph.config import web_search_enabled
from enterprise_rag.graph.consts import STOP_REASON_OFFLINE_MODE
from enterprise_rag.runtime_privacy import enforce_tracing_privacy
from office_agent.engine import answer_office_request
from office_agent.llm_assist.config import (
    STOP_REASON_LLM_ASSIST_ERROR,
    office_llm_enabled,
    offline_mode,
    privacy_mode,
)
from office_agent.schemas import (
    INTENT_CALENDAR_LOOKUP,
    INTENT_DAILY_BRIEFING,
    INTENT_EMAIL_SUMMARY,
    INTENT_KNOWLEDGE_QA,
    INTENT_MEETING_AGENT,
    INTENT_TICKET_ASSISTANT,
    INTENT_UNKNOWN,
    INTENT_WORKFLOW_APPROVAL,
)

# Capabilities that are always deterministic: local mock tools with no LLM path.
_ALWAYS_DETERMINISTIC_INTENTS = frozenset(
    {
        INTENT_CALENDAR_LOOKUP,
        INTENT_TICKET_ASSISTANT,
        INTENT_MEETING_AGENT,
        INTENT_WORKFLOW_APPROVAL,
    }
)

# Capabilities that carry an optional, default-off LLM assist.
_LLM_ASSIST_INTENTS = frozenset({INTENT_EMAIL_SUMMARY, INTENT_DAILY_BRIEFING})


def derive_execution_mode(intent: str, stop_reason: str) -> ExecutionMode:
    """Classify how a completed run executed (spec §8.2 matrix, exhaustive).

    Purely presentational and adapter-derived: it reads the already-produced
    `intent` / `stop_reason` plus the existing `office_llm_enabled()` reader.
    It makes no routing decision, invokes nothing, and must never be treated as
    engine telemetry.

    Degradation *within* a mode stays the job of `stop_reason` — a knowledge run
    with `retrieval_error` is still `"rag_llm"`. Only the offline short-circuit
    earns its own mode, because there no graph and no LLM call ever happened.
    """

    if intent == INTENT_UNKNOWN:
        return "none"

    if intent in _ALWAYS_DETERMINISTIC_INTENTS:
        return "deterministic"

    if intent in _LLM_ASSIST_INTENTS:
        if not office_llm_enabled():
            return "deterministic"
        if stop_reason == STOP_REASON_LLM_ASSIST_ERROR:
            return "llm_assist_fallback"
        return "llm_assisted"

    if intent == INTENT_KNOWLEDGE_QA:
        if stop_reason == STOP_REASON_OFFLINE_MODE:
            return "rag_blocked_offline"
        return "rag_llm"

    # Unreachable for the eight routed intents; keeps the return type total
    # without inventing a classification for an intent this adapter cannot know.
    return "none"


def create_app() -> FastAPI:
    """Build the adapter application.

    Mirrors the CLI entry points: `load_dotenv()` first, then
    `enforce_tracing_privacy()`, so a runtime privacy mode neutralizes tracing
    before any request can reach an engine.
    """

    load_dotenv()
    enforce_tracing_privacy()

    app = FastAPI(
        title="Enterprise Office Agent API",
        description=(
            "Thin adapter over office_agent.engine.answer_office_request(). "
            "Transports engine output; implements no business logic."
        ),
    )

    @app.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        """Report the effective runtime flags from the existing readers."""

        return HealthResponse(
            status="ok",
            privacy_mode=privacy_mode(),
            offline_mode=offline_mode(),
            office_llm_enabled=office_llm_enabled(),
            # Already the effective, mode-aware value — no privacy logic here.
            web_search_effective=web_search_enabled(),
        )

    @app.post(
        "/api/agent/run",
        response_model=AgentRunResponse,
        responses={500: {"model": ErrorResponse}},
    )
    def agent_run(request: AgentRunRequest) -> AgentRunResponse | JSONResponse:
        """Run one Office Agent request and transport the result verbatim."""

        started = time.perf_counter()
        try:
            result = answer_office_request(request.text)
        except Exception as exc:
            # Deliberately broad: this is the adapter's single engine boundary,
            # and no engine failure may escape as an unhandled 500 with a
            # traceback. Only the exception *type* is returned — messages can
            # carry paths, keys, or user data, so the repo convention is to
            # surface the type alone (mirroring the console banners).
            return JSONResponse(status_code=500, content={"error": type(exc).__name__})
        duration_ms = (time.perf_counter() - started) * 1000.0

        return AgentRunResponse(
            intent=result.intent,
            tool=result.tool,
            content=result.content,
            stop_reason=result.stop_reason,
            sources=list(result.sources),
            run_id=result.run_id,
            duration_ms=duration_ms,
            execution_mode=derive_execution_mode(result.intent, result.stop_reason),
            # Phase 4 carries real observability through office_agent; until
            # then this stays null rather than fabricated.
            observability=None,
        )

    return app
