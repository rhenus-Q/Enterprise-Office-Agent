# Agentic RAG Assistant

[![CI](https://github.com/rhenusbeichenGit/Agentic_RAG/actions/workflows/ci.yml/badge.svg)](https://github.com/rhenusbeichenGit/Agentic_RAG/actions/workflows/ci.yml)

**A self-correcting, enterprise-style document Q&A assistant built with LangGraph (CRAG pattern).**

## Overview

This project implements an internal-document Q&A assistant as an **agentic RAG workflow**: instead of a single retrieve-then-generate pass, the system routes each question to the best data source, grades the relevance of every retrieved document, checks each generated answer for hallucinations and usefulness, and automatically falls back to web search or regenerates when a quality gate fails. The graph is a LangGraph `StateGraph` with explicit conditional edges, a bounded retry loop, and three independent LLM quality gates — a practical implementation of the **Corrective RAG (CRAG)** pattern.

The knowledge base is a **synthetic enterprise corpus**: six fictional AcmeCorp internal documents (VPN access policy, expense reimbursement policy, security incident response playbook, on-call & escalation policy, data retention policy, employee onboarding guide) under [`data/acmecorp_internal_docs/`](data/acmecorp_internal_docs/). The documents are entirely fictional — no real company data — but written with realistic structure (effective dates, owners, thresholds, SLAs, escalation paths, exceptions), so privacy mode, provenance, and the quality gates operate on enterprise-shaped content rather than tutorial pages.

## Key Features

- **Question routing** — an LLM router sends knowledge-base questions to vector retrieval and out-of-scope questions straight to web search.
- **Three quality gates**, each an independent structured-output LLM grader:
  1. **Document relevance** — irrelevant retrieved chunks are filtered out before generation, and external web results must pass the *same* relevance gate before they're added to the context (untrusted sources don't get a free pass).
  2. **Answer grounding (anti-hallucination)** — answers not supported by the documents are regenerated.
  3. **Answer usefulness** — grounded but off-target answers trigger a web-search supplement.
- **Web search fallback** via Tavily when the local knowledge base isn't sufficient.
- **Privacy mode** — a `WEB_SEARCH_ENABLED=false` toggle disables every web-search path (routing, fallback, and supplement), so user questions never leave the local environment.
- **Bounded self-correction with honest failure reporting** — a `retries` counter in graph state caps the regenerate/web-search loop (`MAX_RETRIES = 5`), the final allowed generation is still fully graded before the protective stop, and if it still fails a gate the answer is delivered with an explicit warning instead of being presented as successful.
- **Meaningful retries** — each retry changes the input instead of replaying it at `temperature=0`: a failed grounding check injects a corrective instruction into the next generation, and a failed usefulness check rewrites the web-search query (with the fresh web supplement *replacing* the stale one, not stacking duplicates).
- **Per-run cost budget** — counted LLM calls, web searches, and web-result grades are tracked in state and capped by env-configurable budgets; an exhausted budget stops the run safely with an explicit caveat instead of spending indefinitely.
- **Graceful degradation on external failures** — a failing dependency (Chroma retriever, Tavily, the generation LLM, any grader, the query rewriter) never crashes the graph: the run degrades (web fallback, local-only answer, original-question search) or stops safely, records a machine-readable `stop_reason`, and the CLI appends an honest caveat. Ungraded content is never trusted, and an answer whose verification failed is never presented as verified.
- **Answer provenance** — every answer built from documents ends with a deterministic `Sources:` section distinguishing local corpus documents (by title or URL) from the web-search supplement. Web provenance is **page-level**: each relevant result's title and URL are preserved and cited (`Web search: <title> — <url>`), falling back to the query-level citation when Tavily returns no URLs. Formatting is metadata-only after the graph finishes — no LLM-generated citations, no prompt changes, no document content exposed.
- **Side-effect-free imports** — every external client (`ChatOpenAI`, `OpenAIEmbeddings`, `Chroma`, Tavily) is built inside a lazy `@lru_cache` factory. Importing any module requires no API keys and no network, which makes the whole graph unit-testable with plain `monkeypatch`.
- **Two-tier test suite** — fully mocked node tests that run with zero API keys, plus clearly separated integration tests against the real model.

## Architecture

```mermaid
flowchart TD
    Q([User question]) --> ROUTE{route_question}

    ROUTE -- "websearch" --> WS[websearch<br/>Tavily]
    ROUTE -- "retrieve" --> RET[retrieve<br/>Chroma, k=3]

    RET --> GD[grade_documents<br/>relevance gate]
    GD -- "relevant docs remain" --> GEN[generate<br/>gpt-5-mini]
    GD -- "no relevant docs<br/>(policy-dependent)" --> WS
    WS --> GEN

    GEN --> HG{grounding gate<br/>hallucination_grader}
    HG -- "not grounded" --> FB[add_grounding_feedback<br/>corrective instruction]
    FB --> GEN
    HG -- "grounded" --> AG{usefulness gate<br/>answer_grader}
    AG -- "useful" --> E([END])
    AG -- "not useful" --> RW[rewrite_query<br/>more specific search]
    RW --> WS
    HG -. "max retries" .-> E
    AG -. "max retries" .-> E
```

### LangGraph workflow, step by step

1. **`route_question`** (conditional entry point) — a structured-output router (`datasource: "retrieve" | "websearch"`) decides whether the question is covered by the ingested knowledge base or needs external/current information.
2. **`retrieve`** — top-3 similarity search against a persisted Chroma vector store.
3. **`grade_documents`** — each chunk is graded individually (`is_relevant: bool`); irrelevant chunks are dropped, and any failure sets a `web_search` flag. What happens next is governed by `WEB_FALLBACK_POLICY` (see below): by default (**conservative**) the flow generates from the remaining relevant chunks and only detours through Tavily when *no* relevant chunk survives; `aggressive` restores the legacy any-irrelevant-chunk-triggers-web behavior; `disabled` keeps local retrieval paths local entirely.
4. **`websearch`** — searches with the rewritten `search_query` on retry rounds (original question otherwise). Each Tavily result is individually graded for relevance against the *original* question (reusing the retrieval grader, so external content faces the same gate as internal chunks); only relevant results are merged into a single `Document` (tagged `source: web_search`, with each contributing page's title/URL kept in `web_sources` metadata for the Sources section), which **replaces** any previous web supplement instead of stacking duplicates. Malformed responses and irrelevant results are dropped defensively — if nothing usable comes back, the workflow continues with the existing documents.
5. **`generate`** — answers strictly from the provided context; with an empty context it returns a deterministic "not enough information" response without calling the LLM and flags it via `insufficient_context` in state. Each pass increments `retries`.
6. **`grade_generation`** (conditional edge) — two-layer check with eleven explicit outcomes:
   - `insufficient_context` → the generation is the deterministic insufficient-context answer (no usable documents); both graders are skipped — there is nothing to verify and regenerating from the same empty context cannot help — and the run ends honestly on the first pass (in privacy mode via the `web_search_disabled` notice, so the caveat explains why no information could be added),
   - `not_grounded` → `add_grounding_feedback` injects a corrective instruction into the next generation, then regenerate,
   - `useful` → END,
   - `not_useful` → `rewrite_query` produces a more specific search query, then web search and regenerate,
   - `web_search_disabled` → terminal notice node (privacy mode; see below),
   - `web_fallback_disabled` → terminal notice node (`WEB_FALLBACK_POLICY=disabled` blocked a local-only run's not-useful web retry; see below),
   - `max_retries_not_grounded` / `max_retries_not_useful` → terminal notice nodes recording which quality gate the final answer failed (the limit is checked *after* grading, so even the last generation gets a full quality check, and a failed answer is never presented as a normal one),
   - `budget_exhausted` → the per-run cost budget is spent; terminal notice node, the answer goes out with an explicit caveat,
   - `generation_error` → the generation LLM call itself failed; the run ends immediately with a safe placeholder answer, never graded,
   - `tool_error` → a grader call failed; the run ends through a terminal notice node with the answer explicitly flagged as unverified.

State is a `TypedDict` defined in `graph/state.py` with thirteen fields: the working data (`question`, `documents`, `generation`), control flags (`web_search`, `web_search_enabled`, `insufficient_context`), the retry machinery (`retries`, `stop_reason`, `retry_feedback`, `search_query`), and the per-run budget counters (`llm_call_count`, `web_search_count`, `web_result_grading_count`). See [structure.md](structure.md) §3 for the full field-by-field table.

## Tech Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph (`StateGraph`, conditional edges) |
| LLM | OpenAI `gpt-5-mini` (router, graders, generation — all structured output via Pydantic) |
| Embeddings | `OpenAIEmbeddings` |
| Vector store | Chroma (local persistence) |
| Web search | Tavily (`langchain-tavily`) |
| Chains | LangChain LCEL |
| Package management | uv (`pyproject.toml` + committed `uv.lock`) |
| Testing | pytest (mocked unit tests + key-gated integration tests) |

## Project Structure

```
.
├── main.py                  # CLI entry point: interactive Q&A loop over the compiled graph
├── ingestion.py             # KB build: load local Markdown corpus → split → embed → persist to Chroma (idempotent)
├── data/
│   └── acmecorp_internal_docs/  # Synthetic AcmeCorp corpus: 6 fictional internal policy/guide documents
├── structure.md             # Architecture deep-dive: full workflow, state machine, design decisions
├── docs/
│   └── adr/                 # Architecture Decision Records 001–011 (with index in README.md)
├── evals/
│   ├── questions.jsonl      # Behavioral eval dataset (24 rows, 6 categories)
│   ├── run_eval.py          # Eval runner: real graph runs + deterministic checks (not in CI)
│   └── results.md           # Generated eval report
├── .github/
│   └── workflows/ci.yml     # CI: runs the fully mocked suites (node, graph, evals) — no API keys
├── graph/
│   ├── graph.py             # StateGraph assembly, routing/decision functions, MAX_RETRIES, compiled `app`
│   ├── engine.py            # Canonical engine API: answer_question(), AnswerOptions/AnswerResult, seed_state(),
│   │                        #   lightweight observability (run_id, node path, timings, optional trace JSON)
│   ├── formatting.py        # Shared presentation: stop-reason caveats + deterministic Sources section
│   ├── state.py             # GraphState TypedDict
│   ├── config.py            # Env-driven runtime flags: WEB_SEARCH_ENABLED, WEB_FALLBACK_POLICY,
│   │                        #   per-run budgets (MAX_LLM_CALLS_PER_RUN, MAX_WEB_SEARCHES_PER_RUN, MAX_WEB_RESULTS_TO_GRADE)
│   ├── consts.py            # Node-name constants and stop_reason values
│   ├── nodes/               # retrieve, grade_documents, generate, web_search,
│   │                        #   retry helpers (add_grounding_feedback, rewrite_query),
│   │                        #   terminal notice nodes (stop_reason recorders)
│   └── chains/              # LCEL chains: generation, retrieval_grader, question_router,
│                            #   hallucination_grader, answer_grader, query_rewriter
│                            #   (each behind a lazy get_*() factory)
└── tests/
    ├── conftest.py          # Loads .env; provides the `requires_openai` skip marker
    ├── node/                # Unit tests — all external dependencies mocked, no API keys needed
    ├── graph/               # Routing / privacy-toggle / compiled-graph tests — fully mocked
    ├── evals/               # Unit tests for the eval harness's pure helpers — fully mocked
    └── chains/              # Integration tests — call the real gpt-5-mini, need OPENAI_API_KEY
```

## Setup

Requires **Python ≥ 3.11** and [uv](https://docs.astral.sh/uv/).

```powershell
# 1. Clone and enter the project
git clone <repo-url>
cd Agentic_RAG_Claude

# 2. Install dependencies (creates .venv from the committed uv.lock)
uv sync --group dev

# 3. Configure environment variables
Copy-Item .env.example .env   # then edit .env and add your keys
```

### Environment variables

See [`.env.example`](.env.example) for the full template:

| Variable | Required | Used for |
|---|---|---|
| `OPENAI_API_KEY` | Yes | Chat models (router, graders, generation) and embeddings |
| `TAVILY_API_KEY` | Yes | Web-search fallback node |
| `WEB_SEARCH_ENABLED` | Optional (default `true`) | Set to `false` to disable all external web search (privacy mode) |
| `WEB_FALLBACK_POLICY` | Optional (default `conservative`) | `conservative` / `aggressive` / `disabled` — when document grading falls back to web search (see below) |
| `MAX_LLM_CALLS_PER_RUN`, `MAX_WEB_SEARCHES_PER_RUN`, `MAX_WEB_RESULTS_TO_GRADE` | Optional (defaults `30` / `5` / `15`) | Per-run cost/latency budgets (see below) |
| `LANGCHAIN_TRACING_V2`, `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT` | Optional | LangSmith tracing of the correction loops |

`.env` is gitignored; only `.env.example` is committed.

### Privacy mode (`WEB_SEARCH_ENABLED=false`)

In enterprise or compliance-sensitive deployments, sending user questions to an
external search API is a data-leak risk: every routed or fallback web search
transmits the question text to a third-party service. Setting
`WEB_SEARCH_ENABLED=false` guarantees questions never leave the local environment:

- The entry router never sends a question to web search — everything goes to vector retrieval (the router LLM call is skipped entirely on this path).
- If retrieved documents are graded irrelevant, the workflow generates from whatever relevant documents remain instead of searching the web; with none left, it returns the deterministic *"I do not have enough information in the provided documents."* answer rather than fabricating one.
- A grounded-but-off-target answer ends the run with the grounded answer instead of triggering a web-search supplement. In that case the workflow records a `stop_reason` in its state, and the CLI appends an explicit caveat to the answer so the limitation is never silent:

  > *Note: Web search is disabled, so I could only use the local knowledge base. I may not have enough information to fully answer this question.*

  The caveat appears **only** when web search is disabled *and* the workflow would otherwise have needed it — successful local answers are printed without any warning, in both modes.

All grounding and usefulness quality gates remain active in privacy mode, with
one principled exception in both modes: the deterministic insufficient-context
answer skips the graders entirely — it contains no claims to verify, and
regenerating from the same empty context cannot improve it. The default
(variable unset or any value other than `false`/`0`/`no`/`off`) preserves the
full web-search behavior.

### Web fallback policy (`WEB_FALLBACK_POLICY`)

Distinct from the privacy switch: `WEB_SEARCH_ENABLED=false` decides whether
external web search is allowed *at all* (and overrides everything below);
`WEB_FALLBACK_POLICY` decides *when* the system chooses retrieval-triggered
fallback while web search is otherwise allowed.

- **`conservative` (default)** — answer from the curated corpus first: if at
  least one relevant local document survives grading, generate from it; fall
  back to web search only when nothing relevant remains. A grounded local
  answer that later fails the usefulness gate can still trigger a rewritten
  web search.
- **`aggressive`** — legacy CRAG behavior: any irrelevant retrieved document
  triggers web fallback before generation. Better first-pass coverage for
  sparse corpora, at the cost of sending more questions to an external
  service.
- **`disabled`** — local retrieval paths never escalate to the web, including
  the post-generation not-useful retry on runs that have stayed local (those
  end with an explicit caveat via the `web_fallback_disabled` stop reason).
  Router-chosen web searches still work when web search is enabled. With no
  relevant local documents the assistant declines honestly instead of
  searching.

Invalid values fall back to `conservative`. The environment variable is the
*default* source only: the engine resolves the effective policy into per-run
graph state at run start, so callers (evals, tests, future automation) can
pass a different policy per run without touching the environment. Rationale
and trade-offs: [ADR 011](docs/adr/011-web-fallback-policy.md).

### Programmatic engine API

The CLI, the eval harness, and tests all run questions through the same
entry point, `graph.engine.answer_question()` — state seeding and per-run
config resolution live in one place:

```python
from graph.engine import AnswerOptions, answer_question

result = answer_question(
    "How do I request VPN access?",
    AnswerOptions(web_search_enabled=True, web_fallback_policy="conservative"),
)
result.answer                  # raw generation
result.stop_reason             # "" = clean finish
result.sources                 # deduplicated citation lines
result.tracked_llm_calls       # budgeted operational counter (not total LLM usage)
result.web_fallback_policy     # the policy this run actually used
result.raw_state               # full final GraphState for internal callers
result.run_id                  # always set: preserved if provided, generated otherwise
result.node_path               # executed nodes in order, e.g. ["retrieve", "grade_documents", ...]
result.node_timings_ms         # one {"node", "duration_ms"} entry per step (approximate)
result.total_duration_ms       # wall-clock duration of the whole graph run
```

Options left as `None` fall back to the environment defaults
(`WEB_SEARCH_ENABLED` / `WEB_FALLBACK_POLICY`). The hard privacy guarantee is
unchanged: `web_search_enabled=False` — per run or via the environment —
means zero external web searches regardless of the fallback policy.

#### Run traces (optional, metadata-only)

Every run carries lightweight observability: a `run_id`, the executed node
path, per-step timings, and the total duration, collected centrally in the
engine by streaming the graph's node updates — no node or routing changes.
Pass `trace_path` to also write a trace JSON file:

```python
from graph.engine import AnswerOptions, answer_question

result = answer_question(
    "How do I request VPN access?",
    AnswerOptions(run_id="demo-1", trace_path="traces/demo-1.json"),
)
```

The trace contains `run_id`, `generated_at`, `question`, `node_path`,
`total_duration_ms`, `node_timings_ms`, `stop_reason`, the run counters
(`retries`, `tracked_llm_calls`, `web_search_count`,
`web_result_grading_count`), `web_search_enabled`, `web_fallback_policy`,
and the citation lines (`sources`). It deliberately **never** contains
document `page_content`, prompts, raw graph state, or API keys. By default
(`trace_path=None`) no file is written. Note that the question text itself
is part of the trace — store trace files accordingly.

### Retry-exhaustion warnings

The self-correction loop is capped at `MAX_RETRIES = 5` generations. The limit is
checked *after* grading, so even the final generation gets a full quality check —
and if it still fails, the workflow records which gate failed in `stop_reason`
and the CLI appends an explicit warning instead of presenting the answer as
successful:

- **Still not grounded** (`max_retries_not_grounded`):

  > *Warning: This answer did not pass the grounding (anti-hallucination) check after the retry limit was reached. It may contain information that is not supported by the source documents, so do not treat it as fully reliable.*

- **Grounded but still not useful** (`max_retries_not_useful`):

  > *Warning: This answer did not pass the usefulness check after the retry limit was reached. It is grounded in the source documents but may not fully answer your question.*

Answers that pass both gates are printed without any warning, exactly as before.

### Per-run cost / latency budget

Each graph run tracks its spend in state: `llm_call_count` (generations, query
rewrites, web-result grading calls), `web_search_count` (Tavily searches), and
`web_result_grading_count`. Three env-configurable budgets cap them:

- `MAX_LLM_CALLS_PER_RUN` (default 30) — checked *before* each post-generation
  grading round; once spent, the run stops immediately through a
  `budget_exhausted` stop reason rather than spending more.
- `MAX_WEB_SEARCHES_PER_RUN` (default 5) — a spent search budget stops the
  "not useful" retry loop (looping toward a search that can't run is waste)
  and defensively skips any search the node is still asked to perform.
- `MAX_WEB_RESULTS_TO_GRADE` (default 15) — once spent, remaining web results
  are dropped *ungraded and unused* (conservative: unvetted content never
  reaches generation); the run itself continues.

When a budget ends the run, the CLI appends:

> *Note: This answer stopped because the per-run cost/latency budget was reached. The answer may be incomplete or not fully verified.*

The defaults are deliberately sized above the worst case the `MAX_RETRIES`
loop can produce, so default behavior is unchanged — the budgets exist as a
hard cost backstop and for tightening in cost-sensitive deployments.

**`llm_call_count` is a tracked operational counter, not total LLM usage.**
Router calls, local-chunk relevance grading, and the hallucination/answer
graders are not individually counted (the graders run inside a pure
conditional edge and are bounded at two per generation, so capping counted
calls transitively caps them). The counter therefore understates real API
usage by a bounded factor — fine for a budget backstop and relative
observability, **not** billing-accurate cost accounting. True cost accounting
would use tracing/token usage (e.g. LangSmith) rather than manual counters.

### External dependency failure handling

A failing external dependency never crashes the graph. Each failure is caught
at its call site, logged by category only (exception type, never messages that
could carry secrets), recorded as a `stop_reason`, and surfaced to the user as
a caveat appended by the CLI:

| Failure | Behavior | `stop_reason` |
|---|---|---|
| Chroma retriever | Degrade to web-search fallback (or the deterministic insufficient-context answer in privacy mode) | `retrieval_error` |
| Tavily search | Continue with local documents only; the failed attempt still counts against the web-search budget | `web_search_error` |
| Generation LLM | Stop immediately with a safe placeholder answer — the failed generation is never graded or presented as normal | `generation_error` |
| Query rewriter | Fall back to searching with the original question; the retry loop continues fully gated | `tool_error` |
| Relevance grader (local chunk or web result) | Drop the ungraded content — unvetted content never reaches generation; the rest continues | `tool_error` |
| Hallucination / answer grader | Stop and deliver the answer explicitly flagged as unverified | `tool_error` |

Degraded runs keep their `stop_reason` to the end with one deliberate
exception: a *transient* `tool_error` (a dropped chunk/result or a failed
query rewrite — situations the run is built to recover from) is cleared when
the final answer subsequently passes **both** quality gates, so a fully
successful answer never ships with an error caveat. Whole-source degradations
(`retrieval_error`, `web_search_error`) persist even on success, and the
terminal `tool_error` (verification itself failed) is always kept. All
privacy-mode guarantees, budgets, and retry limits remain in force on every
failure path.

## Build the knowledge base (ingestion)

Run once before first use (and again whenever the corpus changes):

```powershell
uv run python ingestion.py
```

This loads the Markdown documents from `data/acmecorp_internal_docs/`, splits them into 1000-character chunks (200 overlap), embeds them, and persists a Chroma collection to `chroma_db/` (gitignored). Ingestion is **idempotent**: the existing collection is dropped and rebuilt with deterministic chunk ids, so re-running never duplicates chunks (tradeoff: a run that fails mid-ingestion leaves the index empty until re-run).

### The synthetic AcmeCorp corpus

The corpus is six fictional internal documents — created for this project, containing no real company data or copyrighted policies:

| Document | Category | Sample question it answers |
|---|---|---|
| `vpn_policy.md` | it_security | "How do I request VPN access?" |
| `expense_reimbursement_policy.md` | finance | "What expenses require manager approval?" |
| `incident_response_playbook.md` | it_security | "When should a security incident be escalated to Sev-1?" |
| `on_call_escalation_policy.md` | operations | "Who gets paged for after-hours production incidents?" |
| `data_retention_policy.md` | compliance | "How long are audit logs retained?" |
| `employee_onboarding_guide.md` | hr | "What should a new employee do during their first week?" |

Each document has an effective date, a policy owner, concrete rules (approval thresholds, ack SLAs, retention periods), escalation paths, an exceptions process, and contacts; documents cross-reference each other so multi-document questions retrieve coherently, with eval rows now checking multi-document provenance. Every document carries provenance metadata (`source`, `title`, `source_type: "local_corpus"`, `document_category`) that survives chunking and feeds the `Sources:` section. To use your own documents, drop Markdown files into the corpus folder (and optionally extend `DOCUMENT_CATEGORIES` in `ingestion.py`), then re-run ingestion.

## Run the assistant

```powershell
uv run python main.py
```

```
Enterprise Knowledge Assistant
Type 'exit' to quit.

Enter your question:
> How do I request VPN access?
```

Node-by-node progress banners (`---RETRIEVE---`, `---CHECK HALLUCINATIONS---`, …) show the graph's path, including any correction loops.

### Source citations

Answers built from documents end with a `Sources:` section showing where the
context came from:

```
Answer:
Submit the "VPN Access Request" form in the IT Service Portal; your manager
approves it, and IT Security provisions access within 2 business days ...

Sources:
- Local corpus: AcmeCorp VPN Access Policy
- Web search: AcmeCorp VPN Client Setup Guide — https://example.com/vpn-setup
```

Local corpus documents are cited by their ingestion metadata (page title,
falling back to the source URL). The web supplement is cited **page-level**:
one line per relevant result, `<title> — <url>` (the bare URL when the title
is missing), deduplicated by URL. When Tavily returns no usable URLs the
citation falls back to the search query that produced the supplement
(`Web search: "<query>"`). Only results that passed the relevance gate are
cited — a dropped page is never named. Repeated sources are listed once,
missing metadata falls back to safe generic labels (`Local corpus document` /
`Web search result`), and runs that used no documents show no Sources section
at all. Citations are pure post-run formatting of `Document` metadata — the
LLM is not asked to generate them, so prompts and model behavior are
unchanged. When a run ends with a caveat, the caveat is printed *before* the
sources, so a sources list never implies a failed answer was verified.

## Run the tests

```powershell
# Unit tests — fully mocked, NO API keys required
uv run pytest tests/node/ -v

# Graph routing / privacy-toggle tests — fully mocked, NO API keys required
uv run pytest tests/graph/ -v

# Eval-harness helper tests — fully mocked, NO API keys required
uv run pytest tests/evals/ -v

# Integration tests — call the real gpt-5-mini, require OPENAI_API_KEY (skipped if unset)
uv run pytest tests/chains/ -v

# Whole suite
uv run pytest -v
```

CI ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs two parallel
jobs on every push and pull request — both keys-free:

- **`mocked-tests`**: the three fully mocked suites (`tests/node/`,
  `tests/graph/`, `tests/evals/`), which also doubles as a regression test that
  imports stay side-effect-free.
- **`lint`**: `ruff check`, `ruff format --check`, and `mypy` (scoped to the
  engine-API surface: `graph/engine.py`, `graph/config.py`,
  `graph/formatting.py`, `graph/state.py`, `graph/consts.py`).

The key-gated integration suite (`tests/chains/`) and the full eval run are
deliberately excluded from CI.

## Dev hygiene

Ruff (lint + format), mypy (scoped), and pre-commit hooks are configured in
[`pyproject.toml`](pyproject.toml) and [`.pre-commit-config.yaml`](.pre-commit-config.yaml):

```powershell
# Install local hooks once per clone
uv run pre-commit install

# Lint and format (mirrors the CI lint job)
uv run ruff check .
uv run ruff format --check .
uv run mypy

# Apply safe fixes and format in one pass
uv run ruff check --fix . ; uv run ruff format .

# Run all hooks across every file (same tools as CI)
uv run pre-commit run --all-files
```

Mypy is scoped to the engine-API surface (`graph/engine.py`, `graph/config.py`,
`graph/formatting.py`, `graph/state.py`, `graph/consts.py`); nodes, chains,
tests, and `ingestion.py` are outside scope. Mypy is **not** a pre-commit hook
(hook-venv isolation makes it unreliable for LangChain-typed code); run it
directly or via CI instead.

## Behavioral evals

Beyond code-path tests, [`evals/`](evals/) contains a lightweight behavioral
evaluation harness: 24 realistic questions
([`evals/questions.jsonl`](evals/questions.jsonl)) across six categories —
answerable from the AcmeCorp corpus (5), requiring web fallback (5),
unanswerable without fabricating (3), privacy-mode guarantees (2), multi-document provenance (4), and fallback-policy behavior (5). The
runner drives the real graph and applies **deterministic** checks (stop
reasons, source provenance including required local titles, run counters including web-search-count expectations, expected substrings, and effective fallback-policy echoes — no
LLM-as-judge), then writes a Markdown report to
[`evals/results.md`](evals/results.md):

```powershell
# Validate the dataset format only — no API calls
uv run python evals/run_eval.py --validate-only

# Full eval — real OpenAI/Tavily calls, requires keys (not part of CI)
uv run python evals/run_eval.py
uv run python evals/run_eval.py --limit 3
```

The harness's pure helpers (loading, validation, checks, metrics, rendering)
are unit-tested without API calls in `tests/evals/`. See
[`evals/README.md`](evals/README.md) for the dataset schema and check rules.

## Architecture decision records

The major design decisions — `stop_reason` semantics, privacy mode,
meaningful retries, the web-result relevance gate, run budgets, graceful
degradation, deterministic provenance, the synthetic corpus, the eval
harness, the prompt-injection defense, and the web-fallback policy — are
documented as short ADRs in [`docs/adr/`](docs/adr/), each
covering the context, the decision, its consequences, the trade-offs
accepted, and the alternatives deliberately not chosen. Start with the
[index](docs/adr/README.md).

### Mocked unit tests vs. API-based chain tests

| | `tests/node/` + `tests/graph/` + `tests/evals/` (unit) | `tests/chains/` (integration) |
|---|---|---|
| What is tested | Node functions (state in/out), routing decisions, the compiled graph with mocked chains, and the eval harness's pure helpers | The LCEL chains: real prompts + structured output against the live model |
| External calls | **None** — retriever, graders, Tavily, and the generation seam are monkeypatched at their lazy `get_*()` factories | Real OpenAI API calls |
| Requirements | No API keys | `OPENAI_API_KEY` (tests are skipped, not failed, without it via the `requires_openai` marker) |
| Speed / cost | Seconds, free | ~1 minute, small API cost |
| Status | 305 tests passing (69 node + 200 graph + 36 evals) | 38 tests passing |

This split is enabled by the lazy-factory pattern: because no client is constructed at import time, every external dependency has a clean, patchable seam.

## Current Limitations

- **Single-turn CLI** — no conversation memory; each question is independent. No API/web surface.
- **Observability is `print()`-based** — no structured logging, timing, or token/cost tracking out of the box (LangSmith tracing can be enabled via env vars).
- **Per-document sequential grading** — relevance grading makes one LLM call per chunk.
- **Prompt-injection defense is prompt-level only** — the generation prompt explicitly treats retrieved content (especially web results) as untrusted evidence, never as instructions ([ADR 010](docs/adr/010-prompt-injection-defense.md)). This is a first-line mitigation, not a complete solution: the relevance gate checks topicality, not safety, and there is no injection detection, content sanitization, or domain allowlisting. Generation has no tools to call, which limits — but does not eliminate — the impact of injected instructions.

## Future Improvements

- Structured logging and documented LangSmith tracing setup.
- Grader-scored (LLM-as-judge) eval metrics on top of the deterministic harness in `evals/`.
- Batched relevance grading.

## What This Project Demonstrates

For reviewers and hiring managers, this codebase is intended to show:

- **Agentic workflow design beyond toy RAG** — a real CRAG implementation with conditional routing, multi-gate self-correction, and a deliberately bounded retry loop (including the subtle decision to grade the final generation *before* enforcing the cap).
- **Dependency-injection discipline in an LLM codebase** — every external client lives behind a lazy cached factory, keeping imports side-effect-free and making the entire graph testable without keys, network, or cost.
- **A deliberate testing strategy** — fast, deterministic, fully mocked unit tests for orchestration logic, strictly separated from clearly labeled, key-gated integration tests for prompt/model behavior.
- **Structured LLM outputs as control flow** — Pydantic schemas (`RouteQuery`, `RetrievalGrade`, `GradeHallucination`, `GradeAnswer`) turn model judgments into typed booleans that drive graph edges, rather than parsing free text.
- **Honest scoping** — the limitations above are documented on purpose: the project optimizes for demonstrating the correction-loop architecture clearly, not for pretending to be production infrastructure.
