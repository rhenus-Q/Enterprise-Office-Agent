# Eval History and Delta Reporting — Implementation Plan

Status: Planned

Date: 2026-06-13

Type: Plan

Source spec: `docs/roadmap/spec/eval-history-delta-reporting.md`

## 1. Spec summary

Give the behavioral eval harness (`evals/run_eval.py`) a memory. Today every full
run renders one Markdown report and **overwrites** `evals/results.md`, so there is
no durable record of past runs and no first-class signal for whether a change
moved the numbers. Comparing two runs means diffing a noisy generated file.

This feature adds two deterministic, additive capabilities:

* **History** — after a *successful* run (the command produced evaluated rows +
  metrics; individual row failures are normal and still recorded with
  `passed: false`), persist one compact, machine-readable JSON record per run to
  an append-only `evals/history/` directory, named by a sortable UTC timestamp +
  run id. The record is **metadata-only and small**: `schema_version`, `run_id`,
  `generated`, dataset path, a `dataset_fingerprint` (`row_count`, ordered `ids`,
  `dataset_sha256`), the full `compute_metrics` dict, and a per-row list of
  `{id, category, passed, failed_checks, stop_reason, retries, llm_call_count,
  web_search_count}`. Never answer text, `page_content`, prompts, or raw state.
* **Delta reporting** — load the most recent prior record as a baseline (or an
  explicit `--baseline <path>`), compute pure deltas (overall passed/total,
  per-category pass counts, per-check match counts, and per-row transitions:
  `newly_passing`, `newly_failing`, `still_failing`, `added`, `removed`), flag
  `dataset_changed` when any fingerprint component differs, and render a
  "Delta vs. previous run" Markdown section after the Metrics section.

New CLI flags: `--no-history` (render the delta against any existing baseline but
write no record), `--baseline PATH` (compare against a specific record; missing/
invalid/incompatible fails fast), and `--history-dir PATH` (default
`evals/history/`). `--validate-only` keeps touching neither the graph/API nor
history I/O.

**Why it is needed / problem it solves:** there is currently no way to tell that
"this change made `web_fallback_2` start failing" or "overall pass count dropped
24→22" without manual, lossy git archaeology of a generated file. History + delta
make run-over-run movement explicit and reproducible.

**What must not change:** the dataset (`evals/questions.jsonl`), the graph,
engine, nodes, chains, prompts, model names, state schema, `stop_reason`/
fallback-policy semantics, and every existing pure helper's output shape
(`compute_metrics` keys/tuples, `evaluate_row`, `summarize_result`,
`normalize_for_contains`, check names, `passed = all(checks.values())`). The
delta layer **reads** these; it does not alter them. When no baseline exists, the
existing report sections stay byte-stable and the only addition is a single
"no previous run" delta line.

## 2. Current system understanding

Verified from `evals/run_eval.py`, `evals/README.md`,
`tests/evals/test_eval_harness.py`, and `.gitignore`:

* **Pure/impure separation is already clean.** `evals/run_eval.py` groups:
  * dataset loading/validation (`load_dataset`, `validate_dataset`, helpers) —
    no graph/API;
  * pure summarization/checks (`summarize_result`, `evaluate_row`,
    `compute_metrics`, `normalize_for_contains`);
  * pure reporting (`render_markdown`, `_table_cell`);
  * the only impure entry point, `run_eval`, which imports `graph.engine` /
    `graph.formatting` **lazily inside the function** so `--validate-only` never
    touches the graph.
* **Per-row evaluation shape** (built in `run_eval`): each `evaluated` entry is
  `{"row", "summary", "checks", "passed"}`. `summarize_result` returns `answer`,
  `formatted_answer`, `stop_reason`, `retries`, `llm_call_count`,
  `web_search_count`, `web_result_grading_count`, `sources_shown`,
  `local_source_used`, `web_source_used`, `local_source_titles`,
  `web_fallback_policy`. A broken row degrades to
  `{"checks": {"run_completed": False}, "passed": False}` with an empty summary —
  so `failed_checks` for such a row is `["run_completed"]`.
* **Metrics shape** (`compute_metrics`): `total`, `passed` (plain ints);
  per-check `(passed, total)` **tuples** (`stop_reason_matches`,
  `source_type_matches`, `expected_contains_matches`,
  `expected_not_contains_matches`, `source_titles_matches`,
  `min_local_sources_matches`, `web_search_count_matches`,
  `policy_applied_matches`); per-category `(passed, total)` **tuples** keyed by
  `CATEGORY_METRIC_KEYS` values (`local_answerable_passed`, `web_fallback_passed`,
  `insufficient_context_passed`, `privacy_mode_passed`, `multi_document_passed`,
  `policy_fallback_passed`); and the averages `average_retries`,
  `average_llm_calls`, `total_web_searches`. **JSON round-trips tuples to lists**
  — the delta helper must normalize `[p, t]`/`(p, t)` equivalently.
* **Category ↔ metric-key mapping** is `CATEGORY_METRIC_KEYS` (note the metric
  key names differ from the raw category names, e.g. category `local_corpus` →
  metric `local_answerable_passed`). Per-category delta keys should be derived
  through this mapping, not hard-coded.
* **Rendering** (`render_markdown(evaluated, metrics, dataset_path)`): emits
  `# Eval results` header (Generated/Dataset/Rows), `## Metrics` table,
  a tracked-LLM-calls disclaimer, `## Per-question results` table, and
  `## Answers (truncated)`. Returns `"\n".join(lines) + "\n"`. The delta section
  must be inserted **after the Metrics section** (and before/around the
  disclaimer + per-question table — see Step 4 for the exact seam).
* **Runner** (`run_eval(rows, output_path, dataset_path)`): loops rows → builds
  `evaluated` → `compute_metrics` → writes `render_markdown(...)` to
  `output_path` → prints a console summary → returns `metrics`.
* **CLI** (`main`): argparse flags today are `--dataset`, `--output`, `--limit`,
  `--validate-only`. `--validate-only` validates and exits before any graph
  import. `--limit` slices rows before `run_eval`.
* **Timestamp/Path usage** already imported: `from datetime import UTC, datetime`
  and `from pathlib import Path`; `import json`, `import argparse`, `import sys`.
  `render_markdown` already formats `datetime.now(UTC)`.
* **Tests** (`tests/evals/test_eval_harness.py`) import named helpers directly
  from `evals.run_eval`, use small `_row(**overrides)` / `_summary(**overrides)`
  factories, validate the real shipped dataset, and never call the graph/API.
  New tests should follow these conventions and use `tmp_path` for I/O round
  trips.
* **`.gitignore`** uses sectioned `# ---- ... ----` comment headers (env, Python,
  venv, uv, caches, `chroma_db/`, build, IDE, OS, and a trailing
  "Local planning / roadmap drafts" header). A new rule for
  `evals/history/*.json` fits as its own section; the directory keeps a tracked
  `.gitkeep`.
* **Engine ethos for reference only** (`graph/engine.py`): runs already carry a
  `run_id` and write metadata-only trace JSON (never `page_content`, prompts, raw
  state). History records must match this discipline. No engine changes.

## 3. Files to inspect during implementation

### Required files

* `CLAUDE.md` — project rules (lazy clients, side-effect-free imports, type-only
  logging, plan-first/ask-before-behavior-change, testing rules).
* `evals/run_eval.py` — read in full: the pure helper sections, `compute_metrics`
  (tuple shape + `CATEGORY_METRIC_KEYS`), `render_markdown` (insertion seam),
  `run_eval` (baseline-select → delta → render → conditional write ordering), and
  `main` (argparse). This is the only production file that changes.
* `tests/evals/test_eval_harness.py` — match imports, `_row`/`_summary`
  conventions, dataset-validation style; add new pure + I/O tests here (or a
  sibling test module under `tests/evals/` following the same conventions).
* `evals/README.md` — extend with the history directory, record schema +
  `schema_version`, the new flags, write-status values, delta section, the
  run-vs-run caveat, and the gitignore/force-add convention.

### Optional files

* `.gitignore` — add the `evals/history/*.json` ignore rule (read fully first to
  place it under a fitting `# ---- ... ----` section).
* `evals/results.md` — current report shape, to confirm the delta section slots
  in without disturbing existing sections.
* `evals/questions.jsonl` — **read-only**, only to sanity-check fingerprint
  inputs (row count / ids / content bytes). Must not be edited.
* `graph/engine.py` — reference only, for the `run_id` + metadata-only-trace
  philosophy. No changes.

## 4. Proposed implementation steps

The spec stages this into two phases. **A later agent may complete Phase 1 and
stop** — Phase 1 adds only pure helpers + tests and leaves runner/report/CLI
byte-stable.

### Step 0 — Orient (no edits)

* Read `evals/run_eval.py` in full and `tests/evals/test_eval_harness.py` to
  match structure, naming, and the `(passed, total)` tuple conventions.
* Validation: none.

### Phase 1 — pure/deterministic helpers + tests only (no behavior change)

**Step 1 — pure dataset fingerprint helper.**
* Goal: add `dataset_fingerprint(rows, dataset_content)` →
  `{"row_count", "ids", "dataset_sha256"}`. Takes already-loaded `rows` (for
  `row_count` and ordered `ids`) and the canonical dataset content as input;
  performs **no file I/O**. Pick and document one canonical content type —
  recommend **bytes** (`hashlib.sha256(dataset_content).hexdigest()` where
  `dataset_content` is the raw file bytes) so content edits that leave ids
  unchanged still change the hash. Also add a thin, clearly separated wrapper
  `read_dataset_content(path)` that reads the bytes from disk and feeds the pure
  helper (the wrapper is I/O-adjacent; keep it out of the pure hash path).
* Files likely changed: `evals/run_eval.py` (new `import hashlib`).
* Avoid: reading the file inside the pure helper; changing `load_dataset`.

**Step 2 — pure record / delta / render helpers.**
* Goal: add, grouped with the existing pure "summarization / reporting" sections:
  * `build_history_record(evaluated, metrics, dataset_path, dataset_fingerprint,
    *, timestamp, run_id)` → JSON-serializable dict with the Section-6.1 schema
    (`schema_version: 1`, `run_id`, `generated` = ISO-8601 UTC string, `dataset`,
    `dataset_fingerprint`, `metrics` stored as-is, `rows` = per-row
    `{id, category, passed, failed_checks, stop_reason, retries, llm_call_count,
    web_search_count}`). `failed_checks` = the entry's check names with
    falsy values (mirrors the report's "failed checks" column); a broken row's
    `failed_checks` is `["run_completed"]`. The caller passes the already-built
    fingerprint dict — this helper does no I/O.
  * `compute_delta(baseline_record, current_record)` → the Section-6.3 dict
    (`baseline_run_id`, `baseline_generated`, `dataset_changed`, `overall`,
    `categories`, `checks`, `rows` transitions). Normalize tuple/list metric
    values before arithmetic; treat missing categories/checks on either side as
    `0`; compute transitions by joining baseline and current rows on `id`
    (`newly_passing`, `newly_failing`, `still_failing`, `added`, `removed`);
    `dataset_changed` = true if **any** fingerprint component differs.
  * `render_delta_section(delta)` → list of Markdown lines (or a string),
    including: a no-baseline single line ("No previous run found — this is the
    first recorded run."), a `dataset_changed` warning that aggregate deltas mix
    dataset + behavior changes, signed (+/-) aggregate rows, and the per-row
    transition lists. Accept a "no baseline" sentinel (e.g. `delta is None`) for
    the no-baseline case.
* Files likely changed: `evals/run_eval.py`.
* Avoid: any file I/O in these helpers; altering `compute_metrics`/`evaluate_row`
  output; changing existing `render_markdown` output when there is no baseline.

**Step 3 — Phase 1 tests.**
* Goal: add mocked/pure tests (Section 6.7) covering: `dataset_fingerprint`
  (`dataset_sha256` changes on content edit with identical ids/row_count, and on
  id edits / add / remove); `build_history_record` (shape, metadata-only — assert
  no `answer`/`formatted_answer`/`page_content` keys anywhere in the serialized
  record, failed-row capture, fingerprint embedded); `compute_delta` (all five
  transitions, tuple-vs-list equivalence, missing category/check as 0,
  `dataset_changed` true when any fingerprint component differs);
  `render_delta_section` (no-baseline line, dataset-changed warning, +/-
  formatting, transition lists); and a **regression** test that `render_markdown`
  output for existing sections is unchanged when no delta/baseline is present.
* Files likely changed: `tests/evals/test_eval_harness.py` (or a new sibling
  `tests/evals/test_eval_history.py` following the same conventions).
* Validation after step: `uv run pytest tests/evals/ -q`,
  `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`.

**Phase 1 boundary:** pure helpers + tests only; **no** `run_eval` integration,
**no** CLI flags, **no** history writes, **no** generated JSON. Runner and report
output remain unchanged.

### Phase 2 — I/O, CLI, integration, docs

**Step 4 — thin I/O wrappers + baseline handling.**
* Goal: add (clearly separated from pure logic):
  * `write_history_record(record, history_dir)` — ensure `history_dir` exists;
    derive the filename from `record["generated"]` converted to a filename-safe,
    sortable stamp + `record["run_id"]`, e.g.
    `20260613T141005Z__<run_id>.json`, so lexical sort == chronological sort; no
    extra filename field on the record. Write UTF-8 JSON.
  * `load_history_record(path)` and `load_latest_history_record(history_dir, *,
    exclude=None)` — "latest" = highest-sorting filename, with the just-written
    file excludable.
  * Invalid-baseline handling: **explicit `--baseline`** missing / invalid-JSON /
    incompatible-or-unknown `schema_version` → **fail fast** with a clear,
    specific error (no silent fallback). **Auto-discovery** → iterate newest-first,
    **skip** unreadable/invalid/incompatible candidates with a type-only warning,
    use the next valid one; if none remain, treat as **no baseline**.
* Files likely changed: `evals/run_eval.py`.
* Avoid: putting hashing or delta logic in these wrappers; raising past the
  caller for write failures (Step 5 wraps writes).

**Step 5 — runner + CLI wiring.**
* Goal: in `run_eval`, after `compute_metrics`: build the current record (generate
  a `run_id` + `generated` timestamp; reuse the engine's `run_id` ethos but a
  local uuid/timestamp is fine since the harness aggregates many engine runs);
  **select the baseline before writing** (explicit `--baseline` path, else
  auto-discover latest valid in `history_dir`); `compute_delta`; render the report
  **including the delta section**; then, unless `--no-history`, write the current
  record (excluding it from its own baseline via `exclude`). Track and surface a
  **history write status**: `written` / `skipped_by_no_history` / `failed`. A
  failed write must warn **type-only** and still produce a valid report — never
  abort the run. Thread `history_dir` / `baseline` / `no_history` from `main`
  into `run_eval` (extend its signature with keyword args defaulting to today's
  behavior so existing callers/tests stay valid). Add argparse flags
  `--no-history` (`store_true`), `--baseline PATH`, `--history-dir PATH`
  (default `evals/history/`). Keep `--validate-only` free of history I/O (it
  returns before `run_eval`, so this holds — just confirm no history read is
  added to the validate path).
* Files likely changed: `evals/run_eval.py`.
* Avoid: writing before selecting the baseline; aborting on write failure;
  changing `--validate-only` semantics; changing default `--output` behavior.

**Step 6 — Phase 2 tests.**
* Goal: add tests for `write_history_record` / `load_latest_history_record`
  round-trip via `tmp_path` (lexical == chronological ordering; `exclude` skips
  the just-written file; empty/absent dir → no baseline); baseline error paths
  (explicit `--baseline` missing/invalid-JSON/incompatible-schema → fail fast;
  auto-discovered invalid record skipped with warning → next valid used; none
  valid → no baseline); `--no-history` (uses existing baseline, renders delta,
  writes no record, status `skipped_by_no_history`); simulated write failure via
  `monkeypatch` (status `failed`, type-only warning, valid report still produced,
  run not aborted).
* Files likely changed: `tests/evals/test_eval_harness.py` / new sibling module.
* Validation after step: `uv run pytest tests/evals/ -q`.

**Step 7 — docs + git convention.**
* Goal: update `evals/README.md` — document `evals/history/` (append-only,
  machine-readable, metadata-only), the record schema + `schema_version`, the new
  flags, the write-status values, how the delta section reads, the run-vs-run
  (not "proof of regression") caveat, and the gitignore + manual force-add
  convention (`git add -f evals/history/<file>.json`). Add the `.gitignore` rule
  for `evals/history/*.json` and create a tracked `evals/history/.gitkeep`.
* Files likely changed: `evals/README.md`, `.gitignore`,
  `evals/history/.gitkeep` (new).
* Avoid: editing the dataset; documenting behavior not implemented.

**Step 8 — safe validation + report.**
* Run the Section 8 validation commands and report per Section 12. Full eval is
  **not required** (pure helpers are fully covered by mocked tests) and must not
  be run without separate explicit approval.

## 5. Files expected to change

* `evals/run_eval.py` — new pure helpers (`dataset_fingerprint`,
  `build_history_record`, `compute_delta`, `render_delta_section`), thin I/O
  wrappers (`read_dataset_content`, `write_history_record`, `load_history_record`,
  `load_latest_history_record`), `run_eval` integration, and `main` argparse
  flags. New imports likely `hashlib` (and `uuid` if used for `run_id`).
* `tests/evals/test_eval_harness.py` (and/or a new
  `tests/evals/test_eval_history.py`) — new pure + I/O/CLI tests.
* `evals/README.md` — history/delta/flags/write-status/caveat/git-convention docs.
* `.gitignore` — one rule: `evals/history/*.json`.
* `evals/history/.gitkeep` — new tracked placeholder so the dir exists in a fresh
  clone.

## 6. Files that should not change

* `evals/questions.jsonl` (dataset).
* `graph/` — all of it: `graph/graph.py`, `graph/engine.py`, `graph/state.py`,
  `graph/config.py`, `graph/consts.py`, `graph/formatting.py`, `graph/nodes/`,
  `graph/chains/`.
* Prompt text, model names (`gpt-5-mini`), `temperature=0`.
* `ingestion.py`, the corpus under `data/acmecorp_internal_docs/`.
* `.env`, `.env.example`.
* `main.py`.
* Existing pure-helper output contracts in `evals/run_eval.py`:
  `compute_metrics` keys/tuples, `evaluate_row`, `summarize_result`,
  `normalize_for_contains`, `validate_dataset`, existing check names, and the
  `passed = all(checks.values())` aggregation, and the existing `render_markdown`
  sections (byte-stable when no baseline).
* `evals/results.md` is regenerated by a real run only — do not hand-edit it as
  part of this feature.

## 7. Safety constraints

Default project constraints:

* Do not change prompts unless explicitly approved.
* Do not change model names unless explicitly approved.
* Do not change corpus documents unless explicitly approved.
* Do not change graph behavior unless explicitly approved.
* Do not change graph routing unless explicitly approved.
* Do not change graph nodes unless explicitly approved.
* Do not change `stop_reason` semantics unless explicitly approved.
* Do not change fallback policy semantics unless explicitly approved.
* Do not modify `.env` or `.env.example`.
* Do not run full eval unless explicitly approved.
* Do not run `ingestion.py` unless explicitly approved.
* Do not run `tests/chains/` unless explicitly approved.
* Do not run API-key-requiring commands unless explicitly approved.
* Do not commit automatically.

Feature-specific constraints:

* Do not edit `evals/questions.jsonl`; history/delta must work on the dataset
  as-is.
* Do not change `compute_metrics` output keys/shape, `evaluate_row`,
  `summarize_result`, `normalize_for_contains`, existing check names, or the
  `passed = all(checks.values())` aggregation. The delta layer **reads** these.
* History records are **metadata-only**: never serialize answer text,
  `page_content`, prompts, or raw graph state.
* Writing a history record must never crash a run: wrap the write so an I/O error
  logs a **type-only** warning (project convention) and still leaves a valid
  report.
* A record is built and written only after evaluated rows + metrics exist
  (successful run as defined in the spec Summary). A command-level crash before
  metrics/report writes **no** record — never a partial/corrupt one. Per-row
  failures (`passed: false`) are still recorded normally.
* `--validate-only` must remain free of graph, API, **and** history I/O.
* Keep imports side-effect-free; no module-level clients; the graph import stays
  lazy inside `run_eval`.

## 8. Validation plan

The plan-creation step must not run these; the implementing agent runs them after
implementation.

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest tests/evals/ -q
uv run pytest tests/node/ tests/graph/ tests/evals/ -q
uv run python evals/run_eval.py --validate-only
```

Optional, only with separate explicit user approval (NOT required — pure helpers
are fully covered by mocked tests):

```powershell
uv run python evals/run_eval.py --output evals/results.md
```

## 9. Acceptance criteria

* `uv run python evals/run_eval.py --validate-only` passes on the unchanged
  dataset and performs no history I/O.
* All existing `tests/evals/` tests pass unchanged.
* New mocked tests cover: fingerprint behavior, record construction (metadata-only
  assertion), delta computation (all five transition kinds + tuple/list
  equivalence + missing keys + `dataset_changed`), I/O round-trip + baseline
  selection (`exclude`, lexical==chronological, empty dir), baseline error paths
  (explicit fail-fast; auto-discovery skip-with-warning), `--no-history`,
  write-failure status, and delta rendering (including no-baseline).
* `dataset_sha256` changes when row **content** changes even if `ids` and
  `row_count` are unchanged, and `dataset_changed` is then true.
* A run with no prior history writes exactly one record (status `written`) and
  renders the "no previous run" delta line; the rest of the report is unchanged
  from today's structure.
* A second run produces a delta section correctly reporting aggregate + per-row
  changes vs. the first run, and does not pick its own freshly written record as
  the baseline.
* `--no-history` reads/uses an existing baseline and renders its delta but writes
  no record (status `skipped_by_no_history`); with no baseline it shows the
  no-baseline message. `--baseline PATH` compares against the given record.
* Explicit `--baseline` to a missing/invalid/incompatible file fails fast with a
  clear error; an auto-discovered invalid record is skipped with a warning and
  the next valid record is used.
* A simulated history write failure reports status `failed` (type-only warning)
  yet still produces a valid Markdown report; the run does not abort.
* History records contain no answer text, `page_content`, prompt, or raw-state
  fields (asserted by a test).
* `evals/README.md` documents the directory, schema, flags, write-status values,
  and delta section; `evals/history/*.json` is gitignored with a `.gitkeep`
  retained.
* No prompt/model/corpus/.env changes; no graph behavior changes; no dataset or
  existing-check changes.
* `uv run ruff check .`, `uv run ruff format --check .`, and `uv run mypy` are
  clean.

## 10. Risks and calibration notes

* **LLM/retrieval/web variability:** the eval drives real router/graders/
  generation, so two runs of identical code can differ. Deltas mix genuine code
  changes with run-to-run noise — frame the section as "run vs. run", not "proof
  of regression"; document the caveat in `evals/README.md`.
* **Tuple/JSON round-trip:** `compute_metrics` emits `(passed, total)` tuples;
  JSON load yields lists. `compute_delta` must normalize both forms or arithmetic
  is subtly wrong. Covered by an explicit test.
* **Baseline selection ordering:** writing the new record before selecting the
  baseline would make a run its own baseline (all-zero deltas). Enforce
  select-then-write plus an `exclude` guard; covered by a test.
* **Category metric-key mapping:** per-category deltas must go through
  `CATEGORY_METRIC_KEYS` (category names ≠ metric-key names); hard-coding risks
  KeyErrors or mislabeled rows.
* **Dataset drift:** add/remove/reorder changes which ids exist;
  `added`/`removed` + `dataset_changed` exist so aggregate deltas are not
  silently misread, and `dataset_sha256` catches same-id content edits that
  `row_count`/`ids` miss.
* **Report byte-stability:** the no-baseline case must leave existing sections
  unchanged; a regression test guards this. Choose the insertion seam carefully
  (after Metrics) so only the new section is added.
* **History growth / privacy:** one file per run accumulates unbounded; gitignored
  by default so the repo doesn't bloat, but the local dir grows
  (pruning is out of scope — note as follow-up). Records are metadata-only,
  upholding the engine's trace discipline; a test asserts no content leaks.
* **Git convention drift:** history is gitignored, so a shared baseline needs a
  manual `git add -f`; document so a "missing" baseline on another machine is
  understood as expected.
* **Overengineering:** resist trend lines, multi-baseline aggregation, or CI
  gating — single previous-vs-current delta is the agreed scope.
* **Documentation drift:** keep `evals/README.md` and any roadmap docs
  referencing report structure in sync with the new section and flags.

## 11. Recommended implementation prompt

> Read `CLAUDE.md` first. Then read this plan
> (`docs/roadmap/plan/eval-history-delta-reporting-plan.md`). Read the source
> spec (`docs/roadmap/spec/eval-history-delta-reporting.md`) only if this plan is
> insufficient on a detail or the user asks. Implement **only** the planned
> scope: add eval history records and run-over-run delta reporting to
> `evals/run_eval.py`, with tests in `tests/evals/`, docs in `evals/README.md`,
> the `.gitignore` rule, and `evals/history/.gitkeep`. You may complete Phase 1
> (pure helpers + tests) and stop, leaving runner/report/CLI byte-stable.
> Respect every safety constraint in Section 7: do not touch the dataset, graph,
> engine, nodes, chains, prompts, model names, state schema, `.env`, or the
> existing pure-helper output contracts; keep history records metadata-only;
> never let a write failure abort a run; keep `--validate-only` free of history
> I/O; keep imports side-effect-free and the graph import lazy. Run only the
> approved safe validation commands in Section 8 — do **not** run the full eval,
> `ingestion.py`, `tests/chains/`, or any API-key command without separate
> explicit approval. Do not commit or create branches. Report per Section 12.

## 12. Final report format

The implementing agent should report:

* Files changed.
* What was implemented (and whether it stopped after Phase 1).
* Tests run (and results).
* Whether full eval was run.
* Whether API-key commands were run.
* Whether prompts/models/corpus/.env changed.
* Whether graph behavior changed.
* `git status --short`.
* `git diff --stat`.
* Known risks or follow-up work (e.g. history pruning/rotation).
