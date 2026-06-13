# Eval History and Delta Reporting — Implementation Report

Status: Implemented

Date: 2026-06-13

Type: Implementation Report

Source spec: not read — implemented from plan

Source plan: `docs/roadmap/plan/eval-history-delta-reporting-plan.md`

## 1. Summary

Added eval history records and run-over-run delta reporting to the behavioral
eval harness. Both Phase 1 (pure helpers + tests) and Phase 2 (I/O, CLI,
integration, docs) are complete.

Every full eval run now persists a compact, metadata-only JSON record to
`evals/history/`. On subsequent runs the harness auto-discovers the most recent
prior record as a baseline, computes deltas (overall pass counts, per-category
and per-check changes, and per-row transitions), and renders a "Delta vs.
previous run" section in the Markdown report. Three new CLI flags
(`--no-history`, `--baseline PATH`, `--history-dir PATH`) control the behavior.

## 2. Files changed

### Code

- `evals/run_eval.py` — added pure helpers (`dataset_fingerprint`,
  `build_history_record`, `_as_pair`, `compute_delta`, `render_delta_section`),
  thin I/O wrappers (`read_dataset_content`, `write_history_record`,
  `load_history_record`, `load_latest_history_record`), `HistoryBaselineError`
  exception class, updated `render_markdown` (new keyword-only `delta_lines`
  parameter), updated `run_eval` (new `history_dir`, `baseline`, `no_history`
  kwargs), updated `main` (three new argparse flags). New imports: `hashlib`,
  `uuid`.

### Tests

- `tests/evals/test_eval_history.py` — new test module (106 tests covering:
  fingerprint behavior, record construction with metadata-only assertion,
  delta computation for all five transition kinds + tuple/list equivalence +
  missing keys + `dataset_changed`, I/O round-trip + baseline selection with
  `exclude` + empty/absent dir, baseline error paths, `--no-history`,
  write-failure status, delta rendering, and `render_markdown` regression).

### Documentation

- `evals/README.md` — extended with history directory, record schema +
  `schema_version`, new CLI flags, write-status values, delta section
  description, run-vs-run caveat, and git convention (gitignore +
  force-add instructions).

### Other

- `.gitignore` — added `evals/history/*.json` ignore rule with a comment
  explaining the force-add workflow.
- `evals/history/.gitkeep` — new tracked placeholder so the directory exists
  in a fresh clone.

## 3. What was implemented

### Phase 1 — pure helpers

**`dataset_fingerprint(rows, dataset_content)`** — takes already-loaded rows
and raw dataset bytes; returns `{row_count, ids, dataset_sha256}`. No file I/O.
`read_dataset_content(path)` is the thin I/O wrapper that feeds it.

**`build_history_record(evaluated, metrics, dataset_path, fingerprint, *, timestamp, run_id)`**
— builds a JSON-serializable dict with `schema_version: 1`, metadata fields,
the full `compute_metrics` output, and per-row `{id, category, passed,
failed_checks, stop_reason, retries, llm_call_count, web_search_count}`. Never
stores answer text, `page_content`, prompts, or raw graph state.

**`_as_pair(value)`** — normalizes `(p, t)` tuples and `[p, t]` lists to
`(int, int)` so `compute_delta` handles both JSON-loaded and native-Python
metric values correctly.

**`compute_delta(baseline_record, current_record)`** — pure function returning
`{baseline_run_id, baseline_generated, dataset_changed, overall, categories,
checks, rows}`. `dataset_changed` is true when any fingerprint component
(`row_count`, `ids`, or `dataset_sha256`) differs. Transitions are computed by
joining on `id`; missing categories/checks are treated as 0.

**`render_delta_section(delta)`** — returns a list of Markdown lines. `None`
renders the "no previous run" case; a valid delta dict renders aggregate tables
and per-row transition lists with a `dataset_changed` warning when applicable.

### Phase 2 — I/O, CLI, integration

**`write_history_record(record, history_dir)`** — derives a sortable filename
from the ISO-8601 `generated` field + `run_id` (e.g. `20260613T100000Z__<uuid>.json`);
creates `history_dir` if absent; writes UTF-8 JSON.

**`load_history_record(path)`** — loads and validates `schema_version == 1`;
raises `ValueError` for incompatible schema, `FileNotFoundError` / `JSONDecodeError`
for missing/corrupt files.

**`load_latest_history_record(history_dir, *, exclude=None)`** — iterates
candidates newest-first (lexicographic == chronological); skips invalid files
with a type-only warning; returns `None` if directory absent or no valid record.

**`run_eval` integration** — after `compute_metrics`: builds the current record;
selects the baseline *before* writing (so the new record is never its own
baseline); computes delta; renders report with the delta section; conditionally
writes the record. History write status (`written` / `skipped_by_no_history` /
`failed`) is tracked and printed; a write failure never aborts the run.

**`render_markdown`** — new keyword-only `delta_lines=None` parameter. When
`None`, output is byte-identical to the pre-history format (existing tests
unaffected). When provided, the delta section is inserted after the Metrics
disclaimer and before `## Per-question results`.

**`main`** — three new argparse flags: `--no-history` (`store_true`),
`--baseline PATH`, `--history-dir PATH` (default `evals/history/`). A
`HistoryBaselineError` from an explicit `--baseline` that fails is caught and
prints a clear error (exit 1). `--validate-only` is untouched and performs no
history I/O.

## 4. What was intentionally not changed

- **Prompts** — unchanged.
- **Model names** — unchanged (`gpt-5-mini`).
- **Corpus documents** — unchanged.
- **Graph behavior** — unchanged (no edits to `graph/`).
- **Graph routing** — unchanged.
- **Graph nodes** — unchanged.
- **`stop_reason` semantics** — unchanged.
- **Fallback policy semantics** — unchanged.
- **`.env` / `.env.example`** — unchanged.
- **`evals/questions.jsonl`** — unchanged.
- **Existing pure-helper contracts** — `compute_metrics` output shape/keys/tuples,
  `evaluate_row`, `summarize_result`, `normalize_for_contains`, `validate_dataset`,
  existing check names, and `passed = all(checks.values())` — all untouched.
- **Existing `render_markdown` output** — byte-stable when `delta_lines=None`
  (confirmed by regression test `test_render_markdown_without_delta_lines_is_stable`).
- **`tests/evals/test_eval_harness.py`** — unchanged; all 66 pre-existing tests pass.

## 5. Validation run

- `uv run ruff check .` — passed (after fixing import sort and two unused imports).
- `uv run ruff format --check .` — passed (after formatting).
- `uv run mypy` — passed (no issues in 5 source files).
- `uv run pytest tests/evals/ -q` — **106 passed** (66 pre-existing + 40 new).
- `uv run pytest tests/node/ tests/graph/ tests/evals/ -q` — **375 passed**.
- `uv run python evals/run_eval.py --validate-only` — passed (Dataset OK: 24 rows).

Full eval was **not run** (requires real API keys; pure helpers are fully covered
by mocked tests).

## 6. Risks and follow-up work

- **LLM/retrieval/web variability:** deltas reflect run-to-run noise as well as
  code changes; framed as "run vs. run" in the README caveat.
- **History growth:** one file per run accumulates unbounded in `evals/history/`.
  Files are gitignored so the repo stays clean, but the local directory grows.
  Pruning/rotation is out of scope; consider a follow-up.
- **Git convention:** shared baselines require `git add -f`; documented in README.
- **Full eval still needs separate approval** before running to confirm end-to-end
  integration (the delta section rendering with real graph output).

## 7. Final git state

```text
 M .gitignore
 M evals/README.md
 M evals/run_eval.py
?? docs/roadmap/plan/eval-history-delta-reporting-plan.md
?? docs/roadmap/spec/eval-history-delta-reporting.md
?? evals/history/
?? tests/evals/test_eval_history.py
```

```text
 .gitignore        |   6 +
 evals/README.md   | 101 +++++++++++++-
 evals/run_eval.py | 395 +++++++++++++++++++++++++++++++++++++++++++++++++++++-
 3 files changed, 494 insertions(+), 8 deletions(-
```

New untracked files: `evals/history/.gitkeep`,
`tests/evals/test_eval_history.py`, and the plan/spec files under `docs/roadmap/`.

## 8. Final confirmation

- No prompt changes.
- No model-name changes.
- No corpus changes.
- No `.env` or `.env.example` changes.
- No graph behavior changes.
- Full eval was not run.
- `ingestion.py` was not run.
- `tests/chains/` was not run.
- No commit was created automatically.
