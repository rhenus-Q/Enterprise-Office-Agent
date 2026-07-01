# Enterprise Office Agent

[![CI](https://github.com/rhenus-Q/Enterprise-Office-Agent/actions/workflows/ci.yml/badge.svg)](https://github.com/rhenus-Q/Enterprise-Office-Agent/actions/workflows/ci.yml)

**A repository for enterprise AI automation, built with LangGraph.** It is organized
as a set of focused modules. Today it ships one completed module — an enterprise
document Q&A / RAG engine — and reserves room for an office-automation agent to be
built alongside it.

## Modules

| Module | Status | What it is |
|---|---|---|
| [`enterprise_rag/`](enterprise_rag/README.md) | ✅ **Implemented** | **Enterprise Document Q&A Engine** (企业文档问答引擎) — a self-correcting Agentic RAG (CRAG-style) LangGraph workflow that answers questions from an ingested internal-document knowledge base, with web-search fallback, privacy mode, quality gates, bounded self-correction, per-run budgets, graceful degradation, and deterministic provenance. |
| `office_agent/` | 🚧 **Planned** | Reserved placeholder for a future **Enterprise Office Agent** (office automation). Intentionally empty — no features implemented yet. |

The completed engine is fully documented in **[`enterprise_rag/README.md`](enterprise_rag/README.md)**
(setup, usage, privacy mode, fallback policy, the programmatic engine API, budgets,
failure handling, evals). This root document is the repository-level overview.

## Repository layout

```
.
├── main.py                      # CLI entry point: interactive Q&A loop over the enterprise_rag engine
├── enterprise_rag/              # ✅ Enterprise Document Q&A Engine (企业文档问答引擎) — see enterprise_rag/README.md
│   ├── README.md                #   Module docs: detailed setup, usage, API, budgets, failure handling
│   ├── ingestion.py             #   KB build: load local Markdown corpus → split → embed → persist to Chroma
│   ├── data/acmecorp_internal_docs/  #   Synthetic AcmeCorp corpus: 6 fictional internal policy/guide documents
│   └── graph/                   #   StateGraph, nodes, chains, engine, config, state, consts, formatting
├── office_agent/                # 🚧 Placeholder for the future Enterprise Office Agent (not implemented yet)
├── structure.md                 # Architecture deep-dive: full workflow, state machine, module boundaries
├── docs/
│   └── adr/                     # Architecture Decision Records 001–014 (repo-level; index in docs/adr/README.md)
├── evals/                       # Behavioral eval harness for enterprise_rag (dataset, runner, report) — not in CI
├── tests/                       # node/ + graph/ + evals/ (fully mocked) and chains/ (integration, key-gated)
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

# 3. Configure environment variables
Copy-Item .env.example .env   # then edit .env and add your keys

# 4. Build the knowledge base (one-time, before first run)
uv run python -m enterprise_rag.ingestion

# 5. Run the assistant
uv run python main.py
```

For everything the engine can do — privacy mode, the web-fallback policy, the
programmatic `answer_question()` API, run traces, per-run budgets, failure
handling, and citations — see **[`enterprise_rag/README.md`](enterprise_rag/README.md)**.

## Documentation

- **[`enterprise_rag/README.md`](enterprise_rag/README.md)** — the Enterprise RAG
  engine: full setup, usage, configuration, and API reference.
- **[`structure.md`](structure.md)** — architecture deep-dive: the full workflow,
  state machine, routing, and module boundaries.
- **[`docs/adr/`](docs/adr/README.md)** — Architecture Decision Records: *why* the
  code is the way it is (context, decision, consequences, trade-offs, alternatives).
  The package refactor that introduced this module layout is
  [ADR 014](docs/adr/014-enterprise-rag-package-and-office-agent-placeholder.md).

## Tests and CI

```powershell
# Fully mocked suites — NO API keys required
uv run pytest tests/node/ tests/graph/ tests/evals/ -v

# Integration tests — call the real gpt-5-mini, require OPENAI_API_KEY (skipped if unset)
uv run pytest tests/chains/ -v

# Whole suite
uv run pytest -v
```

GitHub Actions CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs two
parallel keys-free jobs on every push and pull request: **`mocked-tests`** (the
fully mocked `tests/node/`, `tests/graph/`, `tests/evals/` suites) and **`lint`**
(`ruff check`, `ruff format --check`, and scoped `mypy`). The key-gated
`tests/chains/` suite and the full eval run are deliberately excluded.

## Working in this repository

- **`enterprise_rag` is the completed, behavior-stable module.** Preserve its graph
  routing, prompts, model names, state schema, and test expectations unless a change
  is explicitly requested (see [CLAUDE.md](CLAUDE.md) for the full rules).
- **`office_agent` is planned, not built.** When office-agent work begins it goes in
  `office_agent/` and must not break `enterprise_rag` behavior or its tests; it should
  follow the same engineering rules (side-effect-free imports, lazy `@lru_cache`
  external clients).
- Root-level docs (`README.md`, `CLAUDE.md`, `structure.md`, `docs/adr/`) stay
  repository-level; module-specific usage lives in `enterprise_rag/README.md`.
