# Richer Eval Expected Contains Checks

Status: Draft

Date: 2026-06-12

Type: Spec

## 1. Summary

Extend the eval harness's `expected_contains` check from a flat AND-list of
substrings into a richer, still fully deterministic check language:

* **Any-of groups**: an item in `expected_contains` may be a list of strings,
  meaning "the answer must contain at least one of these" (synonym/variant
  tolerance, e.g. `["VPN", "virtual private network"]`).
* **Negative assertions**: a new optional row field `expected_not_contains`
  (list of strings) asserts that none of the listed substrings appear in the
  answer (e.g. forbid a known-wrong threshold like `"$500"` on the expense row).

Plain string items keep their current AND semantics, so every existing row in
`evals/questions.jsonl` behaves identically with zero edits.

## 2. Background / Current behavior

The behavioral eval harness (`evals/run_eval.py`) applies deterministic
per-row checks — no LLM-as-judge. The `expected_contains` check today:

* Accepts only a flat `list[str]` (validated in `validate_rows`, around
  `evals/run_eval.py:175`).
* Passes only if **all** substrings appear in the formatted answer
  (`evaluate_row`, around `evals/run_eval.py:298`), after
  `normalize_for_contains` (NFKC Unicode normalization, typographic-hyphen
  folding, casefold) is applied to both sides.
* Is matched against `summary["formatted_answer"]` — the full formatted
  output including the `Sources:` section.

Limitations this spec addresses:

* **No synonym tolerance.** The model may correctly say "submit the access
  request form" while the row demands the exact word "manager"; row authors
  are forced to pick a single lowest-common-denominator substring, which makes
  rows either brittle (false failures) or weak (one trivial word).
* **No negative checks.** There is no way to assert the answer does *not*
  contain a known-wrong fact, a hallucination marker, or content that should
  have been declined. The existing `declined_or_caveated` check covers only
  one hard-coded pattern.

## 3. Goals

* Support any-of groups inside `expected_contains` (nested list items) with
  AND-across-items / OR-within-group semantics.
* Support a new optional `expected_not_contains: list[str]` row field
  (answer must contain none of them, after the same normalization).
* Keep every check deterministic and pure (unit-testable without API keys).
* Full backward compatibility: existing rows pass/fail exactly as before;
  flat string lists keep AND semantics.
* Validate the new shapes in `validate_rows` so `--validate-only` catches
  malformed rows (e.g. empty groups, non-string group members, empty strings).
* Report the new check in the results table and metrics (an
  `expected_not_contains` metric row mirroring the existing
  `expected_contains matches` row; failed checks already surface per row).
* Document the richer syntax in `evals/README.md`.

## 4. Non-goals

* No regex support, fuzzy matching, semantic similarity, or LLM-as-judge.
* No changes to `normalize_for_contains` behavior.
* No change to what text is matched (still the full formatted answer,
  including the `Sources:` section).
* No recalibration or editing of existing rows in `evals/questions.jsonl`
  (adding new rows or enriching rows with the new syntax is a separate,
  later calibration task requiring an approved full eval run).
* No changes to the graph, engine, nodes, chains, prompts, state schema,
  or stop_reason semantics.
* No deeper nesting than one level of any-of groups (no groups of groups).

## 5. Files to inspect

* `CLAUDE.md`
* `evals/run_eval.py` — validation (`validate_rows`), check application
  (`evaluate_row`), normalization (`normalize_for_contains`), metrics
  (`compute_metrics` / `check_counts`), and report rendering.
* `evals/questions.jsonl` — current row shapes (must remain valid unchanged).
* `evals/README.md` — dataset field documentation to update.
* `tests/evals/test_eval_harness.py` — existing mocked tests for validation,
  checks, metrics, and rendering; new tests go here (or in a sibling module
  following the same conventions).

## 6. Proposed changes

All changes live in `evals/run_eval.py`, `evals/README.md`, and
`tests/evals/`. No application or graph code is touched.

1. **Validation (`validate_rows`)**
   * `expected_contains` items may be either a non-empty `str` or a
     non-empty `list` of non-empty `str` (an any-of group). Reject empty
     strings, empty groups, and any other types with a precise per-row
     error message in the existing `f"{label}: ..."` style.
   * `expected_not_contains` must be `null` or a list of non-empty strings.

2. **Check application (`evaluate_row`)**
   * `expected_contains`: for each item — a plain string must be contained
     (current behavior); a group passes if at least one member is contained.
     All items must pass for the `expected_contains` check to pass.
     Normalization via `normalize_for_contains` applies to every needle and
     the haystack, exactly as today.
   * `expected_not_contains`: when present and non-empty, add a new check
     entry `checks["expected_not_contains"]` that is true only when no
     listed substring (normalized) appears in the normalized formatted
     answer. Rows without the field get no entry (consistent with how every
     other optional check works), so `passed = all(checks.values())` is
     unaffected for existing rows.

3. **Metrics and report**
   * Add `expected_not_contains_matches` via the existing `check_counts`
     helper and a corresponding row in the metrics table of the rendered
     report, next to `expected_contains matches`.
   * The per-row "failed checks" column already lists failing check names
     generically; no change needed there beyond the new check existing.

4. **Documentation**
   * `evals/README.md`: document the item-or-group syntax for
     `expected_contains`, the new `expected_not_contains` field, the AND/OR
     semantics, and a short JSON example.

5. **Tests (`tests/evals/`)** — mocked/pure, no API keys:
   * Validation: accepts flat lists (regression), accepts mixed
     string/group lists, rejects empty groups, empty strings, non-string
     group members, doubly nested groups, and non-list
     `expected_not_contains`.
   * Checks: group passes on any member, fails when no member matches;
     mixed AND/OR rows; `expected_not_contains` passes when absent from the
     answer, fails when present; normalization (case, typographic hyphens)
     applies to both new shapes; rows without the new fields produce no new
     check entries.
   * Metrics/rendering: `expected_not_contains_matches` counts only rows
     that have the check; report table includes the new row.

## 7. Implementation plan

1. Read `evals/run_eval.py` in full and `tests/evals/test_eval_harness.py`
   to match existing structure, naming, and error-message style.
2. Extend `validate_rows` for the two new shapes (smallest diff; keep the
   existing flat-list branch behavior intact).
3. Extend `evaluate_row` with group-aware `expected_contains` logic and the
   new `expected_not_contains` check.
4. Add the metric entry in `compute_metrics` and the table row in the
   report-rendering function.
5. Add the mocked tests described above.
6. Update `evals/README.md`.
7. Run safe validation commands (Section 9) and report per Section 12.

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

* Do not edit existing rows in `evals/questions.jsonl`; the harness must
  remain backward compatible with the dataset as-is.
* Do not change `normalize_for_contains` or `summarize_state`.
* Do not change existing check names or `passed` aggregation semantics
  (`passed = all(checks.values())`).

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

Only run full eval if the feature explicitly needs it and the user separately
approves (not required for this change, since no rows are edited):

```powershell
uv run python evals/run_eval.py --output evals/results.md
```

## 10. Acceptance criteria

* `uv run python evals/run_eval.py --validate-only` passes on the unchanged
  `evals/questions.jsonl`.
* All existing `tests/evals/` tests pass unchanged (no expectation edits).
* New mocked tests cover: group any-of pass/fail, mixed string/group rows,
  `expected_not_contains` pass/fail, normalization on the new shapes, and
  every new validation rejection case.
* A flat-string `expected_contains` list produces byte-identical check
  results to the current implementation.
* Metrics output includes `expected_not_contains_matches`, and the rendered
  report includes the matching table row.
* `evals/README.md` documents the new syntax with an example.
* No prompt/model/corpus/.env changes; no graph behavior changes; no
  existing eval rows changed.

## 11. Risks and calibration notes

* **Eval row calibration risk:** richer syntax makes it tempting to enrich
  existing rows immediately; that requires a full eval run to recalibrate
  and is explicitly deferred. New syntax is unused by the dataset until a
  separate, approved calibration pass.
* **Semantics ambiguity:** nested-list-means-any-of must be documented
  clearly, or future row authors may assume nested lists are AND-groups.
  The README example and validation errors mitigate this.
* **JSON shape drift:** `expected_contains` becomes a heterogeneous list;
  validation must stay strict (reject deeper nesting and empty values) so
  typos fail at `--validate-only` rather than silently passing checks.
* **Overengineering:** resist adding regex/weights/thresholds; the two
  additions here cover the known gaps with minimal surface.
* **Possible stale documentation:** `evals/README.md` and any roadmap docs
  referencing the `expected_contains` shape must be updated together.
* Retrieval instability, web/API variability, and LLM output variability are
  unaffected by this change (checks are pure), but they still influence any
  later calibration run that uses the new syntax.

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
