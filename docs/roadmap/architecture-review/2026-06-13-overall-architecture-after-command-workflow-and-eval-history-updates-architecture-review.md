# Architecture Review

Status: Review

Date: 2026-06-13

Focus: Overall architecture after command workflow and eval history updates

Report file: `docs/roadmap/architecture-review/2026-06-13-overall-architecture-after-command-workflow-and-eval-history-updates-architecture-review.md`

## 1. Executive summary

**Strong / portfolio-ready.**

The core architecture (graph, nodes, chains, engine, formatting, config) is
clean, consistently layered, and unusually well-documented for a project of
this size. The recent additions under review — the `.claude/commands/`
workflow and the eval **history + delta** feature — were implemented in the
same disciplined style as the rest of the codebase: pure helpers separated
from I/O, metadata-only persistence, safe-by-default behavior, gitignored
generated files, and full mocked-test coverage. Nothing in the recent changes
weakens the privacy guarantees, the bounded retry loop, the `stop_reason`
contract, or the side-effect-free-import rule.

The issues found are all **low severity** and mostly cosmetic: one stale code
comment, an implicit (untested) structural invariant in the trace path, and
some accumulating meta-documentation that risks looking like noise. None block
portfolio use; they are quick polish items.

## 2. Files reviewed

- Context: `CLAUDE.md`, `README.md`, `structure.md`
- Runtime: `graph/graph.py`, `graph/engine.py` (full reads); `graph/state.py`,
  `graph/consts.py`, `graph/config.py`, `graph/formatting.py` (via README /
  structure cross-reference)
- Node/chain inventory: `graph/nodes/*.py`, `graph/chains/*.py` (file listing)
- Eval system: `evals/run_eval.py` (full read), `evals/README.md`,
  `evals/history/` (listing + `.gitkeep`)
- Tests: `tests/evals/test_eval_history.py` (full read); `tests/node/*`,
  `tests/graph/*` (file listing)
- Command workflow: `.claude/commands/arch-review.md` (full read); peer
  commands `new-spec`, `plan-spec`, `implement-spec`, `review-diff` (listing)
- Config / CI: `.github/workflows/ci.yml`, `.gitignore`
- Roadmap artifacts: `docs/roadmap/**` (listing)
- `git status --short` (clean) and recent commit log

`tests/chains/`, `.env`, prompts, model names, corpus documents, and
`ingestion.py` runtime were not executed or modified (review-only).

## 3. Architecture map

- **Graph flow** — A LangGraph `StateGraph` (CRAG pattern) with a conditional
  entry point (`route_question`) and two conditional edges
  (`decide_to_generate`, `grade_generation`). Eleven explicit `grade_generation`
  outcomes map one-to-one to edges; terminal "notice" nodes record a
  `stop_reason`. The regenerate/web-search loop is bounded by `MAX_RETRIES = 5`,
  checked *after* grading so the final generation is still fully verified.
- **Nodes and chains** — Nodes (`graph/nodes/`) are the only state writers,
  including tiny pass-throughs (`add_grounding_feedback`, `rewrite_query`,
  `clear_transient_tool_error`) and terminal notice nodes. Six LCEL chains
  (`graph/chains/`) on `gpt-5-mini`, each behind a lazy `get_*()` factory.
  Conditional edge functions are pure (read-only).
- **Config / runtime** — `graph/engine.py` is the single entry point
  (`answer_question` / `AnswerOptions` / `AnswerResult` / `seed_state`),
  resolving privacy mode and fallback policy once per run into state. All
  external clients are built lazily; imports are side-effect-free.
  `graph/config.py` centralizes env reads; `graph/formatting.py` owns all
  user-facing presentation (caveats + Sources). Lightweight observability
  (run_id, node_path, timings, optional trace JSON) is collected in the engine
  by streaming graph updates.
- **Eval harness** — `evals/run_eval.py` runs the real graph via the engine and
  applies deterministic checks (stop reason, source provenance, counters,
  substrings, fallback-policy echo). Pure helpers (load/validate/summarize/
  evaluate/metrics/render) are separated from history I/O. History + delta is
  metadata-only, append-only, gitignored, with a dataset fingerprint and a
  `dataset_changed` warning.
- **Test structure** — Three keys-free mocked suites (`tests/node/`,
  `tests/graph/`, `tests/evals/`) plus a key-gated integration suite
  (`tests/chains/`). CI runs the mocked suites + lint (ruff + scoped mypy).
- **Docs / workflow** — `README.md` + `structure.md` + 11 ADRs +
  `.claude/commands/` (spec → plan → implement → review-diff → arch-review)
  + `docs/roadmap/` (specs, plans, implementation reports, command reviews,
  architecture reviews).

## 4. What is strong

- **Disciplined separation of concerns.** State writes only in nodes; routing
  logic pure; presentation isolated in `formatting.py`; config reads centralized
  in `config.py`; the engine is the single seeding/resolution site. The eval
  harness mirrors this: pure logic above a thin I/O layer.
- **The engine as a single waist.** CLI, evals, and tests all run through
  `answer_question()`. State seeding and per-run config resolution exist once.
  This is exactly the abstraction that makes the eval-history feature cheap and
  safe to add.
- **Safe-by-construction observability and history.** The trace payload and the
  history record are both *metadata-only by construction* — no `page_content`,
  prompts, or raw state — and the eval test suite actively asserts this
  (`test_build_history_record_is_metadata_only`). Trace/history write failures
  degrade to a type-only console warning and never lose the answer/report.
- **Robust eval history design.** Dataset fingerprint = `row_count` + ordered
  `ids` + SHA-256 of file bytes, surfacing a `dataset_changed` warning so
  deltas aren't silently misread. `_as_pair` handles the tuple→list JSON
  round-trip. `schema_version` guards forward compatibility. Baseline selection
  happens *before* writing so a record is never its own baseline.
- **Generated artifacts handled correctly.** `evals/history/*.json` gitignored;
  the directory kept via `.gitkeep`; an explicit force-add convention documented
  for sharing a baseline. `chroma_db/`, caches, and `.env*` are all ignored
  (with `!.env.example` preserved).
- **Tight command tool-scoping.** `arch-review.md` declares
  `allowed-tools: Read, Write, Glob, Grep, Bash(git status:*), Bash(mkdir:*)` —
  no broad shell or network access for a review-only command.
- **Honest failure surfacing throughout.** The eleven-outcome `grade_generation`
  contract, the budget-before-grading ordering, and the transient-vs-terminal
  `tool_error` distinction are all explicit, commented, and test-backed.

## 5. Main issues found

### Issue 1 — Stale comment: privacy/fallback seeding attributed to `main.py`

- **Issue:** `graph/graph.py` docstring (the Privacy-mode paragraph) still says
  `web_search_enabled` is "seeded from the `WEB_SEARCH_ENABLED` env var by
  main.py". Since the engine refactor, seeding happens in
  `graph/engine.py::seed_state()`, not `main.py`.
- **Why it matters:** A reader tracing how state is seeded is pointed at the
  wrong module. It contradicts the (correct) engine-centric description in
  `structure.md` §3 and the engine docstring.
- **Risk level:** Low.
- **Recommended fix:** Update the comment to attribute seeding to
  `graph/engine.py` (`seed_state`). Doc-only; no behavior change.
- **When:** Later (next docs pass).

### Issue 2 — Trace stream-merge relies on an implicit, untested invariant

- **Issue:** `_run_graph_with_trace` reproduces `app.invoke()` by merging
  `stream_mode="updates"` chunks onto the seeded state. This is correct *only
  because* every `GraphState` channel is a plain last-value overwrite (no custom
  reducers). The invariant is documented in the docstring but not guarded by a
  test, and a future field added with a reducer (e.g. an accumulating list)
  would make traced runs silently diverge from `invoke()`.
- **Why it matters:** Observability is supposed to be *purely additive*. A
  silent divergence would make `node_path`/`raw_state` subtly wrong for the
  default (traced) path while tests using minimal fakes (which fall back to
  `invoke()`) would still pass.
- **Risk level:** Low–Medium (latent, not an active bug).
- **Recommended fix:** Add one mocked equivalence test asserting that, for a
  representative run, the streamed-merge final state equals `app.invoke()` on
  the same seed; optionally a comment in `state.py` noting "last-value channels
  only — see engine trace merge."
- **When:** Should fix soon (cheap insurance for a load-bearing assumption).

### Issue 3 — Accumulating meta-documentation risks looking like noise

- **Issue:** `docs/roadmap/` now holds multiple overlapping process artifacts:
  `commands-review/` has three docs (`claude-command-workflow-review.md`,
  `arch-review-command-review.md`, `arch-review-command-review-v2.md`), and
  `architecture-review/` holds the older un-dated `architecture-review.md`
  alongside the new dated-report convention this command produces.
- **Why it matters:** For a portfolio reviewer, a deep tree of review-of-review
  documents can read as process overhead rather than signal. The mixed naming
  (un-dated vs. dated reports in the same folder) also undercuts the otherwise
  crisp conventions.
- **Risk level:** Low.
- **Recommended fix:** Add a short `docs/roadmap/README.md` index explaining
  what each subtree is for; consider folding the superseded `-v2` command-review
  into one, and either rename or note the legacy un-dated
  `architecture-review.md` as the pre-convention baseline.
- **When:** Optional.

### Issue 4 — Dual resolution of `web_fallback_policy` (engine seeds, graph re-resolves)

- **Issue:** The engine resolves and seeds `web_fallback_policy` into state, but
  `graph.py::_resolve_web_fallback_policy` *also* re-normalizes it and falls back
  to the env default when the field is empty (a back-compat path for legacy
  callers that seed state directly).
- **Why it matters:** Two places "own" the effective policy. It's a deliberate,
  documented back-compat seam, but it's a small hidden-coupling point: the
  invariant "engine always seeds a valid policy" makes the graph-side fallback
  dead code on every supported path, which could mask a future seeding bug.
- **Risk level:** Low.
- **Recommended fix:** Leave as-is for now (the redundancy is defensive and
  harmless). If legacy direct-seeding callers are ever removed, simplify the
  graph helper to a plain `state["web_fallback_policy"]` read.
- **When:** Later / optional.

## 6. Project-specific safety review

This was a review-only pass. Only `git status` (read-only) and targeted file
reads were performed, plus a single `Write` to this new report. Nothing
protected was touched or executed.

| Protected item | Status |
|---|---|
| Prompts | Not read in full, not modified. Intact. |
| Model names (`gpt-5-mini`, `temperature=0`) | Not modified. Intact. |
| Corpus documents (`data/acmecorp_internal_docs/`) | Not opened/modified. Intact. |
| `.env` / `.env.example` | Not inspected (`.env`) / not modified. Intact; `.gitignore` still excludes `.env*` and preserves `!.env.example`. |
| Graph behavior | Not modified. Intact. |
| Graph routing | Not modified. Intact. |
| Graph nodes | Not modified. Intact. |
| `stop_reason` semantics | Not modified. Intact. |
| Fallback policy semantics | Not modified. Intact. |
| Full eval | Not run. |
| `ingestion.py` | Not run/modified. |
| `tests/chains/` | Not run/inspected. |

## 7. Eval architecture review

- **Schema:** Expressive and additive. Required core fields plus optional checks
  (`expected_stop_reason`, `expected_source_type`, `expected_contains` with
  any-of groups, `expected_not_contains`, `expected_source_titles`,
  `expected_min_local_sources`, `expected_web_search_count` with min/max,
  per-row `web_fallback_policy`). Validation is thorough, including the
  `bool`-is-not-`int` guard in `_valid_web_search_count_expectation`. Six
  categories (24 rows) cover local, web-fallback, insufficient-context, privacy,
  multi-document, and policy-fallback behavior.
- **Checks:** Fully deterministic (no LLM-as-judge). `normalize_for_contains`
  (NFKC + dash folding + whitespace collapse + casefold) makes substring checks
  robust without becoming permissive. Multi-document rows assert ≥2 distinct
  local titles via provenance rather than answer wording — a strong choice.
  Privacy rows hard-assert `web_search_count == 0`.
- **History records:** Metadata-only, append-only, sortable filenames
  (`<UTC>__<run_id>.json`), `schema_version`-guarded, dataset-fingerprinted.
  Pure builders separated from `write_/load_/load_latest_history_record` I/O.
- **Delta reporting:** `compute_delta` is pure and JSON-round-trip-safe
  (`_as_pair`), reports overall/category/check deltas and row transitions
  (newly passing/failing, still failing, added, removed), and warns on dataset
  change. `render_delta_section` cleanly handles the no-baseline first-run case.
- **Full eval vs. validate-only:** Cleanly separated. The graph import lives
  *inside* `run_eval`, so `--validate-only` never imports the graph or touches
  APIs/history. `--no-history` renders deltas without writing; `--baseline`
  fails fast (`HistoryBaselineError`) on missing/invalid/incompatible files.
- **Ignored files:** `evals/history/*.json` gitignored with documented force-add
  escape hatch; directory tracked via `.gitkeep`. Correct.
- **Coverage:** `tests/evals/test_eval_history.py` covers fingerprinting,
  record building (incl. metadata-only assertion), delta math (incl. tuple/list
  equivalence and missing-key-as-zero), rendering, I/O round-trips, baseline
  error paths, `--no-history`, and write-failure resilience — all mocked.

## 8. Test architecture review

- **Mocked suites:** Three keys-free suites (`tests/node/`, `tests/graph/`,
  `tests/evals/`) are the CI gate and double as a regression that imports stay
  side-effect-free. Node/graph dirs show broad behavioral coverage (retries,
  budgets, privacy toggle, fallback policy, provenance, error handling,
  insufficient-context bypass, observability, engine).
- **Graph tests:** End-to-end compiled-graph runs drive real retry loops to
  exhaustion and assert negative guarantees (no router/web/rewriter calls in
  privacy mode; no spend past budget). This is the right altitude for an agentic
  graph.
- **Node tests:** Per-node state in/out plus per-dependency graceful-degradation
  paths, mocked at the lazy `get_*()` seam.
- **Eval tests:** Pure-helper coverage is strong (see §7).
- **Risky tests:** Low risk overall. The eval-history mocked-graph tests patch
  `sys.modules["graph.engine"]`/`graph.formatting` — pragmatic and effective,
  though slightly coupled to import timing; acceptable.
- **Missing tests (gaps):**
  - No explicit test that the trace stream-merge equals `invoke()` (see Issue 2).
  - Test/README counts (e.g. "305 tests") are documented numbers that can drift;
    not a correctness risk, but they age.
  - `evaluate_row`/`compute_metrics` coverage lives in `test_eval_harness.py`
    (not read this pass) — assumed covered per README; worth a glance to confirm
    the newer checks (`policy_applied`, `web_search_count` bounds) are exercised.

## 9. Documentation and workflow review

- **README.md:** Excellent and accurate — mermaid flow, env table, privacy mode,
  fallback policy, budgets, failure matrix, engine API, traces, and the
  "what this demonstrates" framing all match the code. One nit: it states
  fixed test counts that will drift over time.
- **structure.md:** Deep and faithful to the implementation (state table,
  eleven-outcome routing table, ordering rationale, trace-merge invariant).
  Best-in-class for a portfolio repo.
- **CLAUDE.md:** Precise and current; the file/responsibility table matches the
  tree, including the engine, formatting split, and eval harness.
- **Claude commands:** A coherent spec→plan→implement→review-diff→arch-review
  pipeline with tight tool scoping. The `arch-review.md` template is *very*
  prescriptive (~400 lines, exact section structure + filename algorithm) —
  reproducible and safe, but heavy; it leans toward over-specification.
- **Roadmap artifacts:** Genuinely useful as evidence of process, but
  accumulating (see Issue 3). An index and light pruning would convert
  "volume" into "signal."
- **Minor staleness:** the `graph.py` seeding comment (Issue 1).

## 10. Recommended next actions

### Must fix
- (none) — no correctness, safety, or privacy defects found.

### Should fix soon
- Add a mocked equivalence test for the trace stream-merge vs. `invoke()` and a
  one-line `state.py` note that channels are last-value only (Issue 2).
- Fix the stale `graph.py` seeding comment to point at `engine.seed_state()`
  (Issue 1).

### Optional improvements
- Add `docs/roadmap/README.md` as an index; consolidate the duplicate
  command-review docs and reconcile the un-dated legacy architecture review with
  the dated convention (Issue 3).
- Replace hardcoded test counts in README with a softer phrasing, or accept
  periodic refresh.
- Long term, if legacy direct-seeding callers go away, simplify
  `_resolve_web_fallback_policy` to a plain state read (Issue 4).

## 11. Portfolio-readiness verdict

**Portfolio-ready.**

The architecture demonstrates exactly what a senior reviewer looks for: a
non-trivial agentic workflow with explicit routing and bounded self-correction,
strict dependency-injection discipline (lazy factories, side-effect-free
imports), a single engine waist that makes features cheap to add, structured
LLM outputs as control flow, and a two-tier testing strategy. The command
workflow and eval-history additions extend this without regressions: both are
pure-core/thin-I/O, metadata-only, safe-on-failure, gitignored, and
test-covered. The open items are doc/cleanup polish, not architectural debt.

## 12. Overall recommendation

The architecture is safe to keep building on as-is — no cleanup is *required*
before adding features, because the engine waist and the pure-helper/thin-I/O
pattern give new work clean seams. The one thing worth doing proactively,
because it protects a load-bearing assumption rather than fixing a present bug,
is the **single next action: add a mocked test asserting the engine's trace
stream-merge produces the same final state as `app.invoke()`** (and note the
last-value-channel invariant in `state.py`). Do the stale-comment and roadmap-
index tidy-ups opportunistically alongside it.
