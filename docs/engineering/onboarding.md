# Engineering Onboarding

This guide helps a new engineer get productive on the **Enterprise Office Agent**
repository. It covers the layout, the module boundary, local setup, how to run
things, where each concern lives, how to add a new Office Agent tool safely, and a
pre-PR checklist.

For *why* the code is shaped the way it is, read the Architecture Decision Records
in [`docs/adr/`](../adr/README.md). For the RAG engine's full workflow, read
[`structure.md`](../../structure.md).

## Repo layout

```
main.py                 # Repository-level entry point → launches the Office Agent CLI
enterprise_rag/         # Enterprise Document Q&A / Agentic RAG engine (LangGraph)
  cli.py                #   Standalone Interactive RAG CLI (uv run python -m enterprise_rag.cli)
  graph/                #   StateGraph, nodes, chains, engine, config, state, consts, formatting
  ingestion.py          #   Build the Chroma index from the local Markdown corpus
  data/                 #   Synthetic AcmeCorp corpus (6 fictional documents)
office_agent/           # Office-workflow agent: deterministic router + base tools, two optional LLM assists
  cli.py                #   Interactive Office Agent CLI over answer_office_request()
  README.md             #   Canonical Office Agent usage guide (capabilities, routing, assists)
  router.py             #   Keyword intent router (no LLM)
  engine.py             #   answer_office_request() entry point + dispatch
  schemas.py            #   Intent constants + typed dataclasses
  run_settings.py       #   Request-scoped Run Settings resolver (pure; server policy wins — ADR 021)
  tools/                #   One tool per intent
  llm_assist/           #   Optional, default-off LLM assists (email digest + briefing narrative)
  mock_data/            #   Fictional AcmeCorp JSON (read-only, deterministic)
api/                    # Thin FastAPI adapter over answer_office_request(): GET /api/health + POST /api/agent/run (ADR 021)
frontend/               # Vite + React + TypeScript observability workspace (npm-managed; see frontend/README.md)
scripts/                # Local demos (demo_office_agent_v1.py)
tests/                  # enterprise_rag/{nodes,graph,evals} + office_agent/ + api/ (mocked) + enterprise_rag/chains/ & office_agent/integration/ (key-gated real-model)
evals/                  # Behavioral evals (not in CI): enterprise_rag/ + office_agent/llm_assist/
docs/                   # ADRs (adr/), engineering docs, release notes, employee quickstart (employee-guide/)
```

## Module boundary (read this first)

- **`enterprise_rag/` owns all RAG behavior** — retrieval, grading, generation,
  the LangGraph state machine, prompts, and provenance. It is behavior-stable:
  do not change graph routing, prompts, model names (`gpt-5-mini`), the state
  schema, or test expectations unless a task explicitly asks.
- **`office_agent/` owns deterministic office-workflow routing and tools.** It is
  a thin keyword router + tool dispatch, **not** a LangGraph graph, and it uses
  **no LLM routing**.
- **`office_agent` must not duplicate `enterprise_rag` internals.** The only
  crossing point is the **Knowledge Q&A adapter**
  ([`office_agent/tools/knowledge.py`](../../office_agent/tools/knowledge.py)),
  which calls `enterprise_rag.graph.engine.answer_question()` and reuses its
  formatting.
- **Mock tools are local-only, deterministic, CI-safe, and read-only by
  default.** Simulated actions never mutate the repo mock data.
- **Two optional, default-off LLM assists** live in
  [`office_agent/llm_assist/`](../../office_agent/llm_assist/) — an **Email
  Digest** on Email Summary and a **Daily Briefing Narrative** on Daily Briefing.
  Gated by `OFFICE_LLM_ENABLED`, they make a single structured-output
  `gpt-5-mini` call, ground it against the tool's selected facts, and fall back to
  the deterministic output on any failure. They are presentation layers — **not**
  new intents or capabilities — and, alongside Knowledge Q&A, the only sanctioned
  LLM paths in `office_agent`. The router itself remains LLM-free.
- **The presentation tier (`api/` + `frontend/`) adds no engine behavior**
  ([ADR 021](../adr/021-frontend-observability-workspace.md)). The thin FastAPI
  adapter's only engine call is `office_agent.engine.answer_office_request()` —
  it never calls `enterprise_rag` directly and duplicates no routing, privacy,
  formatting, or tool logic. The frontend reaches the Office Agent only through
  the adapter's two endpoints (`GET /api/health`, `POST /api/agent/run`) and
  re-derives nothing the backend owns.

## Setup with uv

Requires **Python ≥ 3.11** and [uv](https://docs.astral.sh/uv/). Run everything
from the repository root.

```powershell
uv sync --group dev --group api     # create .venv from the committed uv.lock (the api group is
                                    # needed: pytest collects tests/api/ and mypy type-checks api/)
uv run pre-commit install           # one-time per clone (mirrors CI lint)
```

Most of the Office Agent is local and key-free. API keys are needed only for:

- **Knowledge Q&A / the RAG engine** — `OPENAI_API_KEY`, a built **Chroma** index,
  and optionally `TAVILY_API_KEY` (when web search is enabled).
- **The two optional Office LLM assists** — `OPENAI_API_KEY` only (**no** Chroma),
  and only when `OFFICE_LLM_ENABLED` is set.

```powershell
Copy-Item .env.example .env         # add OPENAI_API_KEY (+ TAVILY_API_KEY if web search on)
uv run python -m enterprise_rag.ingestion   # one-time Chroma build (Knowledge Q&A only)

# Optional: enable the two default-off Office LLM assists (needs OPENAI_API_KEY, no Chroma).
# Set OFFICE_LLM_ENABLED=true in .env; OFFICE_LLM_REQUEST_TIMEOUT_SECONDS bounds each call (default 60).
```

## Run the local Office Agent demo

The default demo is local-only and needs **no API keys**:

```powershell
uv run python scripts/demo_office_agent_v1.py
uv run python scripts/demo_office_agent_v1.py --include-knowledge   # also hits the real RAG pipeline
```

For the full capability list, routing precedence, and example requests, see the
dedicated demo / usage doc: [`office_agent/README.md`](../../office_agent/README.md).

## Run the web workspace (optional)

The observability workspace runs against the thin adapter — the deterministic
capabilities and the `unknown` route need no API keys:

```powershell
uv run uvicorn api.app:create_app --factory --host 127.0.0.1 --port 8000

cd frontend
npm install          # or `npm ci` against the committed package-lock.json
npm run dev          # Vite dev server (proxies /api → http://127.0.0.1:8000)
```

See [`frontend/README.md`](../../frontend/README.md) for the client modes and
the honest-observability rules.

## Run the tests

```powershell
# Fully mocked suites — NO API keys required
uv run pytest tests/enterprise_rag/nodes/ tests/enterprise_rag/graph/ tests/enterprise_rag/evals/ tests/office_agent/ --ignore=tests/office_agent/integration -v

# Office Agent suite only
uv run pytest tests/office_agent/ --ignore=tests/office_agent/integration -v

# Mocked API adapter suite — keys-free, needs the api dependency group
uv run pytest tests/api/ -v

# Whole ordinary suite (real-model tests skip unless RUN_REAL_MODEL_TESTS=1 and OPENAI_API_KEY are set)
uv run pytest -v
```

See [`testing-strategy.md`](testing-strategy.md) for how the suites are organized.

## Lint, format check, and mypy

```powershell
uv run ruff check .            # lint
uv run ruff format --check .   # format check (CI mode)
uv run ruff format .           # apply formatting
uv run mypy                    # type-check the scoped engine-API surface
```

## Where things live

| Concern | Location |
|---|---|
| Office Agent intents (constants + routing) | [`office_agent/schemas.py`](../../office_agent/schemas.py) (`INTENT_*`, `OFFICE_INTENTS`) and [`office_agent/router.py`](../../office_agent/router.py) |
| Office Agent dispatch / entry point | [`office_agent/engine.py`](../../office_agent/engine.py) (`answer_office_request`) |
| Office Agent tools | [`office_agent/tools/`](../../office_agent/tools/) (one module per intent) |
| Office Agent mock data | [`office_agent/mock_data/`](../../office_agent/mock_data/) (read-only JSON) |
| enterprise_rag logic | [`enterprise_rag/graph/`](../../enterprise_rag/graph/) (engine, nodes, chains, graph) |
| RAG corpus + ingestion | [`enterprise_rag/data/`](../../enterprise_rag/data/) + [`enterprise_rag/ingestion.py`](../../enterprise_rag/ingestion.py) |
| Office LLM assists (optional, default-off) | [`office_agent/llm_assist/`](../../office_agent/llm_assist/) — email digest + briefing narrative; `config.py` reads `OFFICE_LLM_ENABLED` / `OFFICE_LLM_REQUEST_TIMEOUT_SECONDS` |
| Office Agent tests | [`tests/office_agent/`](../../tests/office_agent/) (mocked/offline) and [`tests/office_agent/integration/`](../../tests/office_agent/integration/) (gated real-model assist chains) |
| Office assist behavioral evals | [`evals/office_agent/llm_assist/`](../../evals/office_agent/llm_assist/) — runners + `*_cases.jsonl` datasets |
| Request-scoped Run Settings | [`office_agent/run_settings.py`](../../office_agent/run_settings.py) (`OfficeRunOptions`, `resolve_run_settings`; ADR 021) |
| HTTP adapter (presentation tier) | [`api/`](../../api/) — `app.py` (`create_app()` factory, two routes) + `schemas.py` (Pydantic wire models); mocked tests in [`tests/api/`](../../tests/api/) |
| Frontend observability workspace | [`frontend/`](../../frontend/) — see [`frontend/README.md`](../../frontend/README.md) |
| Why the assists are shaped this way | [ADR 017](../adr/office_agent/017-office-agent-llm-assist-email-digest.md) (email digest), [ADR 018](../adr/office_agent/018-office-agent-llm-assist-daily-briefing.md) (briefing narrative) |

## How to add a new Office Agent tool safely

The Office Agent's router and base tools are deterministic and local by design
(the two optional LLM assists are the separate, explicit exception covered below).
To add a **base capability** without regressing anything:

1. **Add an intent constant** in `office_agent/schemas.py` (`INTENT_*`) and append
   it to `OFFICE_INTENTS`. Keep it in lockstep with the router and the dispatch.
2. **Add a route rule** in `office_agent/router.py` using ordered,
   case-insensitive keyword matching — **no LLM routing**. Mind the precedence:
   place the new rule so it does not shadow (or get shadowed by) existing ones.
3. **Add the tool** in `office_agent/tools/<name>.py`. It must:
   - return a `ToolResult` (`tool`, `content`, `stop_reason`, `sources`, `run_id`);
   - keep **imports side-effect-free** — load data lazily (e.g. `@lru_cache`),
     never at import time;
   - read any mock data as **read-only** and anchor dates to the data, **not** the
     system clock;
   - by default contact **no external service** and use **no LLM** — a new *base*
     tool stays deterministic and local (Knowledge Q&A already exists as the RAG
     adapter — do not duplicate RAG logic; adding an LLM assist is a separate,
     explicit decision covered below, not part of a normal tool);
   - keep any "action" **simulated** (computed in the response); only an explicit
     persistence *seam* (e.g. a `persist_path=` argument used by tests) may write,
     and never to the repo `mock_data/`.
4. **Wire the dispatch** in `office_agent/engine.py`.
5. **Add fully mocked tests** in `tests/office_agent/` (patch the Knowledge
   adapter; never call external services). Include a no-mutation assertion if the
   tool simulates an action.
6. **Update the docs** — [`office_agent/README.md`](../../office_agent/README.md),
   `README.md`, and `structure.md` — and add release notes if it ships as a new
   version.

## How to add a new Office Agent LLM assist (rare, explicit)

Base tools stay deterministic; adding an LLM assist is a deliberate, separately
justified step — **not** a default and **not** a new intent. Follow the pattern
the two existing assists use ([`office_agent/llm_assist/`](../../office_agent/llm_assist/),
[ADR 017](../adr/office_agent/017-office-agent-llm-assist-email-digest.md) /
[ADR 018](../adr/office_agent/018-office-agent-llm-assist-daily-briefing.md)):

1. **Record the decision in a new ADR** — an assist is an architectural change.
2. **Gate it default-off** behind `OFFICE_LLM_ENABLED` and keep a byte-for-byte
   flag-off guarantee (flag unset ⇒ the deterministic output, no client built).
3. **Build the model client lazily** (`@lru_cache`), only when enabled, and bound
   each call by `OFFICE_LLM_REQUEST_TIMEOUT_SECONDS`.
4. **Make a single structured-output `gpt-5-mini` call and validate its output
   against the exact facts the tool selected** (grounding). The assist has **no
   action surface** — it cannot send, reply, approve, reject, delete, modify, or
   persist anything.
5. **Fall back deterministically** on any timeout / API / parse / grounding
   failure: return the deterministic output plus an honest caveat and an
   `llm_assist_error` stop reason.
6. **Test it three ways** — mocked/offline tests in `tests/office_agent/`
   (including the flag-off guarantee, patched at the LLM seam), a gated
   real-model chain test in `tests/office_agent/integration/`, and a behavioral eval under
   `evals/office_agent/llm_assist/`.

## What not to touch casually

- **`enterprise_rag` behavior** — graph routing, prompts, model names, the
  `GraphState` schema, chain input variables, node return structures, eval
  semantics, or the corpus.
- **`GraphState` reducers** — the fields are plain last-value channels; do not add
  `typing.Annotated` accumulating channels (the engine merges streamed updates
  with `dict.update()`).
- **Tests and mock data** — do not change them to make a docs/refactor task pass.
- **`.env` files, model names, and dependencies** — do not add dependencies or
  swap models as a side effect.
- **`docs/roadmap/`** and generated/ignored artifacts (e.g.
  `docs/roadmap/architecture-review/`, `evals/enterprise_rag/history/*.json`).

## Common pre-PR validation checklist

Run these from the repo root before opening a PR (see
[`release-checklist.md`](release-checklist.md) for the fuller release version):

```powershell
git status --short
git diff --check
uv run pytest tests/office_agent/ --ignore=tests/office_agent/integration -v   # or the full suite: uv run pytest -v
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run python scripts/demo_office_agent_v1.py # if you touched the Office Agent
uv run pytest tests/api/ -v                   # if you touched api/ or the office_agent response contract
cd frontend; npm run build; npm test; npm run test:responsive   # if you touched frontend/ (one-time: npx playwright install chromium)
```

Prefer **small, scoped PRs**. Keep the diff minimal and reviewable, and update the
docs alongside any behavior change.
