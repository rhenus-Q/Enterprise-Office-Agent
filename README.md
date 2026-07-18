# Enterprise Office Agent

[![CI](https://github.com/rhenus-Q/Enterprise-Office-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/rhenus-Q/Enterprise-Office-Agent/actions/workflows/ci.yml)

**An enterprise AI agent engineering project built with LangGraph.** The
repository is organized as two focused, independently reasoned modules: a
self-correcting **Enterprise Document Q&A / Agentic RAG engine**, and a
deterministic **office-workflow agent layer** that routes free-text requests to
local capabilities. The design emphasis is engineering discipline — clear module
boundaries, side-effect-free imports, lazy external clients, honest failure
handling, and a fully mocked, CI-safe test suite.

## Modules

| Module | Status | What it is |
|---|---|---|
| [`enterprise_rag/`](enterprise_rag/README.md) | ✅ **Implemented** | **Enterprise Document Q&A Engine** — a self-correcting Agentic RAG (CRAG-style) LangGraph workflow that answers questions from an ingested internal-document knowledge base, with web-search fallback, privacy mode, three quality gates, bounded self-correction, per-run budgets, graceful degradation, and deterministic provenance. Entry point: `enterprise_rag.graph.engine.answer_question()`. |
| [`office_agent/`](office_agent/) | ✅ **Implemented (v1.6 / Phase 7)** | **Enterprise Office Agent** — a **deterministic-by-default** intent router over seven capabilities: one Knowledge Q&A adapter over `enterprise_rag` plus six local mock-data tools. Entry point: `office_agent.engine.answer_office_request()`. The router and every core tool workflow are deterministic; Knowledge Q&A delegates to the `enterprise_rag` engine, and two capabilities (Email Summary, Daily Briefing) optionally support a bounded, single-pass LLM assist that is **disabled by default** and falls back to the deterministic output. |

The two modules stay decoupled: `office_agent` reaches `enterprise_rag` only
through a thin Knowledge Q&A adapter, and it never duplicates retrieval,
generation, or graph logic. See [`structure.md`](structure.md) for the module
boundary in detail.

## What the system does

- **`enterprise_rag`** answers questions from a curated local knowledge base
  (a synthetic AcmeCorp internal-document corpus in Chroma), falling back to web
  search (Tavily) when the local corpus is insufficient. Every answer passes
  explicit **document-relevance**, **answer-grounding** (anti-hallucination), and
  **answer-usefulness** gates; failed gates trigger bounded, input-changing
  retries; runs that cannot end with a passing answer record a machine-readable
  `stop_reason` and surface an honest user-facing caveat. A privacy mode disables
  web search entirely so questions never leave the local environment.
- **`office_agent`** classifies a free-text request into exactly one intent with
  a deterministic keyword router (no LLM routing) and dispatches to one tool.

### The seven Office Agent capabilities

| # | Capability | Intent | Release | Backing |
|---|---|---|---|---|
| 1 | Knowledge Q&A | `knowledge_qa` | v1 | Adapter over the real `enterprise_rag` engine |
| 2 | Email Summary | `email_summary` | v1 | Local mock data |
| 3 | Calendar Lookup | `calendar_lookup` | v1 | Local mock data |
| 4 | Task / Ticket Assistant | `ticket_assistant` | v1 | Local mock data |
| 5 | Daily Briefing | `daily_briefing` | v1 | Aggregates the mock email/calendar/ticket data |
| 6 | Meeting Agent / Meeting Prep | `meeting_agent` | v1.5 (Phase 6) | Composes the mock calendar/email/ticket data |
| 7 | Workflow / Approval Agent | `workflow_approval` | v1.6 (Phase 7) | Local mock approval queue + audit log |

### Local mock behavior vs. future production integration

Every Office Agent tool except Knowledge Q&A reads static, entirely fictional
AcmeCorp JSON from [`office_agent/mock_data/`](office_agent/mock_data/). These
data providers are **deterministic/mock-backed demonstrations**: the mock data is
**read-only** and **anchored to the data, not the system clock**, so the tools are
deterministic and CI-safe. "Task creation" and approve/reject decisions are
**simulated** (computed in the response), never written back. No external service
is ever contacted (no Gmail, Outlook, Google Calendar, Slack, Jira, Linear, Asana,
or Trello). Replacing a mock loader with a real integration is deliberately left as
future production work and is **not** part of this repository.

The default path is therefore deterministic, but it is **not** true that no Office
capability other than Knowledge Q&A can call an LLM. Two presentation/synthesis
paths — the **Email Summary** digest ([ADR 017](docs/adr/office_agent/017-office-agent-llm-assist-email-digest.md))
and the **Daily Briefing** narrative ([ADR 018](docs/adr/office_agent/018-office-agent-llm-assist-daily-briefing.md))
— may optionally call the external `gpt-5-mini` model. Both assists are **disabled
by default**; setting `OFFICE_LLM_ENABLED` enables both at once, and if an assist is
disabled or fails the tool returns its deterministic result (with an honest caveat
on failure). These assists only re-synthesize already-selected local data into a
richer summary — they gain **no action surface** and cannot send, approve, mutate,
or execute any office operation. See [`office_agent/llm_assist/`](office_agent/llm_assist/).

Two hierarchical, default-off runtime switches restrict external egress repo-wide
([ADR 019](docs/adr/enterprise_rag/019-hierarchical-runtime-privacy-modes.md)):
`PRIVACY_MODE` disables web search, LangSmith tracing, and both LLM assists while
preserving the OpenAI RAG path, and `OFFLINE_MODE` additionally disables OpenAI
and every other external service — Knowledge Q&A, ingestion, and the real-model
evals then fail closed with explicit, deterministic behavior, while the local
deterministic Office capabilities keep working.

## Repository layout

```
.
├── main.py                      # CLI entry point: interactive Q&A loop over the enterprise_rag engine
├── enterprise_rag/              # ✅ Enterprise Document Q&A Engine — see enterprise_rag/README.md
│   ├── README.md                #   Module docs: detailed setup, usage, API, budgets, failure handling
│   ├── ingestion.py             #   KB build: load local Markdown corpus → split → embed → persist to Chroma
│   ├── data/acmecorp_internal_docs/  #   Synthetic AcmeCorp corpus: 6 fictional internal policy/guide documents
│   └── graph/                   #   StateGraph, nodes, chains, engine, config, state, consts, formatting
├── office_agent/                # ✅ Enterprise Office Agent (router + Knowledge Q&A adapter + six local mock tools)
│   ├── README.md                #   Module guide: all seven capabilities, usage, optional LLM assists
│   ├── router.py                #   Deterministic keyword intent router (no LLM)
│   ├── engine.py                #   answer_office_request() entry point + tool dispatch
│   ├── schemas.py               #   Intent constants + typed ToolResult / response dataclasses
│   ├── tools/                   #   knowledge, email, calendar, tickets, briefing, meeting, approvals
│   ├── llm_assist/              #   Isolated boundary for optional, structured, grounded Office LLM assists (default off)
│   └── mock_data/               #   Fictional AcmeCorp JSON (read-only, deterministic)
├── scripts/demo_office_agent_v1.py  # Local-only Office Agent demo
├── structure.md                 # Architecture deep-dive: full workflow, state machine, module boundaries
├── docs/
│   ├── engineering/             #   Onboarding, testing strategy, release checklist
│   ├── releases/                #   Release notes (office-agent-v1.6.md)
│   └── adr/                     #   Architecture Decision Records 001–018 (repo-level; index in docs/adr/README.md)
├── evals/                       # Eval harnesses by module (not in CI): enterprise_rag/ (RAG behavioral eval) + office_agent/llm_assist/ (assist evals)
├── tests/                       # node/ + graph/ + evals/ + office_agent/ (fully mocked) and chains/ (integration, key-gated)
├── .github/workflows/ci.yml     # CI: fully mocked suites + lint — no API keys
├── pyproject.toml               # uv project config (deps, ruff, mypy, pytest)
└── CLAUDE.md                    # Repo-level guidance for Claude Code
```

## Quickstart

Requires **Python ≥ 3.11** and [uv](https://docs.astral.sh/uv/). All commands run
from the repository root.

```powershell
# 1. Clone and enter the repository
git clone https://github.com/rhenus-Q/Enterprise-Office-Agent.git
cd Enterprise-Office-Agent

# 2. Install dependencies (creates .venv from the committed uv.lock)
uv sync --group dev

# 3. Configure environment variables (only needed for the RAG engine / Knowledge Q&A)
Copy-Item .env.example .env   # then edit .env and add your keys

# 4. Build the knowledge base (one-time, before first RAG run)
uv run python -m enterprise_rag.ingestion

# 5. Run the RAG assistant
uv run python main.py
```

### Run the local Office Agent demo

```powershell
# Local-only demo (Daily Briefing, Email, Calendar, Tickets/Tasks, Meeting Prep,
# Workflow / Approval, Unknown). Deterministic and offline — no API keys or
# external services required.
uv run python scripts/demo_office_agent_v1.py

# Also run the Knowledge Q&A example (needs the enterprise_rag setup + API keys).
uv run python scripts/demo_office_agent_v1.py --include-knowledge
```

Or call it programmatically via `office_agent.engine.answer_office_request(...)`.
See [`office_agent/README.md`](office_agent/README.md) for the full
capability list, routing precedence, and example requests.

## Tests

```powershell
# Fully mocked suites — NO API keys required
uv run python -m pytest tests/enterprise_rag/nodes/ tests/enterprise_rag/graph/ tests/enterprise_rag/evals/ tests/office_agent/ --ignore=tests/office_agent/integration -v

# Office Agent suite only (fully mocked / deterministic)
uv run python -m pytest tests/office_agent/ --ignore=tests/office_agent/integration -v

# Integration tests — call the real gpt-5-mini, require OPENAI_API_KEY (skipped if unset)
uv run python -m pytest tests/enterprise_rag/chains/ tests/office_agent/integration/ -v

# Whole suite
uv run python -m pytest -v
```

## Lint, format, and type checks

```powershell
uv run ruff check .            # lint
uv run ruff format --check .   # format check (CI mode)
uv run python -m mypy          # type-check the scoped engine-API surface
```

## What does and does not require API keys

| Surface | API keys? |
|---|---|
| Office Agent local mock tools (Email, Calendar, Tickets/Tasks, Daily Briefing, Meeting Prep, Workflow/Approval) | **No** — local mock data, deterministic, offline |
| `tests/enterprise_rag/` (`nodes/`, `graph/`, `evals/`), `tests/office_agent/` (excl. `integration/`), CI | **No** — fully mocked |
| `ruff` / `mypy` | **No** |
| Knowledge Q&A + `enterprise_rag` engine (`main.py`, `--include-knowledge`) | **Yes** — `OPENAI_API_KEY` (and `TAVILY_API_KEY` when web search is enabled) |
| `tests/enterprise_rag/chains/` + `tests/office_agent/integration/` integration tests, the full eval run | **Yes** — real `gpt-5-mini`; skipped/excluded without keys |

## Current validation status

Last verified: 2026-07-02

The most recent local validation of the v1.6 baseline:

- Office Agent demo: **passed** (local-only, no keys)
- `tests/office_agent/`: **137 passed**
- Full suite (`uv run python -m pytest`): **592 passed**
- `ruff check`: **passed**
- `ruff format --check`: **passed**
- `mypy`: **passed**

GitHub Actions CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs
two parallel keys-free jobs on every push and pull request: **`mocked-tests`**
(the fully mocked suites) and **`lint`** (`ruff check`, `ruff format --check`, and
scoped `mypy`). The key-gated `tests/enterprise_rag/chains/` and
`tests/office_agent/integration/` suites and the full eval run are
deliberately excluded.

## Limitations and non-goals

- **`office_agent` tools are mock-data-backed**, not real integrations. They are
  deterministic demonstrations of the routing + tool contract, not a connection
  to any mail, calendar, ticketing, or approval system.
- **No LLM routing** in the Office Agent — intent classification is pure keyword
  matching by design (fast, offline, reproducible).
- **Single-turn** — neither module carries conversation memory.
- **No frontend, deployment tooling, or external integrations** ship in this
  repository; those are explicitly out of scope.
- The `enterprise_rag` engine's own limitations (single-turn CLI, `print`-based
  logging, sequential grading, prompt-level-only injection defense) are detailed
  in [`structure.md`](structure.md) §15.

## Documentation

- **[`enterprise_rag/README.md`](enterprise_rag/README.md)** — the Enterprise RAG
  engine: full setup, usage, configuration, and API reference.
- **[`structure.md`](structure.md)** — architecture deep-dive: the full workflow,
  state machine, routing, and the `enterprise_rag` / `office_agent` module boundary.
- **[`office_agent/README.md`](office_agent/README.md)** — the
  dedicated Office Agent demo & usage doc: all seven capabilities, routing
  precedence, the programmatic API, and example requests.
- **[`docs/engineering/onboarding.md`](docs/engineering/onboarding.md)** — new-engineer
  onboarding: repo layout, setup, module boundary, how to add a tool safely, and a
  pre-PR checklist.
- **[`docs/engineering/testing-strategy.md`](docs/engineering/testing-strategy.md)** —
  the testing strategy: unit / router / dispatch / no-mutation tests, CI-safe
  design, and when evals apply.
- **[`docs/engineering/release-checklist.md`](docs/engineering/release-checklist.md)** —
  the release checklist (validation, docs consistency, hygiene, PR/tag steps).
- **[`docs/releases/office-agent-v1.6.md`](docs/releases/office-agent-v1.6.md)** —
  Office Agent v1.6 release notes.
- **[`docs/adr/`](docs/adr/README.md)** — Architecture Decision Records: *why* the
  code is the way it is. The package refactor that introduced this module layout is
  [ADR 014](docs/adr/enterprise_rag/014-enterprise-rag-package-and-office-agent-placeholder.md);
  the original five-capability Office Agent v1 architecture is
  [ADR 015](docs/adr/office_agent/015-office-agent-v1-architecture.md), and the later Meeting
  and Workflow / Approval capability extensions (the current seven-capability
  inventory and router precedence) are
  [ADR 016](docs/adr/office_agent/016-office-agent-capability-extensions.md). The two optional,
  default-off Office LLM assists are the Email Summary digest
  ([ADR 017](docs/adr/office_agent/017-office-agent-llm-assist-email-digest.md)) and the Daily
  Briefing narrative ([ADR 018](docs/adr/office_agent/018-office-agent-llm-assist-daily-briefing.md)).

## Working in this repository

- **`enterprise_rag` is the behavior-stable module.** Preserve its graph routing,
  prompts, model names, state schema, and test expectations unless a change is
  explicitly requested (see [CLAUDE.md](CLAUDE.md) for the full rules).
- **`office_agent` uses deterministic routing and local base workflows by default.** Keep the router LLM-free (no LLM routing), keep the mock tools local-only and CI-safe, invoke Knowledge Q&A only through the adapter, keep the two optional LLM assists default-off with their byte-for-byte flag-off guarantee, and never regress `enterprise_rag`.
- Both modules follow the same discipline: side-effect-free imports and lazy
  `@lru_cache` external clients.
