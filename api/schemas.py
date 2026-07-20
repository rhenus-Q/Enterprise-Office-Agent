"""
api.schemas — Pydantic v2 request/response models for the thin adapter.

These models are the wire contract mirrored by the frontend's
`frontend/src/types/api.ts`; field names must stay identical in both files.

Typing policy (deliberate, and the reason not every field is a `Literal`):

- Fields the **adapter** owns — `status`, `execution_mode` — are `Literal`
  unions, because the adapter produces every possible value itself.
- Fields transported **1:1 from the engine** — `intent`, `tool`, `stop_reason` —
  are plain `str`. FastAPI validates outgoing response models, so a `Literal`
  here would make the adapter reject (HTTP 500) a perfectly valid engine
  response the day a new intent or stop reason is added upstream. Refusing
  engine output is exactly the reinterpretation the adapter must not do; the
  frontend keeps the narrow unions for display.
"""

from typing import Literal

from pydantic import BaseModel, Field

# Adapter-derived execution classification (spec §8.2 matrix). Not engine
# telemetry — no engine reports such a field.
ExecutionMode = Literal[
    "none",
    "deterministic",
    "llm_assisted",
    "llm_assist_fallback",
    "rag_llm",
    "rag_blocked_offline",
]


class AgentRunRequest(BaseModel):
    """Body of `POST /api/agent/run`.

    The bounds are exact: 4000 characters is accepted, 4001 (and empty) get
    FastAPI's standard 422.
    """

    text: str = Field(min_length=1, max_length=4000)


class NodeTimingModel(BaseModel):
    """One graph step's wall-clock timing (Phase 4 payload)."""

    node: str
    duration_ms: float


class KnowledgeObservabilityModel(BaseModel):
    """Knowledge Q&A observability carried through from `AnswerResult`.

    Defined now so the wire contract is complete and typed, but always `null`
    in Phase 2: the `office_agent` carry-through lands in Phase 4. Never
    fabricated.

    `tracked_llm_calls` is the budgeted operational counter, not total LLM
    usage — the UI must label it "tracked".
    """

    run_id: str | None = None
    node_path: list[str] = Field(default_factory=list)
    node_timings_ms: list[NodeTimingModel] = Field(default_factory=list)
    total_duration_ms: float = 0.0
    retries: int = 0
    tracked_llm_calls: int = 0
    web_search_count: int = 0
    web_result_grading_count: int = 0
    web_search_enabled: bool = False
    web_fallback_policy: str = ""
    caveat: str = ""


class AgentRunResponse(BaseModel):
    """Response of `POST /api/agent/run`.

    `intent`, `tool`, `content`, `stop_reason`, `sources`, and `run_id` map 1:1
    from `OfficeAgentResponse` — unaltered, unparsed, unreformatted.

    Only three fields are added by the adapter:
    - `duration_ms` — **adapter-measured** (`time.perf_counter()` around the
      single engine call), never claimed to be engine telemetry.
    - `execution_mode` — **adapter-derived** presentation classification.
    - `observability` — `null` until Phase 4.
    """

    intent: str
    tool: str | None = None
    content: str
    stop_reason: str = ""
    sources: list[str] = Field(default_factory=list)
    run_id: str | None = None
    duration_ms: float
    execution_mode: ExecutionMode
    observability: KnowledgeObservabilityModel | None = None


class HealthResponse(BaseModel):
    """Response of `GET /api/health`.

    Every flag comes from an existing pure reader; none is re-parsed here.
    `web_search_effective` is the *effective* runtime state from
    `enterprise_rag.graph.config.web_search_enabled()` (which already applies
    the privacy floor) — never an echo of the raw `WEB_SEARCH_ENABLED` value.
    """

    status: Literal["ok"] = "ok"
    privacy_mode: bool
    offline_mode: bool
    office_llm_enabled: bool
    web_search_effective: bool


class ErrorResponse(BaseModel):
    """Engine-failure body: the exception **type name** only.

    Matches the repo's console-banner convention — exception messages may carry
    paths, keys, or user data, so they are never returned.
    """

    error: str
