# ADR 014: `enterprise_rag` package and reserved `office_agent` placeholder

Status: Accepted

Date: 2026-07-01

## Context

The repository began as a single-purpose project: a self-correcting Agentic RAG
(CRAG-style) assistant for enterprise document Q&A. Its code lived in top-level
modules — a `graph/` package (StateGraph, nodes, chains, engine, config, state,
consts, formatting), a top-level `ingestion.py`, and a top-level `data/` corpus —
with `main.py` as the CLI entry point. The repository itself is named
**Enterprise-Office-Agent**, signalling a broader intent than document Q&A alone.

Two forces motivated a structural change:

- **The name promises more than one capability.** "Office agent" implies office
  automation (calendar, email, task workflows) beyond document Q&A. Building that
  on top of flat top-level modules named `graph/` / `ingestion.py` would blur which
  code belongs to the RAG engine and which to a future agent.
- **The RAG engine is complete and behavior-stable.** It has quality gates, privacy
  mode, a configurable web-fallback policy, per-run budgets, graceful degradation,
  deterministic provenance, a synthetic corpus, and a deterministic eval harness
  (ADRs 001–013). Growing a second capability must not risk regressing it.

A clear module boundary was needed so a future office agent can be added without
entangling — or endangering — the finished engine.

## Decision

Reorganize the repository around **named capability modules**, without changing any
runtime behavior.

### 1. `enterprise_rag/` owns the completed RAG implementation

The entire existing RAG implementation moved (git-aware renames, history preserved)
under a single package:

- `graph/` → `enterprise_rag/graph/`
- `ingestion.py` → `enterprise_rag/ingestion.py`
- `data/acmecorp_internal_docs/` → `enterprise_rag/data/acmecorp_internal_docs/`

Imports became `enterprise_rag.graph.*` and `enterprise_rag.ingestion`. The engine's
public entry point is `enterprise_rag.graph.engine.answer_question()`. Behavior,
graph routing, prompts, model names (`gpt-5-mini`), the `GraphState` schema, chain
inputs, and test expectations are unchanged — only import paths and documentation
references were updated. The corpus `source` provenance metadata was updated to the
new repo-relative path (`enterprise_rag/data/acmecorp_internal_docs/…`); the Chroma
persist directory stays a working-directory-relative `chroma_db` resolved from the
repo root, so ingestion and retrieval work exactly as before after a rebuild.

### 2. `office_agent/` is reserved but empty

A minimal `office_agent/` package (docstring-only `__init__.py`) reserves the module
path for future office-automation work. **No office-agent features are implemented.**
When they are, they must follow the same rules as the rest of the repo
(side-effect-free imports, lazy `@lru_cache` external clients) and must not break
`enterprise_rag` behavior or its tests.

### 3. `main.py` stays at the repo root

The CLI entry point remains at the root as a thin wrapper over
`enterprise_rag.graph.engine`, preserving `uv run python main.py` and the
`from main import …` re-export surface the tests rely on.

### 4. Documentation is split into repo-level and module-level

- **Root docs stay repo-level.** `README.md` became a repository overview (module
  table, layout, quickstart, pointers); `CLAUDE.md` gives repo-level guidance
  (which module is complete, which is planned, the "don't break `enterprise_rag`"
  rule); `structure.md` documents the repo layout and module boundaries alongside
  the engine's architecture.
- **Detailed engine usage moved to `enterprise_rag/README.md`** — the setup, privacy
  mode, fallback policy, programmatic API, budgets, and failure-handling content that
  previously dominated the root README.
- **ADRs stay repo-level in `docs/adr/`.** They are not moved into `enterprise_rag/`.

### 5. Historical ADRs are preserved, not rewritten

ADRs 001–013 remain as written. They reference the pre-refactor paths (`graph/…`,
`ingestion.py`); those references are accurate as of each ADR's date and are kept as
history rather than edited. This ADR is the single record of the move. The `docs/adr/`
index is updated to add this entry and to reflect the current code path for its
"ADRs reference real files" convention note.

## Consequences

- The RAG engine is now a self-contained, clearly named package; a reader can see at
  a glance that `enterprise_rag/` is the finished capability and `office_agent/` is
  future work.
- A future office agent has a home (`office_agent/`) that is isolated from the engine,
  so building it cannot silently alter RAG routing, prompts, or state.
- Documentation has two clear altitudes: repo-level (root) and module-level
  (`enterprise_rag/README.md`), so the root no longer conflates "what is this repo"
  with "how do I use the RAG engine".
- Test, lint, and eval workflows are unchanged in intent: `tests/`, `evals/`, and CI
  still target the engine, now via `enterprise_rag.*` imports. The full suite, ruff,
  and mypy pass after the move.

## Trade-offs

- **A one-time import/path churn.** Every internal import and many doc references
  changed. This is mechanical and covered by the (unchanged) tests, but it is a large
  diff and invalidates any externally cached `graph.*` / `ingestion` import paths.
- **Chroma indexes must be rebuilt.** Chunk ids embed the corpus `source` path, which
  changed; a fresh `uv run python -m enterprise_rag.ingestion` is required (the index
  is gitignored and rebuilt on demand, so this is a run-once step, not a data loss).
- **Two README files to keep in sync.** The root overview and the module README can
  drift; the split is justified by the clearer altitude, and cross-links keep them
  discoverable.
- **`office_agent/` is currently dead weight** — an empty package with no behavior.
  Accepted deliberately: it documents intent and reserves the boundary at near-zero
  cost, and the alternative (adding it only when work starts) loses the up-front
  signal about the repository's direction.

## Alternatives considered

- **Leave the code as flat top-level modules** — rejected: the repository name
  promises more than document Q&A, and a second capability built on `graph/` /
  `ingestion.py` would blur ownership and make it easy to regress the finished engine.
- **Move ADRs and `docs/` under `enterprise_rag/`** — rejected: ADRs and repo-level
  docs describe repository-wide decisions (including this one and any future
  cross-module concerns), so they belong at the root, not inside one module.
- **Keep the corpus `data/` at the repo root** — rejected: anchoring the corpus and
  its loader together inside `enterprise_rag/` keeps `ingestion.py`'s
  `Path(__file__).parent / "data"` logic unchanged and lets a future module own its
  own data without collision.
- **Rewrite the historical ADRs to use the new paths** — rejected: they record
  decisions as of their dates; editing their path references would falsify history for
  cosmetic consistency. A single new ADR (this one) plus an index update is enough.
- **Build a first slice of `office_agent` now to justify the package** — rejected:
  out of scope. The refactor's goal is structure and safety for the *existing* engine;
  agent features are separate future work with their own ADRs.
