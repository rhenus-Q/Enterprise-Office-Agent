# Richer Eval Expected Contains Checks — Implementation Report

Status: Implemented

Date: 2026-06-12

Type: Implementation Report

Source spec: `docs/roadmap/spec/richer-eval-expected-contains-checks.md` (not read — plan was sufficient)

Source plan: `docs/roadmap/plan/richer-eval-expected-contains-checks-plan.md`

## 1. Summary

Extended the eval harness with two deterministic additions: any-of groups
inside `expected_contains` (a list item means "at least one of these must
appear") and a new `expected_not_contains` check field. Existing flat
`expected_contains` lists and all 24 dataset rows are byte-identical in
behavior.

## 2. Files changed

### Code

- `evals/run_eval.py`

### Tests

- `tests/evals/test_eval_harness.py`

### Documentation

- `evals/README.md`

## 3. What was implemented

### `evals/run_eval.py`

1. **`_valid_expected_contains_item(item)` helper** — returns `True` if item
   is a non-empty `str` or a non-empty `list` of non-empty `str`s. Rejects
   empty strings, empty groups, non-string group members, and deeper nesting.

2. **`validate_dataset`** — updated `expected_contains` validation to use the
   new helper (accepts mixed `str | list[str]` items); added `expected_not_contains`
   validation (must be `null` or a `list` of non-empty strings).

3. **`evaluate_row`** — updated `expected_contains` check to handle group items
   via a ternary in the generator (`isinstance(item, str)` → must contain,
   else `any(...)` over group members). Added new `expected_not_contains` check
   (only when field is present and non-empty) that passes when none of the
   needles appear after `normalize_for_contains`.

4. **`compute_metrics`** — added `"expected_not_contains_matches":
   check_counts("expected_not_contains")`.

5. **`render_markdown`** — added `| expected_not_contains matches | ... |` row
   in the metrics table, immediately after `expected_contains matches`.

### `tests/evals/test_eval_harness.py`

Added 22 new tests:

**Validation (11 tests):** accepts mixed group/string lists; flat list
regression; rejects empty group, empty top-level string, empty in-group
string, non-string group member, doubly nested group; accepts valid
`expected_not_contains`; rejects non-list and empty-string `expected_not_contains`.

**Checks (10 tests):** group passes on any one member; group fails when no
member matches; mixed AND/OR row (three assertions); `expected_not_contains`
passes when absent, fails when present, absent from checks when field omitted;
group normalization (case + typographic hyphens); `expected_not_contains`
normalization.

**Metrics/rendering (3 tests):** `expected_not_contains_matches == (1, 1)` for
a fixture with one passing check; `(0, 0)` for the existing fixture with no
such rows; rendered report includes `"expected_not_contains matches"` string.

### `evals/README.md`

Updated `expected_contains` field description to explain item-or-group syntax
and AND-across/OR-within semantics. Added `expected_not_contains` field entry.
Added a concrete JSON example row using both features.

## 4. What was intentionally not changed

- Prompts: unchanged.
- Model names: unchanged.
- Corpus documents: unchanged.
- Graph behavior: unchanged.
- Graph routing: unchanged.
- Graph nodes: unchanged.
- `stop_reason` semantics: unchanged.
- Fallback policy semantics: unchanged.
- `.env` / `.env.example`: unchanged.
- `evals/questions.jsonl`: zero row edits.
- `normalize_for_contains`, `summarize_result`: unchanged.
- Existing check names and `passed` aggregation: unchanged.

## 5. Validation run

- `uv run ruff check .` — passed.
- `uv run ruff format --check .` — passed (53 files already formatted).
- `uv run mypy` — passed (no issues in 5 source files).
- `uv run pytest tests/evals/ -q` — **57 passed** in 0.19 s.
- `uv run pytest tests/node/ tests/graph/ tests/evals/ -q` — **326 passed** in 6.91 s.
- `uv run python evals/run_eval.py --validate-only` — passed (Dataset OK: 24 rows).

Full eval: **not run** (no rows were edited; explicitly deferred per the plan).

## 6. Risks and follow-up work

- **Full eval recalibration:** the new syntax is available but no existing rows
  use it yet. A separate, approved calibration pass is needed to enrich rows
  with any-of groups or `expected_not_contains` checks.
- **Dataset enrichment:** the plan explicitly defers enriching `questions.jsonl`
  to a later pass.

## 7. Final git state

```text
 M evals/README.md
 M evals/run_eval.py
 M tests/evals/test_eval_harness.py
?? docs/roadmap/claude-command-workflow-review.md
?? docs/roadmap/plan/phase-2b-dev-hygiene-plan.md
?? docs/roadmap/plan/phase-3a-3b-eval-v2-plan.md
?? docs/roadmap/plan/richer-eval-expected-contains-checks-plan.md
?? docs/roadmap/spec/richer-eval-expected-contains-checks.md
```

```text
 evals/README.md                  |  34 ++++++++-
 evals/run_eval.py                |  35 ++++++++-
 tests/evals/test_eval_harness.py | 155 +++++++++++++++++++++++++++++++++++++++
 3 files changed, 218 insertions(+), 6 deletions(-)
```

## 8. Final confirmation

- No prompt changes.
- No model-name changes.
- No corpus changes.
- No `.env` or `.env.example` changes.
- No graph behavior changes.
- Full eval not run.
- `ingestion.py` not run.
- `tests/chains/` not run.
- No commit created automatically.
