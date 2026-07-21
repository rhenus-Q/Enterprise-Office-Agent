# Enterprise Office Agent — Observability Workspace (frontend)

A single, universal **three-pane web workspace** for the Enterprise Office Agent.
It exercises all seven capabilities plus the `unknown` route through one composer,
and makes the engines' **existing** observability — run ids, node paths, per-node
timings, counters, stop reasons, caveats, and privacy-mode state — visible outside
the terminal. It invents no new signals and duplicates no engine logic.

See [ADR 021](../docs/adr/021-frontend-observability-workspace.md) for the design
decision, and the repository [README](../README.md) for the whole system.

## Stack

- **React 18 + TypeScript + Vite** — no router, no UI kit, no state library.
- **Vitest + React Testing Library + jsdom** for tests.
- **lucide-react** for icons.
- Plain CSS (light/dark friendly). All business logic stays in the Python engines.

The app talks to the thin FastAPI adapter (`../api/`) through exactly two
endpoints — `GET /api/health` and `POST /api/agent/run` — and never calls the
engines any other way.

## Layout

```
frontend/
  index.html, package.json, vite.config.ts, tsconfig.json
  src/
    types/api.ts            # single source of truth for the API contract (mirrors the Pydantic models)
    api/client.ts           # AgentClient interface + createHttpClient + createMockClient
    mocks/fixtures.ts       # typed fixtures: one per capability + degraded / unsupported / error / knowledge-observability
    hooks/                  # useAgentRun (run state machine), useHealth
    components/
      AppShell.tsx          # three-pane responsive grid (nav / main / aside landmarks)
      CapabilitySidebar.tsx, RequestComposer.tsx, RunSettingsControls.tsx
      StatusBanner.tsx      # read-only server-policy badges from /api/health (privacy/offline/assist/web-search)
      RunSettingsControls.tsx # interactive per-run settings (Privacy / LLM Assist / Web Search)
      RunSettingsSummary.tsx  # requested vs. backend-reported effective settings + constraints
      ExecutionPanel.tsx    # common fields + sources; KnowledgeTimeline for Knowledge Q&A only
      KnowledgeTimeline.tsx # node path + per-node timing bars + counters + caveat
      results/ResultCard.tsx# per-intent framed transcript (verbatim engine content)
      states/               # Empty / Loading / Error / Degraded / Unsupported / Stopped
    styles/app.css
    **/*.test.tsx           # Vitest + React Testing Library
```

## Prerequisites

- **Node 20 LTS** (the version CI uses) and npm.
- For live (`http`) mode: the FastAPI adapter running locally (see below). The
  deterministic six capabilities and the `unknown` route need no API keys; only a
  real Knowledge Q&A run reaches the RAG engine (`OPENAI_API_KEY` + a built Chroma
  index).

## Install and scripts

```bash
cd frontend
npm install          # or `npm ci` against the committed package-lock.json (what CI runs)

npm run dev          # Vite dev server (proxies /api → http://127.0.0.1:8000)
npm run build        # tsc --noEmit type-check, then vite build
npm run preview      # preview a production build
npm test             # Vitest run (single pass)
npm run test:watch   # Vitest watch mode
```

## Client modes: `mock` vs `http`

One `AgentClient` interface has two implementations, so no component knows which is
active. The mode is selected by the `VITE_API_MODE` build env var and shown in the
runtime status bar (so the demo can never silently pass fixtures off as live data,
or the reverse):

- **`http`** (default) — talks to the real adapter through the two endpoints.
- **`mock`** — typed fixtures with simulated latency; needs no backend. Use it for
  an offline demo or when the adapter is not running. Set with
  `VITE_API_MODE=mock` (e.g. `VITE_API_MODE=mock npm run dev`).

Tests always inject the mock client explicitly, independent of the env var.

## Running against the live Office Agent

From the repository root, start the adapter (localhost only, no auth — it is a
local demo surface):

```bash
uv sync --group dev --group api
uv run uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8000
```

Then, in `frontend/`:

```bash
npm run dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`, so the app is
same-origin in development. Exercise one example prompt per capability plus an
`unknown` request; the status badges reflect `PRIVACY_MODE` / `OFFLINE_MODE` /
`OFFICE_LLM_ENABLED` / effective web-search state set for the adapter process.

## Server policy and Run Settings

The workspace has two distinct settings layers, kept visually and semantically
separate on purpose.

### Server policy — read-only

The status badges in the header come from `GET /api/health` and report the
backend/runtime policy: `privacy_mode`, `offline_mode`, `office_llm_enabled`, and
`web_search_effective` (the effective, mode-aware web-search state). They are
informational chips — no click handler, no toggle — grouped under a "Server policy"
label. The frontend cannot change them: server policy is set by the API runtime, and
it can only ever *restrict* what a run does.

### Run Settings — interactive, request-scoped

Beside the composer, `RunSettingsControls` exposes real form controls for the *next*
request:

- **Privacy** — Standard / Strict (applies to external-service-capable runs)
- **LLM Assist** — Off / On (applies to Email Summary and Daily Briefing)
- **Web Search** — Off / On (applies to Knowledge Q&A)

Behavior:

- **Snapshot at submit.** The selected settings are snapshotted when you press Run
  and travel with that request; changing a control mid-run cannot affect a request
  already in flight.
- **Retry** reuses the *original* run's requested settings, so it reproduces the run
  it retries rather than picking up the current control values.
- **Reset** clears the workspace (composer, result, selection) but **preserves** the
  selected Run Settings as a user preference for the next run.
- **Applicability.** LLM Assist and Web Search apply only to the capabilities above;
  for any other routed capability they are reported "Not applicable" rather than as
  though they were used.
- **Server overrides.** A request can only make a run *stricter*. A requested `Off`
  stays `Off`, and no request can enable a path the server has disabled; the backend
  resolves the request and reports what actually governed the run.

### Request and response shape

`options` is optional and backward-compatible. Omitting it sends the original body
and the response comes back with `run_settings: null`:

```json
POST /api/agent/run
{
  "text": "Summarize my unread emails",
  "options": { "privacy_mode": "standard", "llm_assist": false, "web_search": false }
}
```

The response then carries `run_settings` (or `null`):

```json
{
  "intent": "email_summary",
  "run_settings": {
    "requested":     { "privacy_mode": "standard", "llm_assist": true,  "web_search": false },
    "effective":     { "privacy_mode": "standard", "llm_assist": true,  "web_search": false },
    "applicability": { "llm_assist": true, "web_search": false },
    "constraints": []
  }
}
```

- `requested` — what the frontend submitted.
- `effective` — what actually governed the run (authoritative; the UI never
  re-derives it).
- `applicability` — whether LLM Assist / Web Search apply to the routed capability.
- `constraints` — stable typed reasons `requested` and `effective` differ (e.g.
  `server_privacy_mode`, `web_search_not_applicable`); `RunSettingsSummary` maps them
  to human text.

The `mock` client resolves `run_settings` the same way the adapter does, so the
offline demo shows the requested/effective split too.

## Honest-observability principles

These are load-bearing, not stylistic:

- **The engines are the single source of truth.** The UI renders `content`
  verbatim (React default escaping, no `dangerouslySetInnerHTML`) and never
  re-parses it to recompute counts, dates, priorities, or lists, and never rewords
  engine text. Per-intent renderers **frame** (icon, title, accent,
  monospace-preserved text, the `sources` array, caveat emphasis) — they never
  re-derive.
- **Every displayed value traces to a named engine field.** `duration_ms` is
  labeled **adapter-measured** (wall clock around the single engine call) and
  `execution_mode` **adapter-derived** (a presentation classification), because
  neither is engine telemetry.
- **Observability is never fabricated.** The rich timeline appears for Knowledge
  Q&A only, from real `AnswerResult` metadata; every other capability explicitly
  states that it exposes no execution timeline rather than showing a fake one.
- **No browser-clock dates.** The UI never computes "today" from `new Date()` /
  `Date.now()` for any business date; all dates render verbatim from engine output
  (the mock tools are anchored to their data, not the system clock).
- **Run Settings honesty.** While a run is in flight, Execution Details shows only
  the *requested* snapshot ("waiting for the backend to report which settings
  actually govern this run"); after completion, `effective` is shown strictly from
  the backend's `run_settings` and is authoritative. A `null` `run_settings` is
  stated as "the backend did not report effective settings"; a browser-stopped run
  says the effective settings are unavailable rather than pretending a final answer
  arrived. The UI never infers effective settings from the server-policy badges.

## Testing

```bash
npm test        # Vitest + React Testing Library on jsdom
```

Coverage includes: fixtures typechecking against `types/api.ts`; the composer
submitting the typed request; each UI state (empty/loading/success/degraded/error/
stopped/unsupported); the status classifier over the `StopReason` union; per-intent
result framing and verbatim content (a direct render test for every routed
capability); the Knowledge Q&A timeline; and the HTTP client's error taxonomy. CI
runs `npm ci`, `npm run build`, `npm test`, and `npm run test:responsive` on
Node 20 with no API keys and no deployment steps.

## Responsive verification

Real-browser layout is verified with **Playwright (Chromium only)** against the Vite
dev server in typed **mock** mode — no FastAPI server, no API key, and no network
beyond localhost. It supplements the Vitest unit suite; it does not replace it.

```bash
npx playwright install chromium   # one-time: fetch the Chromium binary
npm run test:responsive
```

Three viewport categories are checked with actual rendered geometry (element
bounding boxes, visibility, and
`document.documentElement.scrollWidth <= window.innerWidth`) — not just the presence
of CSS or media queries:

- **Wide desktop (1440 × 900)** — sidebar visible, the narrow-screen toggle hidden,
  main and the execution aside side by side, composer and Run Settings usable.
- **Medium (1000 × 900)** — sidebar still available, the execution aside stacks below
  the main column, controls reachable.
- **Narrow / mobile (390 × 844)** — sidebar collapsed behind a keyboard-operable
  toggle whose `aria-expanded` tracks state; a mock request runs and its result stays
  readable; result actions stay within the viewport; preformatted content wraps;
  execution details remain reachable below the result; Stop stays reachable while a
  request is loading.

Every viewport also asserts no document-level horizontal overflow. Playwright's
`webServer` starts Vite with `VITE_API_MODE=mock` through its `env` option (not a
shell prefix), so the command is identical on Windows, macOS, and Linux. Generated
`playwright-report/` and `test-results/` are gitignored, and the run is configured
with reporter `list` and trace/screenshot/video off, so nothing is produced to
commit.

## Screenshots

_Placeholder — add workspace screenshots here (three-pane layout, a Knowledge Q&A
timeline, and a degraded run) when capturing them for the portfolio._

## Non-goals

No token streaming/SSE/WebSocket, no authentication, no database or persistent
history, no deployment tooling, and no duplicated business logic. See
[ADR 021](../docs/adr/021-frontend-observability-workspace.md) §5.
