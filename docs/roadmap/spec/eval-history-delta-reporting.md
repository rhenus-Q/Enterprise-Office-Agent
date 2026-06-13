# Eval History and Delta Reporting

Status: Draft

Date: 2026-06-13

Type: Spec

## 1. Summary

Give the behavioral eval harness (`evals/run_eval.py`) a memory. Each full eval
run currently overwrites a single `evals/results.md` snapshot, so there is no
record of past runs and no way to see whether a change moved the numbers.

This spec adds two capabilities, both deterministic and additive:

* **History**: after a successful run, persist a compact, machine-readable
  JSON record of that run (metrics + per-row pass/fail/checks/counters, plus a
  small metadata header) to an append-only `evals/history/` directory, one
  timestamped file per run.
* **Delta reporting**: load the most recent prior history record as a baseline,
  compute the differences against the current run (overall pass count,
  per-category pass counts, per-check match counts, and per-row status
  transitions — newly passing, newly failing, added, removed), and render a
  "Delta vs. previous run" section into the Markdown report.

The dataset, graph, engine, chains, prompts, models, and existing checks are
untouched. Existing rows pass/fail exactly as before; a first-ever run (no
baseline) simply reports "no previous run" and still writes its history record.

Throughout this spec, a **"successful run"** means the eval command completed
and produced evaluated rows plus metrics — it does **not** mean every row
passed. Individual row failures are normal eval outcomes and are still recorded
(with `passed: false`). Only a command-level crash that aborts before metrics
and report generation produces no normal history record.

## 2. Background / Current behavior

`evals/run_eval.py` runs the dataset through the real graph and:

* Builds per-row evaluations in `run_eval` via `summarize_result` +
  `evaluate_row` (each entry: `{"row", "summary", "checks", "passed"}`).
* Aggregates them with `compute_metrics` into a metrics dict containing
  `total`, `passed`, the per-category `(passed, total)` tuples
  (`local_answerable_passed`, `web_fallback_passed`, …), the per-check
  `(passed, total)` tuples from `check_counts` (`stop_reason_matches`,
  `source_type_matches`, `expected_contains_matches`, etc.), and the averages
  (`average_retries`, `average_llm_calls`, `total_web_searches`).
* Renders a single Markdown report with `render_markdown` and writes it to
  `--output` (default `evals/results.md`), **overwriting** any prior report.

Limitations this spec addresses:

* **No history.** Each run clobbers `results.md`; comparing two runs means
  manually diffing git history of a generated file, which is noisy (timestamps,
  truncated answers) and lost once committed over.
* **No deltas.** There is no first-class signal for "this change made row
  `web_fallback_2` start failing" or "overall pass count dropped 24→22". The
  per-row table shows the *current* state only.

The harness already cleanly separates pure helpers (`compute_metrics`,
`evaluate_row`, `render_markdown`, validation) from the API-driven `run_eval`
loop. That separation is what makes history/delta logic addable as pure,
unit-testable functions without touching graph or API code.

## 3. Goals

* Persist one compact JSON history record per real eval run under
  `evals/history/`, named by UTC timestamp + run identifier, append-only.
* Make the history record **metadata-only and small**: metrics dict, dataset
  path, timestamp, a dataset fingerprint (see below), and a per-row list of
  `{id, category, passed, failed_checks, stop_reason, retries,
  llm_call_count, web_search_count}`. Do **not** store answer text,
  `page_content`, prompts, or raw graph state.
* Make the `dataset_fingerprint` strong enough to detect content edits even
  when ids are unchanged. It must include at least `row_count`, the ordered
  `ids`, and `dataset_sha256` (one canonical SHA-256 over the dataset content).
  `dataset_changed` is true if **any** fingerprint component differs between
  baseline and current. (Per-row content hashes are a possible future
  extension; not required here.)
* Keep the fingerprint **computation pure**: the core helper takes
  already-loaded rows plus the canonical dataset content (bytes/text) as
  inputs and returns the fingerprint deterministically — no file reads inside
  it. Reading `dataset_path` from disk is a thin I/O-adjacent wrapper kept
  separate from (and feeding) the pure hash computation, so the hashing stays
  unit-testable without touching the filesystem.
* Load the most recent prior record (by filename/timestamp ordering) as the
  baseline; support an explicit `--baseline <path>` override.
* Compute deltas as a pure function from two history records:
  * overall `passed`/`total` change,
  * per-category pass-count change,
  * per-check match-count change,
  * per-row transitions: `newly_passing`, `newly_failing`,
    `added` (rows not in baseline), `removed` (baseline rows absent now),
    and `still_failing` (for visibility).
* Render a "Delta vs. previous run" Markdown section (baseline id/timestamp,
  the aggregate changes with +/- signs, and the per-row transition lists).
* Add CLI flags:
  * `--no-history`: run and render the report (including the delta section
    against any existing baseline), but **do not write** the current run's
    history record. If no baseline exists it renders the normal no-baseline
    message.
  * `--baseline <path>`: compare against a specific record instead of the
    auto-discovered latest. A missing/invalid/incompatible file fails fast
    with a clear error (see Section 6).
  * `--validate-only` continues to touch neither history (no read, no write)
    nor the graph.
* Keep all new logic deterministic and pure (unit-testable without API keys);
  the only impure parts are the file write and directory read, isolated in thin
  wrappers.
* Document the history directory, record schema, flags, and delta section in
  `evals/README.md`.

## 4. Non-goals

* No changes to the graph, engine, nodes, chains, prompts, state schema,
  model names, `stop_reason` semantics, or fallback-policy semantics.
* No changes to the dataset (`evals/questions.jsonl`) or to any existing check
  logic, check names, normalization, or `passed = all(checks.values())`
  aggregation.
* No changes to what `--validate-only` does (still no API, no graph, and now
  also no history I/O).
* No trend charts, time-series plots, web dashboards, or multi-run aggregation
  beyond the single previous-vs-current delta.
* No automatic pruning/rotation/compaction of the history directory (a manual
  concern; may be a later follow-up).
* No CI gating on deltas (e.g. "fail the build if pass count dropped"); the
  eval is not part of CI.
* No storing of answer text or any corpus/prompt content in history records.
* No automatic `git add`/commit of history files. Generated history JSON is
  gitignored by default (see Section 6); the harness never stages or commits
  records. Developers may *manually* commit a selected baseline if they want a
  shareable reference point — which, because the files are ignored, requires a
  force-add (`git add -f`).

## 5. Files to inspect

* `CLAUDE.md`
* `evals/run_eval.py` — the runner loop (`run_eval`), `compute_metrics`,
  `evaluate_row`/`summarize_result` (shape of per-row data), `render_markdown`
  (where the delta section is inserted), the CLI (`main` / argparse), and the
  `datetime`/`Path` usage already present.
* `evals/questions.jsonl` — only to derive the dataset fingerprint (row
  count, ordered ids, and `dataset_sha256`); must not be edited.
* `evals/README.md` — dataset/usage docs to extend with history + delta + flags.
* `evals/results.md` — current report shape (the delta section is added to it).
* `tests/evals/test_eval_harness.py` — existing mocked tests for validation,
  checks, metrics, and rendering; new pure tests follow the same conventions.
* `graph/engine.py` — only for reference on the existing `run_id` concept and
  metadata-only trace philosophy (so the history record matches that ethos);
  no changes here.

## 6. Proposed changes

All changes live in `evals/run_eval.py`, `evals/README.md`, `tests/evals/`,
`.gitignore` (one ignore rule), and a new `evals/history/.gitkeep`. A new
generated-artifact directory `evals/history/` holds the per-run JSON records
(written at runtime, gitignored). No application or graph code is touched.

1. **History record construction (pure)**
   * Add a pure helper, e.g. `build_history_record(evaluated, metrics,
     dataset_path, dataset_fingerprint, *, timestamp, run_id)`, returning a
     JSON-serializable dict. The caller is responsible for: reading the dataset
     content through thin I/O-adjacent logic, calling
     `dataset_fingerprint(rows, dataset_content)`, and passing the resulting
     fingerprint dict in. This keeps `build_history_record` itself pure and
     free of hidden file I/O.
     ```
     {
       "schema_version": 1,
       "run_id": "<uuid-or-timestamp-derived>",
       "generated": "<ISO-8601 UTC>",
       "dataset": "<dataset path>",
       "dataset_fingerprint": {
         "row_count": N,
         "ids": [...],                 # ordered
         "dataset_sha256": "<hex>"     # canonical SHA-256 of dataset content
       },
       "metrics": { ...compute_metrics output... },
       "rows": [
         {"id", "category", "passed", "failed_checks": [...],
          "stop_reason", "retries", "llm_call_count", "web_search_count"}
       ]
     }
     ```
   * `metrics` is stored as-is. Note: `compute_metrics` emits `(passed, total)`
     **tuples**; JSON round-trips these to lists. The delta helper must treat
     `[passed, total]` lists and `(passed, total)` tuples equivalently
     (normalize on load).
   * Add a small **pure** fingerprint helper, e.g.
     `dataset_fingerprint(rows, dataset_content)`, returning
     `{"row_count", "ids", "dataset_sha256"}`. It takes the already-loaded
     `rows` (for `row_count`/`ids`) and the canonical dataset content
     (bytes or text — pick one and document it) for `dataset_sha256`, and
     performs **no file I/O** itself, so content edits that leave ids
     unchanged still change the hash. Reading `dataset_path` to obtain the
     content is a separate thin wrapper (e.g. `read_dataset_content(path)`)
     that feeds this pure helper, keeping the hash computation deterministic
     and unit-testable without the filesystem.

2. **History persistence (thin I/O wrapper)**
   * Add `write_history_record(record, history_dir)` that ensures
     `history_dir` exists and derives the filename from `record["generated"]`:
     convert that ISO-8601 UTC timestamp into a filename-safe, sortable stamp
     and combine it with `record["run_id"]`, e.g.
     `20260613T141005Z__<run_id>.json`, so lexical sort == chronological sort.
     No separate `generated-as-filename` field is required on the record.
   * Add `load_latest_history_record(history_dir, *, exclude=None)` and
     `load_history_record(path)`; "latest" = highest-sorting filename, with the
     just-written file excluded when picking a baseline for the current run.
   * **Invalid-baseline handling (deterministic, testable):**
     * Explicit `--baseline <path>`: if the file is missing, not valid JSON,
       or has an incompatible/unknown `schema_version`, **fail fast** with a
       clear, specific error (do not silently fall back to auto-discovery).
     * Auto-discovery: iterate candidate records newest-first; if a candidate
       is unreadable, invalid JSON, or schema-incompatible, **skip it with a
       warning** (exception type only) and try the next-latest. If no valid
       record remains, treat the run as having **no baseline**.

3. **Delta computation (pure)**
   * Add `compute_delta(baseline_record, current_record)` returning a dict:
     ```
     {
       "baseline_run_id", "baseline_generated",
       "dataset_changed": bool,            # fingerprint differs
       "overall": {"passed": (old, new, delta), "total": (...)},
       "categories": {cat: (old, new, delta), ...},
       "checks": {check_name: (old, new, delta), ...},
       "rows": {
         "newly_passing": [ids], "newly_failing": [ids],
         "still_failing": [ids], "added": [ids], "removed": [ids]
       }
     }
     ```
   * `dataset_changed` is true when **any** `dataset_fingerprint` component
     differs (`row_count`, ordered `ids`, or `dataset_sha256`) — so a
     same-ids content edit is still flagged.
   * Transitions computed by joining baseline rows and current rows on `id`.
     Missing categories/checks on either side are treated as `0` so schema
     evolution does not crash the delta.

4. **Report rendering**
   * Add a `render_delta_section(delta)` helper and have `render_markdown`
     (or the runner) append a "## Delta vs. previous run" section after the
     Metrics section. When there is no baseline, render a single line:
     "No previous run found — this is the first recorded run." When
     `dataset_changed` is true, render a clear warning that aggregate deltas
     mix dataset changes with behavior changes.
   * Keep the existing report structure and all current sections byte-stable
     when no baseline exists and the section is the only addition.

5. **Runner + CLI wiring (`run_eval`, `main`)**
   * In `run_eval`: after `compute_metrics`, build the current record; select
     the baseline (explicit `--baseline` path, else auto-discover the latest
     valid record in `history_dir`); compute the delta; render the report
     including the delta section; then (unless `--no-history`) write the
     current record. Order: select the baseline *before* writing the new
     record so the new file is never its own baseline.
   * `--no-history` affects only the **write**: the baseline is still read and
     the delta section still renders when a baseline exists; with no baseline
     it renders the normal no-baseline message. No current record is written.
   * **History write status** is tracked and surfaced in the CLI summary (and,
     optionally, a one-line note in the report) as one of:
     * `written` — record persisted to `history_dir`,
     * `skipped_by_no_history` — `--no-history` was set,
     * `failed` — the write raised; warn using the exception **type only**
       (project convention) and still produce a valid Markdown report. A
       failed write must never abort the run or corrupt the report.
   * Add argparse flags: `--no-history` (store_true), `--baseline PATH`,
     and `--history-dir PATH` (default `evals/history/`).
   * A failed run row already degrades to `passed=False`; history must still
     record it faithfully (its `failed_checks` includes `run_completed`).

6. **Documentation + git convention (`evals/README.md`, `.gitignore`)**
   * Document `evals/history/` (append-only, machine-readable, metadata-only),
     the record schema and `schema_version`, the new flags, the history write
     status values, and how the delta section reads.
   * **Git convention (chosen):** generated history JSON is **gitignored by
     default** (add an ignore rule for `evals/history/*.json`). The directory
     may keep a `.gitkeep` so it exists in a fresh clone. Developers may
     *manually* commit a selected baseline record when they intentionally want
     a shareable reference point; the harness never stages or commits records.
     Because the ignore rule hides these files, committing a chosen baseline
     requires a **force-add**, e.g.
     `git add -f evals/history/<selected-baseline>.json`. Document this
     (including the `-f` requirement) in `evals/README.md`.

7. **Tests (`tests/evals/`, mocked/pure — no API keys)**
   * `dataset_fingerprint`: `dataset_sha256` changes when **row content**
     changes even if ids and `row_count` are identical; changes on id edits
     and row add/remove too.
   * `build_history_record`: shape, metadata-only (asserts no `answer`,
     `formatted_answer`, or `page_content` keys), failed-row capture,
     fingerprint embedded.
   * `compute_delta`: newly-passing/failing/still-failing/added/removed
     transitions; tuple-vs-list metric equivalence; missing category/check
     handled as 0; `dataset_changed` true when **any** fingerprint component
     (`row_count`, `ids`, or `dataset_sha256`) differs.
   * `write_history_record` / `load_latest_history_record`: round-trip via
     `tmp_path`; lexical filename ordering equals chronological; `exclude`
     skips the just-written file; empty/absent directory yields no baseline.
   * Baseline error paths: explicit `--baseline` to a missing / invalid-JSON /
     incompatible-schema file **fails fast** with a clear error; an
     auto-discovered invalid record is **skipped with a warning** and the next
     valid one is used (and if none are valid, no baseline).
   * `--no-history`: reads/uses an existing baseline and renders the delta, but
     writes **no** current record; reports `skipped_by_no_history`.
   * History write failure (simulated I/O error via `monkeypatch`): status is
     `failed`, a type-only warning is emitted, and a valid Markdown report is
     still produced (run does not abort).
   * `render_delta_section`: no-baseline line, dataset-changed warning,
     +/- formatting, per-row transition lists.
   * Regression: `render_markdown` output for the existing sections is
     unchanged when the delta section reports "no previous run".

## 7. Implementation plan

The feature is larger than a typical eval-check tweak, so it is staged into two
phases. **A later implementation agent may complete Phase 1 and stop**, leaving
the harness behavior byte-stable (no new files written, no new flags), because
Phase 1 adds only pure helpers and their tests.

0. Read `evals/run_eval.py` in full and `tests/evals/test_eval_harness.py` to
   match existing structure, naming, and the `(passed, total)` tuple
   conventions.

**Phase 1 — pure/deterministic helpers + tests only (no behavior change):**

1. Add the pure dataset fingerprint helper (`dataset_fingerprint(rows,
   dataset_content)` → `{row_count, ids, dataset_sha256}`), which takes the
   dataset content as an input rather than reading it.
2. Add the pure helpers in dependency order: `build_history_record`,
   `compute_delta`, `render_delta_section`. Keep them grouped with the existing
   pure "summarization / reporting" sections.
3. Add the mocked/pure tests for the above (fingerprint, record, delta,
   rendering) per Section 6.7.
4. Phase 1 scope boundaries:
   * pure/deterministic helpers and their tests only;
   * **no** `run_eval` integration;
   * **no** CLI flags;
   * **no** history file writes;
   * **no** generated history JSON files;
   * filesystem access only for test fixtures or thin input setup (e.g.
     reading a fixture to feed the pure helper), **not** runtime integration.

   The runner and report output remain unchanged after Phase 1.

**Phase 2 — I/O, CLI, integration, docs:**

5. Add the thin I/O wrappers (`write_history_record`,
   `load_latest_history_record`, `load_history_record`) with the
   invalid-baseline handling from Section 6.2, clearly separated from pure
   logic.
6. Wire baseline selection, delta computation, delta rendering, the conditional
   history write, and the write-status reporting into `run_eval`; add the
   `--no-history` / `--baseline` / `--history-dir` flags in `main`.
7. Add the Phase 2 tests (baseline error paths, `--no-history`, write-failure
   status, I/O round-trip) per Section 6.7.
8. Update `evals/README.md`; add the `.gitignore` rule for
   `evals/history/*.json` and an `evals/history/.gitkeep` per the chosen
   convention (Section 6.6).
9. Run safe validation commands (Section 9) and report per Section 12.

## 8. Safety constraints

Default constraints for this project:

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
  `passed = all(checks.values())` aggregation. The delta layer **reads** these;
  it does not alter them.
* History records are metadata-only: never serialize answer text,
  `page_content`, prompts, or raw graph state.
* Writing a history record must never crash a run: wrap the write so an I/O
  error logs a warning (exception type only, matching the project's
  type-only logging convention) and still leaves a valid report.
* A record is built and written only after evaluated rows and metrics exist
  (i.e. on a successful run as defined in the Summary). A command-level crash
  before metrics/report generation writes **no** record — never a partial or
  corrupt one. Per-row failures (`passed: false`) are still recorded normally.
* `--validate-only` must remain free of graph, API, and history I/O.

## 9. Validation plan

Safe validation commands:

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest tests/evals/ -q
uv run pytest tests/node/ tests/graph/ tests/evals/ -q
uv run python evals/run_eval.py --validate-only
```

Only run full eval if the feature explicitly needs end-to-end confirmation and
the user separately approves (the pure helpers are fully covered by mocked
tests, so this is not required to validate the logic):

```powershell
uv run python evals/run_eval.py --output evals/results.md
```

## 10. Acceptance criteria

* `uv run python evals/run_eval.py --validate-only` passes on the unchanged
  dataset and performs no history I/O.
* All existing `tests/evals/` tests pass unchanged.
* New mocked tests cover fingerprint behavior, record construction, delta
  computation (all five transition kinds + tuple/list equivalence + missing
  keys + dataset-changed), I/O round-trip and baseline selection, baseline
  error paths, `--no-history`, write-failure status, and delta rendering
  (including the no-baseline case).
* `dataset_sha256` changes when row **content** changes even if `ids` and
  `row_count` are unchanged, and `dataset_changed` is then true.
* A run with no prior history writes exactly one record (status `written`) and
  renders the "no previous run" delta line; the rest of the report is unchanged
  from today's structure.
* A second run produces a delta section that correctly reports aggregate and
  per-row changes against the first run, and does not pick its own freshly
  written record as the baseline.
* `--no-history` reads/uses an existing baseline and renders its delta but
  writes no record (status `skipped_by_no_history`); with no baseline it shows
  the no-baseline message. `--baseline PATH` compares against the given record.
* Explicit `--baseline` to a missing/invalid/incompatible file fails fast with
  a clear error; an auto-discovered invalid record is skipped with a warning
  and the next valid record is used.
* A simulated history write failure reports status `failed` (type-only
  warning) yet still produces a valid Markdown report; the run does not abort.
* History records contain no answer text, `page_content`, prompt, or raw-state
  fields (asserted by a test).
* `evals/README.md` documents the directory, schema, flags, write-status
  values, and delta section; `evals/history/*.json` is gitignored with a
  `.gitkeep` retained.
* No prompt/model/corpus/.env changes; no graph behavior changes; no dataset
  or existing-check changes.

## 11. Risks and calibration notes

* **LLM/retrieval/web variability:** because the eval drives real
  router/graders/generation, two runs of the *same* code can differ. Deltas
  will therefore mix genuine code changes with run-to-run noise. The delta
  section must be framed as "run vs. run", not "proof of regression"; document
  this caveat in `evals/README.md`.
* **Tuple/JSON round-trip:** `compute_metrics` uses `(passed, total)` tuples;
  JSON load yields lists. The delta helper must normalize, or comparisons and
  arithmetic will be subtly wrong. Covered by an explicit test.
* **Baseline selection ordering:** writing the new record before selecting the
  baseline would make a run its own baseline (all-zero deltas). Plan enforces
  select-then-write and an `exclude` guard; covered by a test.
* **Dataset drift:** adding/removing/reordering rows changes which `id`s exist;
  `added`/`removed` lists and the `dataset_changed` flag exist precisely so
  aggregate deltas are not silently misread across dataset edits. The
  `dataset_sha256` component additionally catches same-id content edits that
  `row_count`/`ids` alone would miss.
* **History growth:** one file per run accumulates unbounded. Because records
  are gitignored by default they do not bloat the repo, but the local
  directory still grows. Pruning/rotation is out of scope here — note it as a
  possible follow-up and keep records small (metadata-only).
* **Git convention drift:** since history is gitignored, a developer who wants
  a shared baseline must commit it manually; document this so a "missing"
  baseline on another machine is understood as expected, not a bug.
* **Possible stale documentation:** keep `evals/README.md` and any roadmap docs
  referencing report structure in sync with the new section and flags.
* **Overengineering:** resist trend lines, multi-baseline aggregation, or CI
  gating — single previous-vs-current delta is the agreed scope.
* **Privacy:** metadata-only records uphold the same discipline as the engine's
  trace JSON; a test asserts no content fields leak in.

## 12. Final report format

The implementing agent should report:

* Files changed.
* What was implemented.
* Tests run.
* Whether full eval was run.
* Whether API-key commands were run.
* Whether prompts/models/corpus/.env changed.
* Whether graph behavior changed.
* `git status --short`.
* `git diff --stat`.
* Known risks or follow-up work.
