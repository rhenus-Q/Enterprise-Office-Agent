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
main.py                 # CLI over the enterprise_rag engine
enterprise_rag/         # Enterprise Document Q&A / Agentic RAG engine (LangGraph)
  graph/                #   StateGraph, nodes, chains, engine, config, state, consts, formatting
  ingestion.py          #   Build the Chroma index from the local Markdown corpus
  data/                 #   Synthetic AcmeCorp corpus (6 fictional documents)
office_agent/           # Deterministic office-workflow agent
  router.py             #   Keyword intent router (no LLM)
  engine.py             #   answer_office_request() entry point + dispatch
  schemas.py            #   Intent constants + typed dataclasses
  tools/                #   One tool per intent
  mock_data/            #   Fictional AcmeCorp JSON (read-only, deterministic)
scripts/                # Local demos (demo_office_agent_v1.py)
tests/                  # node/ graph/ evals/ office_agent/ (mocked) + chains/ (key-gated)
evals/                  # Behavioral eval harness for enterprise_rag (not in CI)
docs/                   # ADRs, engineering docs, release notes, Office Agent demo doc
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

## Setup with uv

Requires **Python ≥ 3.11** and [uv](https://docs.astral.sh/uv/). Run everything
from the repository root.

```powershell
uv sync --group dev                 # create .venv from the committed uv.lock
uv run pre-commit install           # one-time per clone (mirrors CI lint)
```

Only the RAG engine / Knowledge Q&A needs API keys and a built index:

```powershell
Copy-Item .env.example .env         # add OPENAI_API_KEY (+ TAVILY_API_KEY if web search on)
uv run python -m enterprise_rag.ingestion   # one-time Chroma build
```

## Run the local Office Agent demo

The default demo is local-only and needs **no API keys**:

```powershell
uv run python scripts/demo_office_agent_v1.py
uv run python scripts/demo_office_agent_v1.py --include-knowledge   # also hits the real RAG pipeline
```

For the full capability list, routing precedence, and example requests, see the
dedicated demo / usage doc: [`docs/office-agent-v1-demo.md`](../office-agent-v1-demo.md).

## Run the tests

```powershell
# Fully mocked suites — NO API keys required
uv run pytest tests/node/ tests/graph/ tests/evals/ tests/office_agent/ -v

# Office Agent suite only
uv run pytest tests/office_agent/ -v

# Whole suite (chains/ integration tests are skipped without OPENAI_API_KEY)
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
| Office Agent tests | [`tests/office_agent/`](../../tests/office_agent/) |

## How to add a new Office Agent tool safely

The Office Agent is deterministic and local by design. To add a capability
without regressing anything:

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
   - contact **no external service** and use **no LLM** (Knowledge Q&A is the only
     exception, and it already exists as an adapter — do not duplicate RAG logic);
   - keep any "action" **simulated** (computed in the response); only an explicit
     persistence *seam* (e.g. a `persist_path=` argument used by tests) may write,
     and never to the repo `mock_data/`.
4. **Wire the dispatch** in `office_agent/engine.py`.
5. **Add fully mocked tests** in `tests/office_agent/` (patch the Knowledge
   adapter; never call external services). Include a no-mutation assertion if the
   tool simulates an action.
6. **Update the docs** — [`docs/office-agent-v1-demo.md`](../office-agent-v1-demo.md),
   `README.md`, and `structure.md` — and add release notes if it ships as a new
   version.

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
uv run pytest tests/office_agent/ -v          # or the full suite: uv run pytest -v
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run python scripts/demo_office_agent_v1.py # if you touched the Office Agent
```

Prefer **small, scoped PRs**. Keep the diff minimal and reviewable, and update the
docs alongside any behavior change.
