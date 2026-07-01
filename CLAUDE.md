# CLAUDE.md

Guidance for Claude Code when working in this repository.

## 1. Project Overview

This repository — **Enterprise Office Agent** — is organized as named capability modules
(see [ADR 014](docs/adr/014-enterprise-rag-package-and-office-agent-placeholder.md)):

- **`enterprise_rag/`** — ✅ **the completed module**, and the subject of everything below:
  an **enterprise internal-document Q&A engine** built with **LangGraph**, implementing a
  self-correcting Agentic RAG (CRAG-style) workflow. It answers questions from an ingested
  knowledge base and falls back to web search when needed. Public entry point:
  `enterprise_rag.graph.engine.answer_question()`.
- **`office_agent/`** — ✅ **implemented: the Enterprise Office Agent (v1 + v1.5).** A
  deterministic, LLM-free intent router — entry point `office_agent.engine.answer_office_request(user_input)`
  — over local capabilities: **Knowledge Q&A** (a thin adapter over the `enterprise_rag`
  engine), **Email Summary**, **Calendar Lookup**, **Task / Ticket Assistant**, **Daily
  Briefing**, and (Phase 6 / v1.5) **Meeting Agent / Meeting Prep**. All tools except Knowledge
  Q&A run on local mock data with no LLM and no external services. Office-agent work **must not
  change or regress `enterprise_rag` behavior or its tests** (§3 rules apply: side-effect-free
  imports, lazy `@lru_cache` external clients). See [`docs/office-agent-v1-demo.md`](docs/office-agent-v1-demo.md)
  and [ADR 015](docs/adr/015-office-agent-v1-architecture.md); office-agent working rules are in §3.

Root docs (`README.md`, `CLAUDE.md`, `structure.md`, `docs/adr/`) are repository-level;
detailed engine usage lives in `enterprise_rag/README.md` and `docs/office-agent-v1-demo.md`.
Most of this file is guidance for working in `enterprise_rag`; office-agent-specific rules are
called out in §3.

**Stack:** LangGraph, LangChain, OpenAI (`gpt-5-mini`, `OpenAIEmbeddings`), Chroma (vector
store), Tavily (web search). Managed with **uv**.

**High-level flow** (see `structure.md` for details):

```
question
→ route_question
    ├── websearch → generate
    └── retrieve → grade_documents
            ├── relevant docs → generate
            └── no relevant docs → websearch → generate
generate
→ grounding check (hallucination_grader)
    ├── not grounded → add grounding feedback → regenerate
    └── grounded → usefulness check (answer_grader)
            ├── useful → END
            └── not useful → rewrite search query → websearch
```

Three quality gates: **document relevance**, **answer grounding** (anti-hallucination), and
**answer usefulness**. A `retries` counter in state caps the regenerate/websearch loop at
`MAX_RETRIES = 5` (defined in `enterprise_rag/graph/graph.py`).

External dependency failures (retriever, Tavily, generation LLM, graders, query rewriter)
never crash the graph: each call site catches the exception, degrades or stops safely, and
records a `stop_reason` (`retrieval_error`, `web_search_error`, `generation_error`,
`tool_error`) so `main.py` appends an honest caveat. Console banners log only the exception
type, never the message.

## 2. Project Structure

| Path | Purpose |
|------|---------|
| `main.py` | CLI entry point. Loads `.env`, then runs an interactive Q&A loop over `enterprise_rag.graph.engine.answer_question()`. Re-exports the `enterprise_rag/graph/formatting.py` names (`format_answer`, `format_sources`, caveat notes) for backward compatibility. |
| `enterprise_rag/__init__.py` | Package marker + docstring for the RAG engine. No clients, no side effects. |
| `enterprise_rag/README.md` | Module-level documentation: detailed engine setup, usage, privacy mode, fallback policy, programmatic API, budgets, and failure handling (the content that used to dominate the root README). |
| `office_agent/` | The **Enterprise Office Agent** (v1 + v1.5 Meeting Agent). Deterministic keyword router (`router.py`), `answer_office_request()` entry point (`engine.py`), typed intent constants + `ToolResult` schemas (`schemas.py`), unsupported-intent + presentation (`formatting.py`), and `tools/` — `knowledge` (thin `enterprise_rag` adapter) plus `email`, `calendar`, `tickets`, `briefing`, `meeting` (local mock-data tools). Local-only and LLM-free except the Knowledge Q&A adapter; mock data in `mock_data/` is read-only and anchored to the data (not the system clock). Must never regress `enterprise_rag`. See `docs/office-agent-v1-demo.md` and ADR 015. |
| `enterprise_rag/graph/engine.py` | Canonical programmatic API: `answer_question(question, options) -> AnswerResult`, `AnswerOptions` (per-run `web_search_enabled` / `web_fallback_policy` / `run_id` / `trace_path` overrides; `None` = env default), and `seed_state()` — the single state-seeding helper shared by CLI, evals, and tests. Also owns the lightweight observability: every run gets a `run_id`, the executed `node_path` + per-step timings + `total_duration_ms` are collected by streaming graph updates (additive — merging the updates reproduces `invoke()`), and `trace_path` optionally writes a metadata-only trace JSON (never `page_content`, prompts, raw state, or keys). |
| `enterprise_rag/graph/formatting.py` | Shared presentation: `stop_reason` caveats (`STOP_REASON_NOTES`) plus the deterministic `Sources:` section built from `Document` metadata (`format_answer` / `format_sources` / `source_lines`; local corpus vs. `web_search` supplement). Pure — no clients, no env reads. |
| `enterprise_rag/ingestion.py` | Builds the knowledge base: loads the local Markdown corpus from `enterprise_rag/data/acmecorp_internal_docs/`, splits, embeds, persists to Chroma (idempotent: collection reset + deterministic chunk ids; provenance metadata `source`/`title`/`source_type`/`document_category`). Exposes `get_retriever()` (lazy, `@lru_cache`). Run once before `main.py`. |
| `enterprise_rag/data/acmecorp_internal_docs/` | Synthetic AcmeCorp enterprise corpus: 6 fictional internal Markdown documents (VPN, expenses, incident response, on-call, data retention, onboarding). No real company data — safe to edit/extend. |
| `enterprise_rag/graph/graph.py` | Assembles the LangGraph `StateGraph`, wires nodes + conditional edges, exports compiled `app`. Holds `MAX_RETRIES` and the routing decision functions. |
| `enterprise_rag/graph/state.py` | `GraphState` TypedDict: `question`, `documents`, `generation`, `web_search`, `web_search_enabled`, `web_fallback_policy` (resolved per run by the engine; graph decisions read it from state), `retries`, `stop_reason`, `insufficient_context`, `retry_feedback`, `search_query`, plus budget counters (`llm_call_count`, `web_search_count`, `web_result_grading_count`). |
| `enterprise_rag/graph/config.py` | Env-driven runtime flags: `web_search_enabled()` (privacy mode), `web_fallback_policy()` / `normalize_web_fallback_policy()` (conservative/aggressive/disabled, default conservative; the env var is the *default source* — the engine resolves the effective policy into per-run state), and the per-run budgets `max_llm_calls_per_run()` / `max_web_searches_per_run()` / `max_web_results_to_grade()`. |
| `enterprise_rag/graph/consts.py` | Node-name string constants (`RETRIEVE`, `GRADE_DOCUMENTS`, `GENERATE`, `WEBSEARCH`, `WEB_SEARCH_DISABLED_NOTICE`) and `stop_reason` values. |
| `enterprise_rag/graph/nodes/` | Graph node functions: `retrieve`, `grade_documents`, `generate`, `web_search`, retry helpers (`add_grounding_feedback`, `rewrite_query`), plus terminal notice nodes (`web_search_disabled_notice`, `web_fallback_disabled_notice`, `max_retries_not_grounded_notice`, `max_retries_not_useful_notice`, `budget_exhausted_notice`, `tool_error_notice`) that record `stop_reason`, and `clear_transient_tool_error` (success-path pass-through: clears a stale transient `tool_error` once both gates pass). |
| `enterprise_rag/graph/chains/` | LCEL chains: `generation`, `retrieval_grader`, `question_router`, `hallucination_grader`, `answer_grader`, `query_rewriter`. Each exposes a lazy `get_*()` factory. |
| `tests/node/` | Unit tests for node functions. Fully mocked — no API keys needed. |
| `tests/graph/` | Routing / privacy-toggle / compiled-graph tests. Fully mocked — no API keys needed. |
| `tests/chains/` | Integration tests for the chains. Call the real `gpt-5-mini` — need `OPENAI_API_KEY`. |
| `tests/evals/` | Mocked unit tests for the eval harness's pure helpers (validation, checks, metrics, rendering). No API keys needed. |
| `tests/office_agent/` | Unit tests for the Office Agent (router, engine dispatch, and each mock tool). Fully mocked / deterministic — no OpenAI, Tavily, Chroma, or external services; no `enterprise_rag` graph call (the knowledge adapter is patched). No API keys needed. |
| `evals/` | Behavioral eval harness: `questions.jsonl` (24-row dataset with multi-document and fallback-policy rows; optional per-row `web_fallback_policy`, source-title, min-local-source, and web-search-count checks), `run_eval.py` (runs the real graph via `enterprise_rag.graph.engine.answer_question()` — **never run the full eval without explicit approval**; `--validate-only` is safe), `results.md` (generated report). Each full run also writes a metadata-only JSON history record and renders a "Delta vs. previous run" section in the report. Not part of CI. |
| `evals/history/` | Append-only, metadata-only eval history records (one JSON per full run; never answer text, `page_content`, prompts, or raw state). The harness only writes new records — never edits/deletes. `evals/history/*.json` is gitignored by default (the dir is tracked via `.gitkeep`); force-add (`git add -f`) to share a known-good baseline. |
| `docs/adr/` | Architecture Decision Records (001–011) with an index in `docs/adr/README.md`. When a documented decision changes, update or supersede the matching ADR. |
| `docs/roadmap/` | Tracked process artifacts (see `docs/roadmap/README.md`): `spec/`, `plan/`, `implementation/`, `commands-review/`, plus per-topic `<topic>-review/` dirs (e.g. `architecture-review/`, `security-review/`, `failure-modes-review/`, `test-coverage-review/`). Specs/plans/reports use a short feature slug. `docs/roadmap/<topic>-review/` is the convention for timestamped reports from project-level `<topic>-review` commands (architecture, security, failure-modes, test-coverage); these use dated `<YYYY-MM-DD>-<focus-slug>-<topic>-review.md` collision-safe filenames and must not overwrite prior reports. `docs/roadmap/commands-review/` remains for command-file review reports (e.g. `/review-command`). |
| `.claude/commands/` | Claude Code slash-command workflow files (spec → plan → implement → review-diff; plus `arch-review`, command-authoring/review, and `update-claude-md`). Each has YAML frontmatter (`description`, `argument-hint`, `allowed-tools`); keep `allowed-tools` minimal and scoped (e.g. `Bash(git status:*)`, not blanket `Bash`). |
| `tests/conftest.py` | Loads `.env` before collection; provides the `requires_openai` skip marker. |
| `pyproject.toml` | uv project config: deps, `[dependency-groups] dev` (pytest, ruff, mypy, pre-commit), `[tool.pytest.ini_options]`, `[tool.ruff]`/`[tool.ruff.lint]`/`[tool.ruff.lint.per-file-ignores]`, and `[tool.mypy]`/`[[tool.mypy.overrides]]`. |
| `.gitattributes` | Line-ending policy: `text=auto` + explicit `*.py/md/yml/yaml/toml/json text` rules to prevent CRLF churn on Windows working copies. |
| `.pre-commit-config.yaml` | Local hooks mirroring CI: `ruff-check --fix`, `ruff-format`, and basic hygiene hooks (`trailing-whitespace`, `end-of-file-fixer`, `check-yaml`, `check-toml`, `check-added-large-files`, `check-merge-conflict`). |

## 3. Development Rules

- **Preserve behavior by default.** Do not change graph routing, `GraphState` schema, prompts,
  model names (`gpt-5-mini`), `temperature=0`, chain input variables, or node return
  structures unless explicitly asked.
- **No broad architecture changes.** Avoid restructuring the graph or rewriting modules wholesale.
- **`GraphState` fields are plain last-value channels.** Do not add `typing.Annotated` reducers /
  accumulating channels: `enterprise_rag/graph/engine.py` merges streamed node updates with `dict.update()`, which
  only reproduces `app.invoke()` for last-value channels. If a reducer is ever needed, revisit that merge first.
- **Refactors should be small, mechanical, and reviewable.** Prefer minimal diffs.
- **Lazy external clients (required pattern).** `ChatOpenAI`, `OpenAIEmbeddings`,
  `TavilySearch` (`langchain-tavily`), `Chroma`, retrievers, and any API-backed tool must be constructed
  inside a lazy factory — use `@lru_cache(maxsize=1) def get_x(): ...` — never at module level.
- **Imports must be side-effect-free.** Importing any module (`enterprise_rag.graph.graph`, `enterprise_rag.graph.nodes.*`,
  `enterprise_rag.graph.chains.*`, `ingestion`) must NOT require API keys or network, and must NOT construct
  any external client.
- **Backward-compatible chain names.** Chain modules expose `get_*()` factories; old
  module-level names (e.g. `generation_chain`, `question_router`) remain available via a lazy
  module-level `__getattr__`. Don't reintroduce eager module-level chain objects.
- Code comments/docstrings are written in **English**.
- **`office_agent/` working rules.** The Office Agent is deterministic and local by design —
  keep it that way unless a task explicitly says otherwise:
  - **No LLM routing.** Classify intents with the existing keyword router + intent constants /
    typed schemas (`schemas.py`); do not introduce an LLM router.
  - **Knowledge Q&A goes through the existing adapter over `enterprise_rag`** — never duplicate
    retrieval/generation/graph logic inside `office_agent`.
  - **Mock tools stay local-only and deterministic.** Read `office_agent/mock_data/` as
    **read-only** and anchor dates to the data, **not the system clock**. **No external
    integrations** (Gmail, Google/Outlook Calendar, Slack, Jira, Linear, Asana, Trello) unless
    explicitly requested.
  - Tools return a `ToolResult`; `answer_office_request(user_input)` is the single entry point.
  - Same discipline as `enterprise_rag`: **side-effect-free imports**, lazy data/client access.
  - **`office_agent` tests stay fully mocked / CI-safe** — no OpenAI, Tavily, Chroma, or external
    services, and no real `enterprise_rag` graph call (patch the knowledge adapter).

## 4. Testing Rules

- **Unit tests mock all external dependencies** via `monkeypatch`, targeting the lazy seam
  (e.g. patch `get_node_retriever`, `get_web_search_tool`, `get_retrieval_grader`,
  `generate_answer`).
- **Node tests (`tests/node/`) must never call real OpenAI, Tavily, Chroma, or embeddings.**
  They must pass with no API keys.
- **Integration tests (`tests/chains/`) call real services** and require `OPENAI_API_KEY`.
  Label such tests clearly and gate them with the `requires_openai` marker from `conftest.py`.
- **Do not run tests unless explicitly asked.** Writing tests ≠ running them.

## 5. Claude Code Behavior Rules

- **Plan first.** Before changing files, explain the plan and list every file to be changed and why.
- **Summarize after.** After editing, provide a diff summary.
- **Don't run commands without explicit approval** — no `pytest`, `python -c`, `py_compile`, or
  any code-executing command unless the user asks. Provide commands for the user to run instead.
- **Stop and ask** before any change that may affect business logic, graph routing, prompt
  behavior, model behavior, or the state schema.
- **Tests-only tasks:** when the request is only to write tests, prefer asking before touching
  production code; make the smallest safe change if a seam is genuinely needed for testability.

## 6. Common Commands

> These are for **the user to run manually**. Claude Code should not execute them without approval.

```powershell
# Always work from the project root
cd "<your-local-repo-path>"

# Set up the environment (creates .venv, writes uv.lock)
uv sync --group dev

# Install local pre-commit hooks (one-time per clone)
uv run pre-commit install

# Build the Chroma index (one-time, before first run)
uv run python -m enterprise_rag.ingestion

# Run the assistant
uv run python main.py

# Node unit tests — fully mocked, NO API keys required
uv run pytest tests/node/ -v

# Chain integration tests — real gpt-5-mini, needs OPENAI_API_KEY
uv run pytest tests/chains/ -v

# Whole suite
uv run pytest -v

# Dev hygiene (mirrors the CI lint job — run before committing)
uv run ruff check .                  # lint
uv run ruff check --fix .            # lint + safe autofixes
uv run ruff format .                 # format
uv run ruff format --check .         # format check (CI mode)
uv run mypy                          # type-check scoped modules only

# Run all pre-commit hooks across every file (equivalent to what runs on commit)
uv run pre-commit run --all-files

# Syntax-only check (no test execution)
$files = @(
    "enterprise_rag/graph/graph.py",
    "enterprise_rag/graph/nodes/generate.py",
    "enterprise_rag/graph/nodes/retrieve.py",
    "enterprise_rag/graph/nodes/web_search.py",
    "enterprise_rag/graph/nodes/grade_documents.py",
    "enterprise_rag/graph/chains/generation.py",
    "enterprise_rag/graph/chains/retrieval_grader.py",
    "enterprise_rag/graph/chains/question_router.py",
    "enterprise_rag/graph/chains/hallucination_grader.py",
    "enterprise_rag/graph/chains/answer_grader.py",
    "enterprise_rag/ingestion.py",
    "main.py"
)

uv run python -m py_compile $files

# Verify imports construct no clients and need no keys
uv run python -c "import enterprise_rag.graph.graph, enterprise_rag.graph.nodes, enterprise_rag.graph.chains, ingestion; print('IMPORT OK')"
```
