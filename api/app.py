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
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.schemas import (
    AgentRunRequest,
    AgentRunResponse,
    ErrorResponse,
    ExecutionMode,
    HealthResponse,
    KnowledgeObservabilityModel,
    NodeTimingModel,
    RunOptionsRequest,
    RunSettingsApplicabilityModel,
    RunSettingsModel,
    RunSettingsValuesModel,
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
from office_agent.run_settings import OfficeRunOptions, ResolvedRunSettings
from office_agent.schemas import (
    INTENT_CALENDAR_LOOKUP,
    INTENT_DAILY_BRIEFING,
    INTENT_EMAIL_SUMMARY,
    INTENT_KNOWLEDGE_QA,
    INTENT_MEETING_AGENT,
    INTENT_TICKET_ASSISTANT,
    INTENT_UNKNOWN,
    INTENT_WORKFLOW_APPROVAL,
    KnowledgeObservability,
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


def derive_execution_mode(
    intent: str, stop_reason: str, settings: ResolvedRunSettings | None = None
) -> ExecutionMode:
    """Classify how a completed run executed (spec §8.2 matrix, exhaustive).

    Purely presentational and adapter-derived: it reads the already-produced
    `intent` / `stop_reason` plus the assist decision that actually governed the
    run. It makes no routing decision, invokes nothing, and must never be
    treated as engine telemetry.

    When the request carried per-run settings, the assist branch uses the
    **effective** decision the engine resolved rather than the bare server flag
    — otherwise a run whose request switched the assist off would still be
    reported as `"llm_assisted"`, which would be a lie. With no per-run settings
    the original server-flag behavior is unchanged.

    Degradation *within* a mode stays the job of `stop_reason` — a knowledge run
    with `retrieval_error` is still `"rag_llm"`. Only the offline short-circuit
    earns its own mode, because there no graph and no LLM call ever happened.
    """

    if intent == INTENT_UNKNOWN:
        return "none"

    if intent in _ALWAYS_DETERMINISTIC_INTENTS:
        return "deterministic"

    if intent in _LLM_ASSIST_INTENTS:
        assist_ran = settings.effective.llm_assist if settings is not None else office_llm_enabled()
        if not assist_ran:
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


def _observability_model(
    observability: KnowledgeObservability | None,
) -> KnowledgeObservabilityModel | None:
    """Transport the office-agent observability structure onto the wire.

    A field-for-field copy: `None` stays `None` (every capability except
    Knowledge Q&A), and nothing is defaulted, rounded, or invented.
    """

    if observability is None:
        return None

    return KnowledgeObservabilityModel(
        run_id=observability.run_id,
        node_path=list(observability.node_path),
        node_timings_ms=[
            NodeTimingModel(node=timing.node, duration_ms=timing.duration_ms)
            for timing in observability.node_timings_ms
        ],
        total_duration_ms=observability.total_duration_ms,
        retries=observability.retries,
        tracked_llm_calls=observability.tracked_llm_calls,
        web_search_count=observability.web_search_count,
        web_result_grading_count=observability.web_result_grading_count,
        web_search_enabled=observability.web_search_enabled,
        web_fallback_policy=observability.web_fallback_policy,
        caveat=observability.caveat,
    )


def _run_options(options: RunOptionsRequest | None) -> OfficeRunOptions | None:
    """Convert the validated request body into the engine's frozen options type.

    `None` stays `None` so an omitted `options` field reaches the engine as "no
    per-run options" — preserving the original behavior exactly rather than
    silently substituting defaults, which would force both external paths off.
    """

    if options is None:
        return None

    return OfficeRunOptions(
        privacy_mode=options.privacy_mode,
        llm_assist=options.llm_assist,
        web_search=options.web_search,
    )


def _run_settings_model(settings: ResolvedRunSettings | None) -> RunSettingsModel | None:
    """Transport the backend-resolved settings onto the wire, verbatim.

    The adapter deliberately re-derives nothing here: `effective` is whatever
    the engine resolved, so the frontend can display it as authoritative.
    """

    if settings is None:
        return None

    return RunSettingsModel(
        requested=RunSettingsValuesModel(
            privacy_mode=settings.requested.privacy_mode,  # type: ignore[arg-type]
            llm_assist=settings.requested.llm_assist,
            web_search=settings.requested.web_search,
        ),
        effective=RunSettingsValuesModel(
            privacy_mode=settings.effective.privacy_mode,  # type: ignore[arg-type]
            llm_assist=settings.effective.llm_assist,
            web_search=settings.effective.web_search,
        ),
        applicability=RunSettingsApplicabilityModel(
            llm_assist=settings.applicability.llm_assist,
            web_search=settings.applicability.web_search,
        ),
        constraints=list(settings.constraints),
    )


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

    @app.exception_handler(RequestValidationError)
    async def request_validation_error(
        _request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        """Return only the validation exception type, never rejected input."""

        return JSONResponse(status_code=422, content={"error": "RequestValidationError"})

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
            result = answer_office_request(request.text, _run_options(request.options))
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
            execution_mode=derive_execution_mode(
                result.intent, result.stop_reason, result.run_settings
            ),
            # Real engine metadata when the Knowledge Q&A adapter produced it;
            # null for every other capability rather than fabricated.
            observability=_observability_model(result.observability),
            run_settings=_run_settings_model(result.run_settings),
        )

    return app
