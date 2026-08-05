# ADR 021: Frontend observability workspace and thin FastAPI adapter

Status: Accepted

Date: 2026-07-20

Scope: **Repository-wide** — this decision adds the repository's first web surface
(`frontend/`), the first HTTP surface over the engines (`api/`), and additive,
backward-compatible changes to the `office_agent` contract that both consume (the
Knowledge Q&A observability carry-through and the request-scoped Run Settings
recorded in the Amendment below). It spans both packages
and the CI configuration, so the ADR lives at `docs/adr/` rather than under either
module's ADR directory (the third repository-level ADR, beside
[ADR 019](019-hierarchical-runtime-privacy-modes.md) and
[ADR 020](020-module-owned-cli-entry-points.md)).

## Context

The repository had two completed engines and **no web surface at all**. The Office
Agent's single entry point `office_agent.engine.answer_office_request()` and the
RAG engine behind its Knowledge Q&A adapter already produced real observability
data — run ids, node paths, per-node timings, counters, stop reasons, caveats, and
privacy-mode state — but none of it was visible outside the terminal CLIs
([ADR 020](020-module-owned-cli-entry-points.md)), which also recorded the future
API/frontend tier as direction only.

Two forces shaped the design:

- **The engines must stay authoritative.** Routing, intent detection, tool
  behavior, formatting, privacy/fallback semantics, date interpretation, and
  LLM-assist logic all live in the engines and are covered by their tests. A web
  tier that re-derived any of that would immediately drift from the source of
  truth it was meant to display.
- **The rich Knowledge Q&A observability was dropped at the `ToolResult`
  boundary.** `office_agent/tools/knowledge.py` already held the full
  `enterprise_rag` `AnswerResult`, but `ToolResult` (`tool`, `content`,
  `stop_reason`, `sources`, `run_id`) had nowhere to carry the node path, timings,
  counters, or fallback flags — so the API could not surface them without either
  duplicating engine logic or calling `answer_question()` directly and bypassing
  the Office Agent boundary.

## Decision

Build **one universal observability workspace** (React + TypeScript + Vite in
`frontend/`) over a **thin FastAPI adapter** (`api/`) that calls
`answer_office_request()` verbatim, and carry the missing Knowledge Q&A
observability across the `ToolResult` boundary with a single additive schema
change. No engine behavior changes.

### 1. One workspace, not seven apps, and not a chatbot

The frontend is a single three-pane workspace — a capability rail (`nav`), a
universal request composer plus per-intent results (`main`), and execution details
(`aside`) — that exercises all seven capabilities plus the `unknown` route. Each
capability is framed (icon, title, accent, monospace-preserved engine text) but the
composer and request path are shared, so the workspace demonstrates the
deterministic router rather than fronting seven separate tools or a plain chat box.
No Next.js / Streamlit / Chainlit / Gradio; no router, UI kit, or state library.

### 2. Thin FastAPI adapter — one engine call, no duplicated logic

`api/app.py` exposes a **factory** `create_app() -> FastAPI` (no module-level app,
so imports stay side-effect-free), which calls `load_dotenv()` then
`enforce_tracing_privacy()` — the same entry-point pattern as the CLIs
([ADR 020](020-module-owned-cli-entry-points.md)). It exposes exactly two routes:

- `GET /api/health` → the four existing flag readers, unmodified:
  `office_agent.llm_assist.config.privacy_mode/offline_mode/office_llm_enabled` and
  `enterprise_rag.graph.config.web_search_enabled()`. The last is reported as
  `web_search_effective` — the effective, mode-aware value (the reader already
  returns `False` whenever privacy restrictions are active), never a raw
  `WEB_SEARCH_ENABLED` echo.
- `POST /api/agent/run` → calls `answer_office_request(text, options)` **once**,
  maps `OfficeAgentResponse` fields 1:1, and adds four presentation/observability
  values: `duration_ms` (adapter-measured wall clock around the single call),
  `execution_mode` (an **adapter-derived** classification computed by a pure helper
  from the routed intent, the stop reason, and the assist decision that actually
  governed the run), `observability` (Knowledge Q&A only — see §3), and
  `run_settings` (the backend-resolved per-run settings — see the Amendment; `null`
  when the request omitted `options`). The request body accepts an optional
  `options` object (`privacy_mode` / `llm_assist` / `web_search`), and omitting it
  preserves the original behavior exactly. Engine exceptions become HTTP 500 with
  the exception **type name only**, matching the engines' banner convention that
  messages may carry paths or secrets.

The adapter contains no routing, intent, formatting, privacy, fallback, or date
logic; its only engine call is `answer_office_request()`, so the Knowledge Q&A
adapter boundary with `enterprise_rag` stays intact and nothing is duplicated. The
per-run settings it forwards are resolved **inside** the engine (after routing, by
the pure `office_agent.run_settings`); the adapter re-derives nothing and transports
`run_settings` verbatim (see the Amendment). The Vite dev server proxies `/api` to
the localhost adapter, so no CORS middleware is needed.

### 3. Additive `KnowledgeObservability` carry-through

To surface the dropped Knowledge Q&A metadata without duplicating logic, the data
is carried across the boundary as new **optional, default-`None`** fields:

- `office_agent/schemas.py` gains two dataclasses — `NodeTiming` (`node`,
  `duration_ms`) and `KnowledgeObservability` (mirroring `AnswerResult`: `run_id`,
  `node_path`, `node_timings_ms` as typed `NodeTiming` values, `total_duration_ms`,
  `retries`, `tracked_llm_calls`, `web_search_count`, `web_result_grading_count`,
  `web_search_enabled`, `web_fallback_policy`, `caveat`) — plus one optional
  `observability` field on **both** `ToolResult` and `OfficeAgentResponse`.
- `office_agent/tools/knowledge.py` populates it from the `AnswerResult` it already
  holds, re-typing each timing dict into a `NodeTiming` and reusing the engine's
  existing `STOP_REASON_NOTES` for the caveat — it computes nothing.
- `office_agent/engine.py` carries `observability` through; the `unknown` branch
  and every non-knowledge tool keep the `None` default, so their `ToolResult`
  values are byte-for-byte unchanged.

`AnswerResult` and every other `enterprise_rag` file are untouched (zero diff). The
three timing representations stay aligned 1:1 — `NodeTiming` (dataclass) ↔
`NodeTimingModel` (Pydantic) ↔ `NodeTiming` (TypeScript). This was the only
production change when the workspace first shipped; the request-scoped Run Settings
recorded in the Amendment below add a second, equally additive surface.

### 4. Honest-observability rule

Every value the UI shows traces to a named engine field. Adapter-measured
`duration_ms` is labeled adapter-measured; adapter-derived `execution_mode` is
labeled adapter-derived; `observability` is populated for Knowledge Q&A only and is
**never fabricated** for the deterministic capabilities — those explicitly say
"this capability does not expose an execution timeline" rather than showing a fake
one. Per-intent renderers **frame** the engine's `content` string (headings,
accents, the `sources` array, caveat emphasis) but never re-parse it to recompute
counts, dates, or lists, and never reword engine text; `content` is always rendered
as text (React default escaping, no `dangerouslySetInnerHTML`). No UI code computes
a business date from the browser clock — dates render verbatim from engine output.

### 5. Localhost-only, no-auth demo scope

The adapter binds localhost only. Authentication, a database, persistent history,
multi-tenant support, token streaming/SSE/WebSocket, and any deployment tooling
(Docker, hosting) are explicit non-goals — this is a local demonstration surface,
not a hosted product.

### 6. Keys-free CI coverage, no deployment

`.github/workflows/ci.yml` gains coverage without any keys or deploy step: the
`api` dependency group (`fastapi`/`uvicorn`/`httpx`) is installed in both existing
uv jobs (the `lint` job needs it so mypy can type-check `api/`), the `mocked-tests`
job gains a `uv run pytest tests/api/ -q` step (the adapter tested with
`fastapi.testclient` and a monkeypatched engine seam), and a new `frontend` job
runs `npm ci` / `npm run build` / `npm test` on Node 20. Every job stays keys-free.

## Consequences

- The repository has a localhost web surface that makes the engines' existing
  observability visible for the first time, while the terminal CLIs remain
  unchanged.
- The engines stay the single source of truth: the only engine call from the web
  tier is `answer_office_request()`, and every production change is additive — the
  `observability` carry-through and the request-scoped Run Settings surface (see the
  Amendment) — so `enterprise_rag/**` has zero diff and the tools stay byte-for-byte
  identical when no per-run options are sent.
- CI now guards the adapter and the frontend build/tests on every push, still with
  no API keys and no deployment steps. `npm ci` requires the committed
  `frontend/package-lock.json`, and `uv sync --locked --group api` requires
  `uv.lock` to carry the `api` group (both committed).
- Two durations are visible on knowledge runs — adapter `duration_ms` (whole engine
  call) vs. `total_duration_ms` (graph only) — and are labeled distinctly to avoid
  implying they measure the same thing.

## Trade-offs

- **A new HTTP + web surface to maintain.** Accepted: the adapter holds no business
  logic (pure pass-through plus two labeled presentation values), and the frontend
  never re-derives engine data, so drift risk is bounded to the hand-mirrored types
  — which `tests/api/` pins by asserting the exact JSON field names.
- **`execution_mode` is a classification, not telemetry.** The engines report no
  such field; it is computed in the adapter and must always be labeled
  adapter-derived. Reading `office_llm_enabled()` at response time is accurate
  because env state is process-consistent, but the field never claims a per-run LLM
  count.
- **Hand-mirrored types can desynchronize** between the Pydantic models and
  `types/api.ts`. Mitigated by both citing the same contract as the source of truth
  and by the adapter tests asserting field names.
- **The additive schema field touches a shared module.** `office_agent/schemas.py`
  is used by every tool and test, so the field is optional and default-`None`, and
  the full pre-existing mocked office suite is run unchanged to prove no regression.

## Alternatives considered

- **Call `answer_question()` directly from the API for Knowledge Q&A** — rejected:
  it would bypass the Office Agent boundary and duplicate the adapter's job. The
  additive `observability` carry-through keeps the single `answer_office_request()`
  entry point.
- **Seven per-capability apps or a plain chatbot** — rejected: the product is one
  deterministic router over seven capabilities, so one universal workspace
  demonstrates it honestly; separate apps hide the routing and a chatbot hides the
  observability.
- **Next.js / Streamlit / Chainlit / Gradio** — rejected: a minimal Vite + React +
  TypeScript app with no router/UI-kit/state library keeps the surface small,
  typed, and framework-light for a demo tier.
- **Reformat or enrich `content` in the adapter or renderers** — rejected: the
  engines own formatting; re-parsing `content` would silently duplicate formatting
  rules and could drift. Renderers frame, never re-derive.
- **Add auth / persistence / deployment now** — rejected: out of scope for a
  localhost demonstration surface; each would need its own decision.
- **File this ADR under a module directory** — rejected: it adds a repository-level
  web/HTTP tier, spans both packages, and changes CI, so it is repository-wide and
  belongs at the `docs/adr/` root beside ADR 019 and ADR 020.

## Amendment (2026-07-20) — request-scoped Run Settings

The workspace as first shipped exposed server policy read-only and offered no way to
vary a single run. This amendment adds **optional, request-scoped Run Settings**: the
composer can make one submitted run stricter, the backend resolves the request
against its own policy, and the response reports — honestly — what actually governed
the run. It **amends** (does not supersede) the decision above; the two endpoints,
the honest-observability rule, and the localhost-only scope are unchanged.

### Context

`GET /api/health` already reports server/runtime policy (`privacy_mode`,
`offline_mode`, `office_llm_enabled`, `web_search_effective`), but those are
read-only environment facts. There was no way for a demo user to say "run *this*
request with the LLM assist off" or "strict for this one" without editing the
server's environment and restarting — which would change global state for every
request, not one.

### Decision

Add a second, additive layer that is request-scoped and mutates nothing.

- **Two visually and semantically separate surfaces.** The top status chips
  (`StatusBanner`) stay read-only server policy — informational, no click handler,
  no toggle, labeled "Server policy … Read-only server policy configured by the API
  runtime." The interactive controls (`RunSettingsControls`) live beside the composer
  and are real form controls: **Privacy** (Standard / Strict, a radiogroup),
  **LLM Assist** (Off / On), **Web Search** (Off / On), each with an applicability
  hint.
- **Request shape (additive, backward-compatible).** `POST /api/agent/run` gains an
  optional `options` object on the body:

  ```json
  {
    "text": "<request>",
    "options": { "privacy_mode": "standard", "llm_assist": false, "web_search": false }
  }
  ```

  `AgentRunRequest.options` is `RunOptionsRequest | None` with `extra="forbid"` and
  conservative defaults (`privacy_mode="standard"`, both paths `false`). Omitting
  `options` reaches the engine as "no per-run options"
  (`answer_office_request(text, None)`), preserving the original behavior exactly;
  `run_settings` then comes back `null`.
- **Response shape.** `AgentRunResponse` gains `run_settings: RunSettingsModel | null`.
  `RunSettingsModel` separates four questions so observability cannot lie:
  - `requested` — what the caller submitted (`RunSettingsValuesModel`:
    `privacy_mode` / `llm_assist` / `web_search`).
  - `effective` — what actually governed the run (same shape).
  - `applicability` — whether `llm_assist` / `web_search` even apply to the routed
    capability (`RunSettingsApplicabilityModel`).
  - `constraints` — `list[str]` of stable typed reasons `requested` and `effective`
    differ: `server_offline_mode`, `server_privacy_mode`, `request_privacy_strict`,
    `server_llm_assist_disabled`, `server_web_search_disabled`,
    `llm_assist_not_applicable`, `web_search_not_applicable`.
- **Engine resolution (`office_agent.run_settings`).** `answer_office_request` routes
  first, then calls `resolve_run_settings(intent, options, server_*=…)` — a pure
  function over frozen dataclasses — and threads only the resolved *effective*
  decision into the affected tool: web search into the Knowledge Q&A adapter's
  existing `AnswerOptions(web_search_enabled=…)` seam, LLM assist into the Email
  Summary / Daily Briefing tools. Deterministic tools receive nothing. The adapter's
  `execution_mode` helper reads the resolved `effective.llm_assist` when settings are
  present (falling back to the server flag otherwise), so a run whose request
  switched the assist off is never mislabeled `llm_assisted`.

### Precedence (one level below ADR 019)

`OFFLINE_MODE` > `PRIVACY_MODE` > server feature availability > per-request options. A
server privacy or offline mode forces `effective.privacy_mode = strict`; otherwise a
request may request strict itself. Strict, and any disabled server feature, force the
corresponding external path off:

```text
effective.web_search = requested.web_search AND web_search-applies
                       AND server_web_search_available AND not strict
effective.llm_assist = requested.llm_assist AND llm_assist-applies
                       AND server_llm_assist_available AND not strict
```

A per-run request can only ever **restrict**: a requested `Off` stays `Off`, and no
request can enable a path the server prohibits. Applicability: LLM Assist applies to
Email Summary and Daily Briefing; Web Search applies to Knowledge Q&A; Privacy
applies to runs able to reach an external service. A setting that does not apply is
reported as `applicability=false` and shown "Not applicable" — never as though it had
been used.

### Request isolation (safety properties)

- `OfficeRunOptions` is passed **explicitly** through `answer_office_request()`; it is
  a frozen dataclass, so a run's options cannot drift mid-run.
- Settings are resolved **after** routing; routing is never influenced by them.
- `resolve_run_settings` reads **no** environment variable and touches **no** module
  global — server policy arrives as function arguments, and resolution mutates
  nothing.
- No temporary `os.environ` change and no mutable module state exist on this path, so
  two concurrent requests with opposite settings cannot interfere.

### UI honesty

- **While running**, Execution Details shows only the *requested* snapshot and says
  it is "Waiting for the backend to report which settings actually govern this run";
  it never guesses `effective`.
- **After completion**, `effective` is rendered strictly from the backend's
  `run_settings` and is authoritative; the frontend never re-derives it and never
  infers it from the status chips.
- If a completed response carries `run_settings: null`, the panel states the backend
  did not report effective settings.
- If the browser **stops** waiting, the panel says the effective settings are
  unavailable rather than pretending a final answer arrived.
- Retry reuses the original run's requested snapshot; Reset clears the workspace but
  preserves the selected Run Settings as a user preference.

### Why no `/api/settings` endpoint

Run Settings are a property of one request, not server state. They ride on the run
request body and come back on the run response, so `POST /api/agent/run` stays the
only run endpoint and `GET /api/health` stays the only policy read. A settings
endpoint would imply mutable, shared server configuration — exactly the global state
this design avoids.

### Why global environment mutation was rejected

"Apply these settings for this run" must not change what any other request sees.
Mutating `os.environ` (or a module global) around a call would leak into concurrent
requests, break the isolation property, and reintroduce the shared mutable state the
runtime privacy modes were careful to keep read-only. Passing frozen options through
the call and resolving them purely keeps every run independent.

### Why server policy and per-run settings are visually separated

Collapsing "what the server allows" and "what this run asked for" into one control
would invite two lies: that a badge can be toggled, and that a requested value was
honored. Keeping read-only policy chips distinct from interactive request controls —
and reporting `requested` vs `effective` separately — makes the precedence visible
instead of hidden.

### Consequences

- One run can be made stricter for a demo without touching the environment or
  restarting; every other request is unaffected.
- The response is honest about divergence: `requested`, `effective`, `applicability`,
  and typed `constraints` are all reported, and the UI shows `effective` only from
  the backend.
- The change is additive and backward-compatible: omitting `options` reproduces the
  original request/response exactly (`run_settings: null`). `enterprise_rag/**`
  remains zero-diff; the only `enterprise_rag` touch point is the pre-existing
  `AnswerOptions(web_search_enabled=…)` seam.

### Alternatives considered

- **A `/api/settings` endpoint or server-side stored preferences** — rejected:
  settings are per-request, not shared state; see above.
- **Mutating `os.environ` / a module global for the duration of a call** — rejected:
  breaks concurrency isolation and reintroduces shared mutable state; see above.
- **One merged control surface for policy + per-run settings** — rejected: it would
  imply the read-only badges are interactive and that a requested value was
  necessarily honored; the split keeps precedence honest.
- **Predict `effective` in the frontend** — rejected: only the backend knows server
  policy at run time, so the UI shows `effective` solely from `run_settings` and says
  so when it is absent.
