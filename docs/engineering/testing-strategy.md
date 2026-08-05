# Testing Strategy

This repository is validated by a **fully mocked, CI-safe** test suite plus a
key-gated integration layer and a separate behavioral eval harness. The guiding
principle: the default test run must be **deterministic and require no API keys or
network**, so anyone (and CI) can validate the repository offline.

## Test suites at a glance

| Suite | Scope | External calls |
|---|---|---|
| [`tests/enterprise_rag/nodes/`](../../tests/enterprise_rag/nodes/) | Each `enterprise_rag` node's in/out behavior, the web-result relevance gate, defensive parsing, and graceful degradation | None — every dependency mocked at its lazy `get_*()` seam |
| [`tests/enterprise_rag/graph/`](../../tests/enterprise_rag/graph/) | The routing functions, privacy toggle, stop reasons, budgets/counters, caveat formatting, and compiled-graph end-to-end runs | None — fully mocked |
| [`tests/enterprise_rag/evals/`](../../tests/enterprise_rag/evals/) | The Enterprise RAG eval harness's pure helpers (dataset validation, per-row checks, metrics, rendering) | None — pure functions |
| [`tests/office_agent/`](../../tests/office_agent/) | The Office Agent: router, engine dispatch, each mock tool, **and the two LLM assists** — flag-off byte-for-byte guarantee, grounding validation, and deterministic fallback | None — fully mocked/deterministic; Knowledge adapter and the LLM assists patched at their seams |
| [`tests/office_agent/evals/`](../../tests/office_agent/evals/) | The two Office Agent LLM-assist eval runners' pure helpers (env loading, dataset validation, CONFIG/INFRA/EVAL_FAIL classification) | None — offline; chain and env preconditions patched |
| [`tests/api/`](../../tests/api/) | The thin FastAPI adapter (`api/`): the health flag matrix, 1:1 response mapping, the `execution_mode` matrix, request-validation bounds, the type-name-only 500 handler, the `observability` / `run_settings` pass-through, the app-factory tracing-privacy enforcement, and the OpenAPI wire contract | None — `fastapi.testclient` with `answer_office_request` and the flag readers monkeypatched; needs the `api` dependency group installed |
| [`tests/test_environment_isolation.py`](../../tests/test_environment_isolation.py) | Pytest's environment isolation and real-model authorization matrix | None — local environment mappings only; no provider client is built |
| [`tests/enterprise_rag/chains/test_generation.py`](../../tests/enterprise_rag/chains/test_generation.py) selected with `-m "not real_model"` | Document formatting and the no-context deterministic generation gate | None — the marked live-model cases are deselected |
| `frontend/` (Vitest + Playwright) | The web workspace: components, client modes, status classification, and verbatim rendering (Vitest on jsdom), plus real-browser responsive layout in typed mock mode (`npm run test:responsive`, Playwright/Chromium) | None — mock client / localhost only; run with npm from `frontend/` |
| Tests marked `real_model` under [`tests/enterprise_rag/chains/`](../../tests/enterprise_rag/chains/) | The six **Enterprise RAG** LCEL chains against the real `gpt-5-mini` | **Real OpenAI API** — require `RUN_REAL_MODEL_TESTS=1` **and** `OPENAI_API_KEY`; excluded from keys-free CI |
| [`tests/office_agent/integration/`](../../tests/office_agent/integration/) | The two **Office Agent LLM-assist** chains (email digest + briefing narrative) against the real `gpt-5-mini` | **Real OpenAI API** — marked `real_model` (via the `requires_openai` alias); skips unless `RUN_REAL_MODEL_TESTS=1` **and** `OPENAI_API_KEY` are set; excluded from keys-free CI |

## Unit tests

Unit tests target the **lazy seam** — every external client is constructed inside
a lazy factory (`@lru_cache def get_x()`), so tests patch that factory with
`monkeypatch` instead of the real client. This keeps imports side-effect-free and
makes each node/tool testable in isolation with no keys and no network.

## Office Agent tool tests

Each Office Agent tool (`email`, `calendar`, `tickets`, `briefing`, `meeting`,
`approvals`, and the `knowledge` adapter) has fully mocked, deterministic tests in
`tests/office_agent/`. Because the mock tools read static JSON anchored to the
data (not the system clock), their output is identical on every run, so tests
assert exact rendered content rather than fuzzy matches.

## Router tests

The router is pure keyword matching, so its tests are exhaustive and
deterministic: they assert that representative requests classify to the expected
intent and that **precedence** holds (e.g. an `APR-<n>` / approval request routes
to `workflow_approval` before ticket/task; meeting-prep phrasing routes to
`meeting_agent` before the broad calendar keywords; unsupported requests fall to
`unknown`).

## Engine dispatch tests

Dispatch tests verify that `answer_office_request()` routes each intent to exactly
one tool and builds a uniform `OfficeAgentResponse` with the routed intent
attached. The Knowledge Q&A path is tested with the `enterprise_rag` adapter
**patched** — the real graph is never invoked from the Office Agent suite.

## Mock-data no-mutation tests

Because simulated actions (task creation, approve/reject) must never mutate the
repo mock data, the Office Agent tests assert **no mutation**:
`handle_approval_request` and the pure `build_simulated_*` helpers compute results
in the response only. The optional `record_decision(..., persist_path=...)` seam
is exercised against a caller-provided path (pytest's `tmp_path`), never the
repo's `mock_data/` files.

## CI-safe design

- **Imports are side-effect-free** — importing any module constructs no external
  client and needs no keys.
- **External clients are lazy** (`@lru_cache`), so tests patch one well-known seam.
- **Mock data is deterministic** — anchored to the data, not the wall clock.
- **Ordinary pytest is environment-isolated** — `tests/conftest.py` forces
  `OFFICE_LLM_ENABLED=false` and disables `.env` loading for the pytest process,
  so a developer's local `.env` cannot enable an assist or leak credentials into
  ordinary tests. Real-model tests additionally require the deliberate
  `RUN_REAL_MODEL_TESTS=1` opt-in — a key alone never authorizes a paid call.
- CI ([`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)) runs three
  parallel keys-free jobs: **`mocked-tests`** (the fully mocked Python suites,
  including `tests/api/`, plus `tests/test_environment_isolation.py` and
  `tests/enterprise_rag/chains/test_generation.py -m "not real_model"`),
  **`lint`** (`ruff check`, `ruff format --check`, and scoped `mypy` — whose
  `pyproject.toml` scope includes `api/`), and
  **`frontend`** (`npm ci`, `npm run build`, `npm test`, `npm run test:responsive`
  on Node 20).

## Avoiding external calls

- **Node/graph/eval/office_agent tests never call OpenAI, Tavily, Chroma, or
  embeddings.** They pass with no API keys.
- **Do not** introduce a real network call into these suites. If a new capability
  needs an external dependency, put it behind a lazy factory and patch that seam.
- The tests that call real services are marked `real_model` under
  `tests/enterprise_rag/chains/` (Enterprise RAG chains) and
  `tests/office_agent/integration/` (the two Office Agent LLM-assist chains).
  The legacy `requires_openai` name is an alias; marked tests skip
  unless **both** the deliberate `RUN_REAL_MODEL_TESTS=1` opt-in and
  `OPENAI_API_KEY` are set; both suites are excluded
  from keys-free CI. **Do not run either without explicit approval.**

## Full-suite validation

```powershell
# Fully mocked suites — NO API keys required
uv run pytest tests/enterprise_rag/nodes/ tests/enterprise_rag/graph/ tests/enterprise_rag/evals/ tests/office_agent/ --ignore=tests/office_agent/integration -v

# Mocked API adapter suite — keys-free (needs the api dependency group installed)
uv run pytest tests/api/ -v

# Environment-isolation and deterministic generation gates — keys-free
uv run pytest tests/test_environment_isolation.py -v
uv run pytest tests/enterprise_rag/chains/test_generation.py -m "not real_model" -v

# Whole ordinary suite (real-model tests skip unless RUN_REAL_MODEL_TESTS=1 and OPENAI_API_KEY are both set)
uv run pytest -v
```

The fully mocked and deterministic selections pass with no API keys. Tests
marked `real_model` under `tests/enterprise_rag/chains/` and the
`tests/office_agent/integration/` suite are skipped unless both
`RUN_REAL_MODEL_TESTS=1` and `OPENAI_API_KEY` are set.

## Behavioral evals

Behavioral evals live under [`evals/`](../../evals/), are **separate from the test
suites**, and are **excluded from CI**. There are two, one per module; each has a
keys-free `--validate-only` mode and an approval-gated full run.

### Enterprise RAG behavioral eval

[`evals/enterprise_rag/`](../../evals/enterprise_rag/) runs a 24-row dataset
through the **real** `enterprise_rag` compiled graph
(`enterprise_rag.graph.engine.answer_question()`) and scores deterministic checks
(stop reasons, source provenance, counters, expected substrings, fallback-policy
echoes). Relevant when you change `enterprise_rag` behavior (routing, prompts,
grading, fallback policy).

```powershell
uv run python evals/enterprise_rag/run_eval.py --validate-only   # keys-free
```

### Office Agent LLM-assist behavioral evals

[`evals/office_agent/llm_assist/`](../../evals/office_agent/llm_assist/) evaluates
**only** the two optional LLM assists (the deterministic tools are covered by
`tests/office_agent/`). Relevant when you change an assist's prompt, grounding, or
output shape.

- **Email Digest** — action-item recall, deadline correctness, no invented
  deadlines, email-id grounding, and priority-order validity.
- **Daily Briefing Narrative** — critical-fact coverage, valid references,
  cross-source coverage, conflict-counterpart references, and grounded output.

```powershell
uv run python evals/office_agent/llm_assist/run_email_digest_eval.py --validate-only
uv run python evals/office_agent/llm_assist/run_briefing_narrative_eval.py --validate-only
```

A full run of either eval calls the real `gpt-5-mini`, needs `OPENAI_API_KEY`, and
must **never** run without explicit approval; `--validate-only` is keys-free and
safe.

## Validation by change type

Always run `ruff check .`, `ruff format --check .`, and `mypy`. Then, by what you
touched:

- **Docs only** — `git diff --check` and confirm links/paths resolve; no test or
  eval run required.
- **Deterministic Office Agent change** (router, base tools, dispatch) —
  `uv run pytest tests/office_agent/ --ignore=tests/office_agent/integration -v` plus the local demo
  (`uv run python scripts/demo_office_agent_v1.py`).
- **Office LLM-assist change** — `uv run pytest tests/office_agent/ --ignore=tests/office_agent/integration -v` (mocked,
  incl. the flag-off guarantee) **plus** the two assist `--validate-only`
  commands above. The gated `tests/office_agent/integration/` real-model tests and full
  assist evals run **only with explicit approval** and a real key.
- **Enterprise RAG change** —
  `uv run pytest tests/enterprise_rag/nodes/ tests/enterprise_rag/graph/ tests/enterprise_rag/evals/ -v` plus the deterministic generation selection above;
  tests marked `real_model` and the full RAG eval run **only with explicit approval**.
- **API adapter change (`api/` or the `OfficeAgentResponse` contract)** —
  `uv run pytest tests/api/ -v` (mocked, keys-free; needs the `api` dependency
  group installed) plus `mypy` (its scope covers `api/`).
- **Frontend change (`frontend/`)** — from `frontend/`: `npm run build`,
  `npm test`, and `npm run test:responsive` (Playwright/Chromium in typed mock
  mode; one-time `npx playwright install chromium`). Frontend-only changes need
  no Python suites.

## Recommended pre-PR commands

```powershell
git status --short
git diff --check
uv run pytest tests/office_agent/ --ignore=tests/office_agent/integration -v   # Office Agent work
uv run pytest -v                          # broader changes
uv run ruff check .
uv run ruff format --check .
uv run mypy
```
