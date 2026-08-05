# Office Agent v1.7.0 — Release Notes

## Summary

Office Agent v1.7.0 adds the repository's presentation tier and hardens the
complete Enterprise Office Agent system while preserving the existing
seven-capability engine contract. The release adds a React 18 + TypeScript +
Vite observability workspace, a thin FastAPI adapter, request-scoped Run
Settings, and Knowledge Q&A observability carry-through. It also expands
keys-free API and frontend validation, error boundaries, privacy-policy tests,
responsive behavior, and release documentation.

The Python engine remains authoritative. `office_agent.engine.answer_office_request()`
still routes to the same seven intents; v1.7.0 does **not** introduce an eighth
Office Agent capability. The web tier is a localhost reference/demo surface,
not a production deployment or a replacement for the Python engine and CLIs.

## Version map

| Release | Phase | Capabilities or release focus |
|---|---|---|
| **v1** | Phases 1–5 | Knowledge Q&A, Email Summary, Calendar Lookup, Task / Ticket Assistant, Daily Briefing |
| **v1.5** | Phase 6 | Meeting Agent / Meeting Prep |
| **v1.6** | Phase 7 | Workflow / Approval Agent |
| **v1.7.0** | Presentation and hardening | Frontend workspace, thin API adapter, request-scoped settings, observability, reliability, testing, and open-source release documentation; **no new Office Agent capability** |

The v1.6 note remains an intentionally preserved historical snapshot. See the
[v1.6 release notes](office-agent-v1.6.md) for that release point and
[Upgrade notes from v1.6](#upgrade-notes-from-v16) below for the current delta.

## Included capabilities

| # | Capability | Intent | Current backing implementation |
|---|---|---|---|
| 1 | Knowledge Q&A | `knowledge_qa` | [`office_agent/tools/knowledge.py`](../../office_agent/tools/knowledge.py), a thin adapter over `enterprise_rag.graph.engine.answer_question()` |
| 2 | Email Summary | `email_summary` | Local `mock_data/emails.json`; optional, default-off Email Digest LLM assist |
| 3 | Calendar Lookup | `calendar_lookup` | Local `mock_data/calendar_events.json` |
| 4 | Task / Ticket Assistant | `ticket_assistant` | Local `mock_data/tickets.json` and `mock_data/tasks.json` |
| 5 | Daily Briefing | `daily_briefing` | Deterministic aggregation of local email, calendar, and ticket/task data; its optional, default-off narrative fact set also includes local approvals |
| 6 | Meeting Agent / Meeting Prep | `meeting_agent` | Deterministic composition of local calendar, email, and ticket/task data |
| 7 | Workflow / Approval Agent | `workflow_approval` | Local `mock_data/approvals.json` and `mock_data/audit_log.json`; actions are simulated |

`unknown` is a safe routing outcome, not an eighth capability. The intent
constants remain defined in [`office_agent/schemas.py`](../../office_agent/schemas.py),
and the deterministic keyword router remains in
[`office_agent/router.py`](../../office_agent/router.py).

Most Office Agent behavior is a deterministic local demonstration over static,
fictional AcmeCorp data. Knowledge Q&A is the exception: it adapts the real
LangGraph-based `enterprise_rag` engine. Email Summary and Daily Briefing can
also use their bounded, single-pass LLM assists when server defaults enable
them or a request asks for them within allowed server policy; those assists are
presentation/synthesis paths, not new intents, and they fall back to
deterministic output on failure. The
FastAPI layer adds no business capability and duplicates no routing, tool, or
RAG implementation.

## What is new in v1.7.0

### Frontend observability workspace

[`frontend/`](../../frontend/) now contains a React 18, TypeScript, and Vite
workspace with one universal request composer and a three-pane layout:

- a semantic capability navigation rail;
- the request, Run Settings, state, and result workspace; and
- an execution-details panel.

The workspace covers all seven capabilities plus `unknown` handling. Results
receive intent-specific labels, accents, icons, and prose/monospace framing,
while the engine's `content` is rendered verbatim and escaped by React. The UI
surfaces source provenance, stop reasons, engine caveats, adapter duration,
adapter-derived execution mode, and—only when supplied by Knowledge Q&A—the
graph execution timeline and counters.

One typed `AgentClient` interface supports two explicit modes:

- `http` (default), which uses `GET /api/health` and `POST /api/agent/run`;
- `mock`, selected with `VITE_API_MODE=mock`, which uses typed fixtures and
  identifies itself as a mock environment.

The HTTP client distinguishes user cancellation, client-side timeout, an
unreachable adapter, validation failures, and type-only adapter errors. “Stop”
ends the browser's wait; it does not claim to interrupt synchronous work already
accepted by the server. Replacement requests abort the earlier browser request,
and late responses are prevented from overwriting newer state.

The UI has explicit empty, loading, success, degraded, unsupported, stopped,
error, and retry behavior. Semantic landmarks, labeled controls, live regions,
keyboard-operable disclosures and mobile navigation, visible focus handling,
and reduced-motion support make those states accessible without claiming a
formal conformance certification. Playwright verifies wide desktop
(1440×900), medium (1000×900), and narrow/mobile (390×844) layouts, including
stacking, sidebar collapse, reachable controls, and horizontal-overflow guards.

### Thin FastAPI adapter

[`api/app.py`](../../api/app.py) exposes the `create_app() -> FastAPI` factory
and two application endpoints:

- `GET /api/health`
- `POST /api/agent/run`

The request and response models live in
[`api/schemas.py`](../../api/schemas.py). `AgentRunRequest` accepts `text`
(1–4000 characters) and an optional `RunOptionsRequest`; `AgentRunResponse`
transports the engine response plus adapter and observability fields.

For a run, the adapter:

1. validates the wire request with Pydantic;
2. calls `office_agent.engine.answer_office_request(request.text, options)`
   once;
3. measures adapter wall-clock `duration_ms`;
4. derives the presentation-only `execution_mode`; and
5. maps the `OfficeAgentResponse`, optional `KnowledgeObservability`, and
   optional `ResolvedRunSettings` onto the response models.

It does not implement intent routing, tools, RAG, date interpretation,
formatting, or fallback policy. It does not call
`enterprise_rag.graph.engine.answer_question()` directly; the web path reaches
Knowledge Q&A only through `answer_office_request()` and the existing knowledge
adapter. `create_app()` loads `.env` and then calls
`enforce_tracing_privacy()`, keeping import-time app construction and external
client creation out of the module surface.

### Run Settings

[`office_agent/run_settings.py`](../../office_agent/run_settings.py) adds
request-scoped, frozen `OfficeRunOptions` and pure
`resolve_run_settings(...)` resolution. A run may request:

- `privacy_mode`: `standard` or `strict`;
- `llm_assist`: on or off; and
- `web_search`: on or off.

Resolution happens after deterministic routing. The server is authoritative:
`OFFLINE_MODE` takes precedence over `PRIVACY_MODE`, which takes precedence over
server feature availability and then the request. A client request may restrict
a run but cannot enable a path the server prohibits. LLM Assist applies only to
Email Summary and Daily Briefing; Web Search applies only to Knowledge Q&A.
Non-applicable settings are reported explicitly.

The response separates `requested`, `effective`, `applicability`, and typed
`constraints`. The frontend displays backend-reported `effective` values and
does not derive them from controls or health badges. Resolution reads no
environment variable and mutates no global state; current server policy is
passed into the pure resolver as arguments, keeping concurrent requests
isolated.

Request-scoped `strict` disables the optional external paths governed by these
settings—Tavily web search and the two Office LLM assists. It is not equivalent
to `OFFLINE_MODE`: the OpenAI-backed Knowledge Q&A core path remains available
unless server policy blocks it, and request-scoped strictness does not rewrite
the server's LangSmith tracing configuration. Use the server-level privacy
modes for those process-wide restrictions.

When `options` is omitted, `answer_office_request()` uses the earlier server
defaults, returns `run_settings=None`, and preserves the prior behavior. An
explicit, even partial, `options` object is different: its conservative schema
defaults leave both optional paths off unless requested.

### Knowledge Q&A observability

The knowledge adapter now carries the existing `enterprise_rag` `AnswerResult`
metadata through `ToolResult`, `OfficeAgentResponse`, Pydantic models, and the
frontend. The optional `KnowledgeObservability` structure contains:

- run ID;
- executed node path;
- per-node timings;
- total graph duration;
- retry count;
- tracked LLM-call count (an operational counter, not total usage);
- web-search and web-result-grading counts;
- effective web-search flag and fallback policy; and
- the existing stop-reason caveat.

The response also carries `stop_reason` and deterministic `sources` alongside
that structure. Detailed graph observability applies to Knowledge Q&A only;
the six deterministic Office tools do not receive fabricated timelines.

The underlying RAG engine can optionally write a limited local trace JSON via
`AnswerOptions.trace_path`. It excludes full prompts, responses, document
content, and raw graph state, but retains a best-effort-redacted question
preview and an unkeyed input hash, so it remains a potentially sensitive local
artifact; see the [trace handling guidance](../../enterprise_rag/README.md#run-traces-optional-local-debugging-artifacts).
The trace is not exposed as a payload by the v1.7.0 HTTP response.

### Reliability and security hardening

This release strengthens explicit boundaries without treating the demo as a
production security boundary:

- Request-validation failures return a fixed 422 body,
  `{"error":"RequestValidationError"}`, without echoing rejected input.
- Unexpected engine failures at the adapter boundary return a 500 body with the
  exception type name only; exception messages are not returned.
- The server privacy hierarchy is tested through the HTTP boundary, including
  the rule that a request cannot re-enable blocked web search.
- `create_app()` enforces tracing privacy for both supported tracing variables
  whenever server privacy restrictions are active.
- A checked-in OpenAPI wire-contract projection guards the two public route
  schemas and their reachable models.
- The Office Agent CLI handles prompt interruption/end-of-file cleanly and
  contains unexpected request failures by printing only the exception type.
- RAG dependency failures retain machine-readable stop reasons and caveats.
  Transient `tool_error` caveats are cleared only after a final answer passes
  both quality gates; whole-source failures remain visible. Optional Office LLM
  failures preserve the deterministic result and add an honest caveat.
- Ordinary pytest startup forces `OFFICE_LLM_ENABLED=false` and disables local
  `.env` loading before test collection. Real-model tests require both the
  explicit `RUN_REAL_MODEL_TESTS=1` opt-in and their named credentials.
- Frontend cancellation and timeouts use distinct error types and abort stale
  browser requests without representing client cancellation as server-side
  engine termination.

These controls reduce accidental leakage and ambiguous failure handling; they
do not add authentication, authorization, tenant isolation, hardened content
sanitization, or a production security boundary.

### Testing and CI

[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml) defines three
parallel, keys-free jobs:

1. **`mocked-tests`** — mocked Enterprise RAG node/graph/eval-helper suites,
   the deterministic/mocked Office Agent suite (excluding
   `tests/office_agent/integration/`), [`tests/api/`](../../tests/api/),
   `tests/test_environment_isolation.py`, and the deterministic tests in
   `tests/enterprise_rag/chains/test_generation.py` selected with
   `-m "not real_model"`.
2. **`lint`** — `ruff check`, `ruff format --check`, and scoped `mypy`, including
   `office_agent/` and `api/`.
3. **`frontend`** — Node 20, `npm ci`, the TypeScript/Vite build, Vitest with
   React Testing Library, and Playwright/Chromium responsive checks in typed
   mock mode.

The API tests cover health flags, response mapping, validation limits, privacy
precedence, execution-mode classification, type-only failures, app-factory
tracing enforcement, and the OpenAPI wire contract. Frontend tests cover both
client modes, Run Settings snapshots, verbatim rendering, all seven result
frames, unknown intent handling, state transitions, retry/stop behavior,
timeouts, and responsive real-browser layout.

Tests marked `real_model` under `tests/enterprise_rag/chains/`, the
`tests/office_agent/integration/` suite, provider-backed ingestion, and full
eval runs are excluded from normal CI. This release note intentionally describes
the current validation layers without claiming a new numeric test-count baseline.

## Architecture notes

```text
frontend/
  -> thin FastAPI adapter (api/)
     -> office_agent.engine.answer_office_request()
        -> deterministic router
           -> deterministic local tools
           -> Knowledge Q&A adapter -> enterprise_rag answer_question()
```

- Office Agent routing remains deterministic keyword matching; no LLM router
  is introduced. The two documented Office LLM assists remain optional,
  default-off synthesis paths after deterministic fact selection.
- `api/` never calls the RAG engine entry point directly. It reaches Knowledge
  Q&A through `answer_office_request()` and contains no duplicated business
  logic.
- Request options and observability fields are additive. Omitting options keeps
  the earlier engine behavior.
- Imports remain side-effect-conscious: the FastAPI app is created by a factory,
  engine clients remain lazy, and mock-data loaders are cached and lazy.
- Simulated ticket/task and approval actions do not mutate canonical mock data.
  Test-only persistence seams write only to an explicit caller-provided path.

## Local run instructions

Requires Python 3.11 or newer and `uv`. From the repository root, install the
Python, development, and API dependencies:

```powershell
uv sync --group dev --group api
```

Start the localhost FastAPI adapter:

```powershell
uv run uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8000
```

In another terminal, install and start the frontend:

```bash
cd frontend
npm install          # or `npm ci` against the committed package-lock.json
npm run dev
```

Run the frontend over typed fixtures without the adapter:

```bash
cd frontend
VITE_API_MODE=mock npm run dev
```

Windows PowerShell equivalent:

```powershell
cd frontend
$env:VITE_API_MODE = "mock"
npm run dev
```

Knowledge Q&A additionally needs provider configuration and a local Chroma
index. After configuring `.env` as described in the
[Enterprise RAG guide](../../enterprise_rag/README.md):

```powershell
uv run python -m enterprise_rag.ingestion
```

Safe, keys-free validation commands include:

```powershell
uv run pytest tests/enterprise_rag/nodes/ tests/enterprise_rag/graph/ tests/enterprise_rag/evals/ tests/office_agent/ --ignore=tests/office_agent/integration -v
uv run pytest tests/api/ -v
uv run pytest tests/test_environment_isolation.py -v
uv run pytest tests/enterprise_rag/chains/test_generation.py -m "not real_model" -v
uv run pytest -v
```

Ordinary `uv run pytest -v` startup disables local `.env` loading before
collection and forces `OFFICE_LLM_ENABLED=false`. Tests marked `real_model` are
skipped unless `RUN_REAL_MODEL_TESTS=1` and every required credential named by
the marker is explicitly provided; when that opt-in is present, `OFFLINE_MODE`
still forces those tests to skip. This keeps the normal path keys-free by
default—the explicitly opted-in provider path is separate.

From `frontend/`:

```bash
npm run build
npm test
npm run test:responsive
```

Do not set `RUN_REAL_MODEL_TESTS=1` for the keys-free validation path.

## Compatibility

- The seven intent names remain unchanged: `knowledge_qa`, `email_summary`,
  `calendar_lookup`, `ticket_assistant`, `daily_briefing`, `meeting_agent`, and
  `workflow_approval`.
- `office_agent.engine.answer_office_request()` remains the engine entry point.
  Its optional second argument accepts request-scoped `OfficeRunOptions`.
- Omitting options preserves the earlier server-default behavior and reports no
  fabricated requested/effective settings.
- `observability` and `run_settings` are additive, optional response data.
- Existing deterministic tool output remains authoritative; the presentation
  tier frames it rather than rewriting it.
- The Python CLI, local demo, and programmatic engine remain supported. The
  frontend and API do not replace them.

## Open-source scope

The public release includes the two Python engine modules, fictional AcmeCorp
corpus and office mock data, terminal CLIs and demo script, thin FastAPI adapter,
React observability workspace, architecture and engineering documentation,
mocked test suites, gated provider tests/evals, and the three-job CI workflow.

Explicit non-goals remain:

- no production deployment infrastructure or hosted-service configuration;
- no authentication or authorization layer;
- no real Gmail, Outlook, Calendar, Jira, Slack, or approval-system connector;
- no conversation memory or persistent interaction history;
- no autonomous mutation of external systems;
- no provider-backed test, ingestion, or eval execution in CI; and
- no claim that the repository is production-ready.

## Known limitations

- Intent classification is deterministic substring/keyword matching, not
  semantic routing. Each request routes to one intent.
- Email, calendar, ticket/task, meeting-prep, and approval behavior uses static,
  fictional local data. Date words are anchored to that data, not the system
  clock.
- The system is single-turn and has no conversation memory.
- Knowledge Q&A requires a locally built Chroma index and OpenAI-backed
  embeddings/chat access; Tavily is additionally required when web search is
  enabled. `OFFLINE_MODE` therefore blocks Knowledge Q&A before the graph runs.
- Request-scoped strict mode does not make the OpenAI RAG core offline and does
  not alter process-wide tracing configuration; server-level policy must govern
  those boundaries.
- Browser “Stop” and the frontend timeout stop waiting on the client. They do
  not terminate synchronous engine work already accepted by FastAPI.
- The API and frontend are localhost reference/demo presentation layers with no
  auth, persistence, streaming, database, deployment tooling, or real enterprise
  connectors.
- The RAG engine still uses print-based console logging, sequential grading,
  and layered prompt-level injection defenses rather than a complete production
  security boundary.

## Upgrade notes from v1.6

v1.6 remains the historical Phase 7 release that completed the seven-capability
inventory. Moving to the current v1.7.0 tree adds:

- the React + TypeScript + Vite frontend and thin FastAPI adapter;
- the two optional, default-off Office LLM assists added after v1.6;
- request-scoped Run Settings with backend-authoritative resolution;
- Knowledge Q&A observability carry-through to the web workspace;
- API validation, exception, privacy, and OpenAPI contract coverage;
- Vitest/React Testing Library and Playwright responsive coverage; and
- a third CI job for the frontend, while the Python mocked and lint jobs expand
  to cover the adapter.

No migration is required for existing Python callers that continue to call
`answer_office_request(user_input)` with one argument. Their engine routing and
tool behavior remain unchanged; the new options and response metadata are
additive.

## Detailed usage

- [Repository README](../../README.md) — project overview, quickstart, privacy
  modes, tests, and full documentation map.
- [Frontend README](../../frontend/README.md) — web stack, client modes, Run
  Settings, observability principles, and responsive verification.
- [Office Agent README](../../office_agent/README.md) — all capabilities,
  routing precedence, programmatic API, CLI, demo, and optional LLM assists.
- [Enterprise RAG README](../../enterprise_rag/README.md) — Knowledge Q&A setup,
  Chroma ingestion, provider configuration, graph API, and limitations.
- [Engineering onboarding](../engineering/onboarding.md) — repository layout,
  module boundaries, setup, and development workflow.
- [Testing strategy](../engineering/testing-strategy.md) — mocked, frontend,
  real-model, and eval validation layers.
- [Release checklist](../engineering/release-checklist.md) — review and release
  validation steps.
- [Employee quick start](../employee-guide/office-agent-quickstart.md) —
  end-user capability guide and simulated-action caveats.
- [ADR 021](../adr/021-frontend-observability-workspace.md) — presentation-tier,
  Knowledge Observability, and Run Settings design decisions.
