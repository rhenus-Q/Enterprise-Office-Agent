# Architecture Review

Status: Review

Date: 2026-06-13

Focus: Overall architecture

## 1. Executive summary

**Strong / portfolio-ready.** This is a genuinely well-architected Agentic RAG /
LangGraph project that would read as senior-level work to a hiring manager or a
reviewing engineer. The design has a clear, consistently applied grammar
(pure conditional edges, state writes only in nodes, every external client
behind a lazy `@lru_cache` factory, side-effect-free imports), a single
canonical entry point (`graph.engine.answer_question()`) that centralizes state
seeding and per-run config resolution, honest failure handling with
machine-readable `stop_reason` values, a deterministic eval harness with
history/delta reporting, and documentation (README + `structure.md` + 11 ADRs)
that matches the code closely.

The issues found are refinements, not structural problems. The most
architecturally interesting one is a *load-bearing-but-untested invariant*: the
engine returns the state assembled by merging streamed node updates, which only
equals `app.invoke()` because `GraphState` has no reducer channels — a fact the
code documents but no test guards. Everything else is comment drift, type-check
scope, and roadmap-artifact tidiness. None block portfolio use.

## 2. Files reviewed

Context / setup:

* `CLAUDE.md`, `README.md`, `structure.md`
* `pyproject.toml`, `.github/workflows/ci.yml`, `.gitignore`
* `git status --short`

Graph / runtime:

* `graph/graph.py`, `graph/engine.py`, `graph/state.py`, `graph/config.py`,
  `graph/consts.py`, `graph/formatting.py`
* `graph/nodes/__init__.py`, `graph/nodes/generate.py`,
  `graph/nodes/web_search.py`, `graph/nodes/retrieve.py`
* `graph/chains/__init__.py`, `graph/chains/generation.py`
* `main.py`, `ingestion.py`

Eval system:

* `evals/run_eval.py`, `evals/README.md`, `evals/questions.jsonl`,
  `evals/history/` (listing: `.gitkeep` only)

Tests (read in full or sampled):

* `tests/graph/test_engine.py`, `tests/graph/test_observability.py`,
  `tests/evals/test_eval_history.py`
* `tests/` tree listing (node / graph / evals / chains directories and file
  names)

Claude command workflow:

* `.claude/commands/arch-review.md`, `.claude/commands/review-diff.md`
* `docs/roadmap/claude-command-workflow-review.md`,
  `docs/roadmap/architecture-review/arch-review-command-review.md`

Not inspected, by instruction: `tests/chains/`, `.env`, corpus documents. No
application code, tests, evals, prompts, or config were modified — this review
wrote only this report file.

## 3. Architecture map

**Graph flow.** A `StateGraph` (`graph/graph.py`) with a conditional entry
point (`route_question`) and two conditional edges (`decide_to_generate` after
document grading, `grade_generation` after generation). `grade_generation`
returns eleven explicit outcomes, each mapped one-to-one to an edge. The
self-correction loop (regenerate on not-grounded, rewrite+websearch on
not-useful) is bounded by `MAX_RETRIES = 5`, checked *after* grading so the
final generation is still fully verified. Three quality gates: document
relevance, answer grounding, answer usefulness.

**Nodes and chains.** Nodes (`graph/nodes/`) are the only place state is
written, including tiny pass-through nodes (`add_grounding_feedback`,
`rewrite_query`) and terminal notice nodes that record a `stop_reason`. Chains
(`graph/chains/`) are six LCEL pipelines on `gpt-5-mini` (`temperature=0`), each
behind a lazy `get_*()` factory with backward-compatible module-level
`__getattr__` for the old names. Conditional-edge functions are pure (read
state/chains, never write).

**Config / runtime.** `graph/config.py` centralizes env access
(`web_search_enabled`, `web_fallback_policy` + `normalize_web_fallback_policy`,
three per-run budgets). `graph/engine.py` is the canonical entry point:
`seed_state()` is the single state-seeding site; per-run `AnswerOptions`
override env defaults and are written into state once, so graph decisions never
read `os.environ` mid-run. `graph/formatting.py` is a pure presentation module
(stop-reason caveats + deterministic Sources section) shared by the CLI, evals,
and engine. `main.py` is a thin CLI that re-exports formatting names for
backward compatibility. `ingestion.py` is the offline, idempotent Chroma build.

**Observability.** Additive by construction: the engine streams the compiled
graph's node updates (`stream_mode="updates"`), records `run_id`, `node_path`,
per-step timings, and total duration, and can write a metadata-only trace JSON.
A test asserts the trace never contains `page_content` or raw state.

**Eval harness.** `evals/run_eval.py` runs the real graph through the same
`answer_question()` entry point, applies deterministic checks (stop reasons,
provenance, counters, expected/forbidden substrings, fallback-policy echoes),
and writes `evals/results.md` plus a metadata-only history record with
run-over-run delta reporting. Pure helpers are cleanly separated from file I/O.
`--validate-only` is safe; the full run is excluded from CI.

**Test structure.** Two tiers: fully mocked unit suites (`tests/node/`,
`tests/graph/`, `tests/evals/`) that need no keys and run in CI, plus key-gated
integration tests (`tests/chains/`) against the real model. Mocks target the
lazy `get_*()` seams.

**Docs / workflow.** README + `structure.md` + ADRs 001–011, plus a
`.claude/commands/` spec→plan→implement→review workflow and a `docs/roadmap/`
artifact tree (specs, plans, implementation reports, templates, and two review
documents).

## 4. What is strong

* **A single, consistently applied design grammar.** Pure edges; state writes
  only in nodes; every retry passes through `generate` (so the counter that
  `MAX_RETRIES` caps cannot be bypassed); shared constants in `consts.py`;
  presentation isolated in `formatting.py`. This consistency is what makes the
  graph readable despite eleven terminal outcomes.
* **Dependency-injection discipline.** Every external client (`ChatOpenAI`,
  `OpenAIEmbeddings`, `Chroma`/retriever, `TavilySearch`) is built inside an
  `@lru_cache` factory; imports are side-effect-free. This is verified, not just
  claimed — the mocked CI suites and the import-only smoke check depend on it,
  and `test_seed_state_covers_every_graphstate_field` actively guards the state
  contract.
* **One canonical entry point.** `answer_question()` owns state seeding and
  per-run config resolution, so the CLI, evals, and tests cannot drift in how a
  run is set up. Per-run options (`web_search_enabled`, `web_fallback_policy`)
  override env without mutating it — exactly what evals and tests need.
* **Honest failure handling.** Every external call is wrapped; banners log only
  the exception *type* (never messages that could carry secrets); failures
  degrade or stop with a specific `stop_reason`; ungraded content is never
  trusted; a failed-verification answer is never presented as verified. The
  transient-vs-terminal `tool_error` distinction (cleared on success, kept on
  whole-source degradation) is a subtle, correct touch.
* **Security-minded generation.** The generation system prompt explicitly treats
  retrieved context as untrusted evidence (prompt-injection first line of
  defense, ADR 010), and web results face the *same* relevance gate as local
  chunks rather than getting a free pass.
* **Deterministic, well-separated eval harness.** No LLM-as-judge; checks are
  reproducible; history records are metadata-only with a dataset fingerprint and
  delta reporting; pure helpers are unit-tested without API calls. The
  expressive row schema (any-of substring groups, not-contains, source-title and
  min-local-source checks, web-search-count bounds, per-row policy) is more than
  most portfolio projects attempt.
* **Documentation that matches the code.** README, `structure.md`, and the ADRs
  describe the implementation accurately, down to ordering subtleties in
  `grade_generation`. This is a real differentiator.

## 5. Main issues found

### Issue 1 — The engine's returned state relies on an untested "no reducer channels" invariant

* **Issue:** `answer_question()` returns the state assembled by
  `_run_graph_with_trace`, which merges streamed node updates with a plain
  `dict.update()` (last-value-wins). This equals `app.invoke()` *only because*
  every `GraphState` channel is a last-value channel. The docstring states this
  invariant, but no test enforces it. If a future feature adds a reducer channel
  (e.g. `Annotated[list[Document], operator.add]`), `invoke()` would accumulate
  across nodes while the engine's merge would overwrite — and since the merged
  state is the authoritative return value, this would be a silent *behavior*
  divergence, not merely a trace artifact.
* **Why it matters:** It is the one place where the "tracing is additive and can
  never change behavior" guarantee could quietly become false, and it sits on
  the critical path of every run.
* **Risk level:** Medium.
* **Recommended fix:** Add a regression test asserting `GraphState` uses only
  last-value channels (e.g. assert none of the annotations are `Annotated` with
  a reducer), or have the engine assert/fall back to `invoke()` if a reducer
  channel is ever introduced. Keep the existing
  `test_streamed_updates_reproduce_the_final_state` as the behavioral companion.
* **When:** Soon (before any feature that touches the state schema or
  accumulating channels).

### Issue 2 — mypy scope excludes the most logic-dense modules

* **Issue:** mypy is scoped to `engine.py`, `config.py`, `formatting.py`,
  `state.py`, `consts.py`. The orchestration core (`graph/graph.py`, including
  the eleven-outcome `grade_generation`) and every node/chain are
  `follow_imports = "silent"` and effectively unchecked.
* **Why it matters:** The decision logic with the highest branching complexity
  is exactly where type checking would catch the most mistakes; right now it is
  guarded only by tests.
* **Risk level:** Low–Medium.
* **Recommended fix:** This is a documented, defensible tradeoff (LangChain
  typing is noisy). Consider incrementally adding `graph/graph.py` and the node
  signatures to the mypy `files` list with targeted `# type: ignore` where
  LangChain types fight back, rather than expanding wholesale.
* **When:** Later / optional.

### Issue 3 — Stale comment in `consts.py` about who reads `WEB_SEARCH_SOURCE`

* **Issue:** `graph/consts.py` says `WEB_SEARCH_SOURCE` is "Shared by the
  web_search node (which writes it) and main.py (which reads it for the Sources
  section)." The reader is now `graph/formatting.py` (`source_lines` /
  `_web_source_lines`) and `evals/run_eval.py`; `main.py` only re-exports
  formatting. The comment predates the formatting extraction.
* **Why it matters:** A comment that names the wrong collaborator is a small
  trust tax in an otherwise precise codebase; it can mislead a future reader
  about the module boundary.
* **Risk level:** Low.
* **Recommended fix:** Update the comment to name `graph/formatting.py` (and the
  eval harness) as the readers. (Comment-only; no behavior change — outside the
  scope of this review to apply.)
* **When:** Later.

### Issue 4 — Roadmap-artifact organization is starting to accrue noise

* **Issue:** `docs/roadmap/` now holds specs, plans, implementation reports,
  three templates, and two review documents
  (`claude-command-workflow-review.md`, and
  `architecture-review/arch-review-command-review.md`). This architecture review
  lands in the same `architecture-review/` folder as a *command*-review, so the
  folder mixes two different review subjects, and there is still no
  `docs/roadmap/README.md` index (already recommended by the command-workflow
  review).
* **Why it matters:** For a portfolio repo, a navigable docs tree reads as
  intentional; an unindexed pile of process artifacts reads as clutter. It also
  makes `/review-diff` more likely to misclassify new roadmap files.
* **Risk level:** Low.
* **Recommended fix:** Add a short `docs/roadmap/README.md` describing the
  spec→plan→implementation→review lifecycle and what the `architecture-review/`
  folder contains; consider whether the command-review belongs under a
  `command-reviews/` (or similar) subfolder distinct from the
  product-architecture review.
* **When:** Optional.

### Issue 5 — A few hardcoded magic numbers are not configurable like the budgets are

* **Issue:** Retrieval `k=3` (`ingestion.py`) and Tavily `max_results=3`
  (`web_search.py`) are inline literals, while the per-run budgets are
  env-configurable through `graph/config.py`.
* **Why it matters:** Minor inconsistency in where "knobs" live; tuning recall
  currently means editing source.
* **Risk level:** Low.
* **Recommended fix:** If these are ever tuned in practice, route them through
  `graph/config.py` for consistency. Otherwise leave them — over-parameterizing
  a demo is its own smell.
* **When:** Optional.

## 6. Project-specific safety review

All protected areas were respected during this review (read-only inspection;
only `git status --short` was executed; the sole file written is this report):

| Area | Protected? | Note |
|---|---|---|
| prompts | ✅ | `graph/chains/generation.py` read only; not modified |
| model names (`gpt-5-mini`) | ✅ | Observed, untouched |
| corpus documents | ✅ | Not opened |
| `.env` / `.env.example` | ✅ | Not opened; `.gitignore` correctly ignores `.env*` and un-ignores `.env.example` |
| graph behavior | ✅ | `graph/graph.py` read only |
| graph routing | ✅ | Routing functions read only |
| graph nodes | ✅ | Nodes read only |
| `stop_reason` semantics | ✅ | `consts.py` / `formatting.py` read only |
| fallback policy semantics | ✅ | `config.py` / decisions read only |
| full eval | ✅ | Not run |
| `ingestion.py` | ✅ | Read only; not executed |
| `tests/chains/` | ✅ | Not inspected, per instruction |

No API-key-requiring command was run; no commit, branch creation, or branch
switch occurred.

## 7. Eval architecture review

* **Schema:** Expressive and well-validated. Required fields plus optional
  checks (`expected_stop_reason` as string-or-list, `expected_source_type`,
  any-of `expected_contains` groups, `expected_not_contains`,
  `expected_source_titles`, `expected_min_local_sources`,
  `expected_web_search_count` as int-or-min/max, per-row `web_fallback_policy`).
  `validate_dataset` checks types thoroughly, including the bool-is-not-int trap
  in `_valid_web_search_count_expectation`.
* **Checks:** Fully deterministic — stop reasons, provenance metadata, counters,
  normalized substrings (NFKC + dash folding + casefold, a thoughtful guard
  against typographic false negatives), category rules, and a hard
  `web_search_count == 0` assertion on every privacy row. No LLM-as-judge.
* **History / delta:** Metadata-only records (no answer text, `page_content`,
  prompts, or raw state — asserted by `test_build_history_record_is_metadata_only`),
  SHA-256 dataset fingerprint that catches content edits even when ids are
  unchanged, sortable filenames, `compute_delta` handling tuple-vs-list JSON
  round-trips and a `dataset_changed` warning. Pure helpers separated from thin
  I/O wrappers.
* **Full vs. safe:** `--validate-only` touches no graph or API (the engine is
  imported lazily inside `run_eval`). The full run is clearly marked
  REAL-API/not-in-CI in code, README, and ADR 009.
* **Generated files ignored:** `evals/history/*.json` is gitignored with
  `.gitkeep` tracking the directory; the force-add convention for sharing a
  baseline is documented.
* **Test coverage:** `tests/evals/test_eval_history.py` is thorough —
  fingerprints, record shape/metadata-only, all delta transitions, render
  stability, I/O round-trips, baseline error paths, `--no-history`, and
  write-failure resilience.

One small risk: the `web_fallback`/`policy-aggressive` rows depend on live web
results and model routing, so they are inherently flakier than the local and
privacy rows. This is acknowledged in the README/ADR ("run vs. run, not proof of
regression"); no action needed beyond keeping that framing.

## 8. Test architecture review

* **Mocked unit tests:** Patch the lazy `get_*()` seams, need no keys, and form
  the CI suite. The engine tests use both a minimal `_FakeApp` and a real
  compiled-graph run with mocked node seams, which is the right blend of fast
  and faithful.
* **Graph tests:** Cover routing branches, the privacy toggle, stop reasons,
  budgets, fallback-policy resolution from state (incl. env-precedence and
  legacy-fallback paths), and end-to-end retry exhaustion with negative
  guarantees (no web/router/rewriter calls in privacy mode).
* **Node tests:** Cover per-node state in/out and graceful degradation when each
  node's dependency raises.
* **Eval tests:** Pure-helper coverage is strong (see §7).
* **Recent features covered:** Engine API, observability (run_id/node
  path/timings/trace + the no-page-content assertion), and eval history all have
  dedicated mocked suites. This is better-than-typical coverage for newly added
  surface.
* **Missing / risky:**
  * The "no reducer channel" invariant behind the engine's streamed-state merge
    is not guarded (Issue 1) — the single most valuable test to add.
  * `graph/formatting.py` (`source_lines` / `_web_source_lines` /
    `format_answer`) carries real branching (page-level vs. query-level vs.
    generic fallbacks, dedup, caveat ordering). It is exercised indirectly via
    engine/eval tests; a small direct unit test would harden a user-facing,
    pure, easily-testable module. (Confirm whether `tests/node/` already covers
    it before adding.)
  * No brittle/over-mocked tests were observed; mocks sit at the documented
    seams rather than reaching into internals.

## 9. Documentation and workflow review

* **README:** Excellent and accurate — flow diagram, feature list, env table,
  privacy/fallback explanations, failure-handling table, and an honest
  "limitations / what this demonstrates" section. Strong portfolio asset.
* **structure.md:** A faithful deep-dive (state table, node table, the
  eleven-outcome routing table, ordering rationale). Matches the code, including
  the streamed-updates/`invoke()` equivalence note that underlies Issue 1.
* **CLAUDE.md:** Precise operating contract; the module table matches the repo.
* **ADRs:** Eleven decision records with an index; the decision set maps to the
  features. This is the kind of artifact that reads as professional.
* **Claude commands:** The spec→plan→implement→review workflow is coherent and
  safety-aware; the `arch-review`/`review-diff` commands are review-only and run
  nothing expensive. Two prior review docs already catalog the workflow's own
  minor issues (permission-allowlist breadth in some commands, a frontmatter
  defect, a template/plan contradiction). Those belong to the workflow, not the
  product architecture, but they confirm the team reviews its own tooling.
* **Roadmap artifacts:** Useful as process evidence but trending toward
  un-indexed (Issue 4).

Documentation drift is low overall; the `consts.py` comment (Issue 3) is the one
concrete instance found.

## 10. Recommended next actions

### Must fix

* None. The architecture is correct and safe to build on as-is.

### Should fix soon

* **Issue 1** — Add a guard test (or engine fallback) for the "GraphState has
  only last-value channels" invariant that the engine's streamed-state merge
  depends on. Highest-value item.
* Consider a small direct unit test for `graph/formatting.py` if one does not
  already exist in `tests/node/`.

### Optional improvements

* **Issue 3** — Refresh the stale `WEB_SEARCH_SOURCE` comment in `consts.py`.
* **Issue 4** — Add `docs/roadmap/README.md`; separate command-reviews from the
  product-architecture review folder.
* **Issue 2** — Incrementally widen mypy to `graph/graph.py` and node
  signatures.
* **Issue 5** — Route `k` / Tavily `max_results` through `graph/config.py` only
  if they are ever tuned in practice.

## 11. Portfolio-readiness verdict

**Portfolio-ready.**

The project demonstrates exactly what a strong Agentic RAG / LangGraph portfolio
piece should: a real CRAG implementation with conditional routing and bounded
multi-gate self-correction; dependency-injection discipline that keeps the whole
graph testable without keys; structured LLM outputs used as typed control flow;
a deterministic eval harness with history/delta tracking; graceful degradation
with honest user-facing caveats; and documentation (README + structure + ADRs)
that a reviewer can trust. The open items are refinements, and the project's
limitations are documented deliberately rather than hidden — itself a senior
signal. It does not show meaningful overengineering (the budgets, notice nodes,
and observability each earn their place) nor underengineering (the failure and
privacy paths are unusually complete for a demo).

## 12. Overall recommendation

The architecture is safe to keep building on; no cleanup is required before
adding features. The one thing worth doing *before* the next state-schema-level
change is to pin down the invariant in Issue 1 — the engine returns a state
built by merging streamed updates, which equals `invoke()` only while
`GraphState` stays free of reducer channels, and that fact is currently
documented but not tested.

**Single next recommended action:** add a regression test asserting
`GraphState` uses only last-value channels (paired with the existing
`test_streamed_updates_reproduce_the_final_state`), so any future
accumulating-channel feature fails loudly instead of silently diverging.
