# Richer Eval Expected Contains Checks — Implementation Plan

Status: Planned

Date: 2026-06-12

Type: Plan

Source spec: `docs/roadmap/spec/richer-eval-expected-contains-checks.md`

## 1. Spec summary

The eval harness's `expected_contains` check is currently a flat AND-list of
substrings: every string must appear in the formatted answer (after
`normalize_for_contains` normalization). This forces row authors to pick a
single lowest-common-denominator substring, making rows either brittle
(false failures on valid wording) or weak (one trivial word), and there is no
way to assert that an answer does *not* contain a known-wrong fact.

The spec extends the check language with two deterministic additions:

* **Any-of groups** inside `expected_contains`: an item may be a list of
  strings, meaning "at least one of these must appear" (OR within the group,
  AND across items). Plain string items keep current semantics.
* **`expected_not_contains`** (new optional row field, `list[str]`): the
  check passes only when none of the listed substrings appear in the
  normalized formatted answer.

What must not change: existing rows in `evals/questions.jsonl` (zero edits;
byte-identical check results for flat string lists), `normalize_for_contains`,
`summarize_state`, existing check names, `passed = all(checks.values())`
aggregation, and anything outside the eval harness — no graph, engine, node,
chain, prompt, model, state-schema, or corpus changes. No regex, fuzzy
matching, LLM-as-judge, or nesting deeper than one group level.

## 2. Current system understanding

Verified from `evals/run_eval.py` and `tests/evals/test_eval_harness.py`:

* `validate_rows` validates optional per-row fields with per-row
  `f"{label}: ..."` error messages. `expected_contains` is accepted only as
  a flat `list[str]` (around `evals/run_eval.py:175-179`).
  `expected_not_contains` does not exist yet.
* `evaluate_row` (around `evals/run_eval.py:277-346`) builds a
  `checks` dict; optional checks add an entry only when the row has the
  field, and `passed = all(checks.values())`. The `expected_contains` check
  (around line 298) normalizes both the haystack
  (`summary["formatted_answer"]` — the full formatted output including the
  `Sources:` section) and every needle via `normalize_for_contains` (NFKC,
  typographic-hyphen folding, casefold), then requires all needles present.
* `compute_metrics` uses a `check_counts(check_name)` helper (around line
  358) that counts pass/total only over rows that have the check; the
  rendered Markdown report has a metrics table row per check (e.g.
  `expected_contains matches`, around line 421) and a per-row results table
  whose "failed checks" column lists failing check names generically.
* `tests/evals/test_eval_harness.py` is fully mocked (no API keys): `_row`
  and `_summary` helper factories, validation tests
  (`test_validate_flags_bad_optional_field_types`,
  `test_validate_accepts_new_optional_eval_v2_fields`, ...), per-check tests
  (`test_expected_contains_is_case_insensitive_and_checks_formatted_answer`,
  unicode-hyphen variants, ...), `_evaluated_fixture` for metrics, and
  `test_render_markdown_includes_metrics_and_every_row` for rendering.
* The shipped dataset (24 rows) uses only flat string lists, e.g.
  `"expected_contains": ["manager"]` — it must validate and evaluate
  identically after the change.

## 3. Files to inspect during implementation

### Required files

* `CLAUDE.md`
* `docs/roadmap/spec/richer-eval-expected-contains-checks.md`
* `evals/run_eval.py` (full read: validation, checks, metrics, rendering)
* `tests/evals/test_eval_harness.py` (full read: match helper/test style)
* `evals/README.md` (the field documentation to extend)

### Optional files

* `evals/questions.jsonl` (only to confirm existing shapes still validate;
  do not edit)
* `graph/formatting.py` (only if unsure what `formatted_answer` contains)

## 4. Proposed implementation steps

1. **Extend `validate_rows` in `evals/run_eval.py`.**
   * Goal: accept `expected_contains` items that are either a non-empty
     `str` or a non-empty `list` of non-empty `str`; accept
     `expected_not_contains` as `null` or a list of non-empty strings.
     Reject empty strings, empty groups, non-string group members, and
     deeper nesting, each with a precise `f"{label}: ..."` message.
   * Files: `evals/run_eval.py` only.
   * Avoid: changing `REQUIRED_FIELDS`, other field validations, or the
     error-message style.
2. **Extend `evaluate_row`.**
   * Goal: group-aware `expected_contains` (string item → must contain;
     list item → at least one member contained; check passes when all items
     pass), and a new `checks["expected_not_contains"]` entry (only when the
     field is present and non-empty) that is true when no listed substring
     appears. All needles and the haystack go through
     `normalize_for_contains`, exactly as today.
   * Files: `evals/run_eval.py` only.
   * Avoid: touching `normalize_for_contains`, `summarize_state`, other
     checks, or the `passed` aggregation.
3. **Extend metrics and report rendering.**
   * Goal: add `expected_not_contains_matches` via the existing
     `check_counts` helper and a matching metrics-table row next to
     `expected_contains matches`. The per-row "failed checks" column needs
     no change.
   * Files: `evals/run_eval.py` only.
4. **Add mocked tests in `tests/evals/test_eval_harness.py`.**
   * Goal, following the existing `_row`/`_summary` style:
     * Validation: accepts mixed string/group lists; flat lists still
       accepted (regression); rejects empty group, empty string (top-level
       and in-group), non-string group member, doubly nested group, and
       non-list `expected_not_contains`.
     * Checks: group passes on any one member; group fails when no member
       matches; mixed AND/OR row; `expected_not_contains` passes when
       absent and fails when present; normalization (case, typographic
       hyphens) applies to group members and `expected_not_contains`
       needles; a row without the new field produces no
       `expected_not_contains` entry in `checks`.
     * Metrics/rendering: extend `_evaluated_fixture` (or add a row) so
       `expected_not_contains_matches` counts only rows that have the
       check, and the rendered report includes the new table row.
   * Avoid: editing or weakening existing tests; calling any real service.
   * Validation after step: `uv run pytest tests/evals/ -q` (safe, mocked).
5. **Update `evals/README.md`.**
   * Goal: document the item-or-group syntax, `expected_not_contains`,
     the AND-across-items / OR-within-group semantics, and one short JSON
     example row using both features.
6. **Run safe validation (Section 8) and report per Section 12.**

## 5. Files expected to change

* `evals/run_eval.py`
* `tests/evals/test_eval_harness.py`
* `evals/README.md`

## 6. Files that should not change

* `evals/questions.jsonl` (explicitly: zero row edits)
* `graph/` (everything: graph, engine, state, config, consts, nodes, chains,
  formatting)
* `main.py`, `ingestion.py`
* prompt text, model names
* corpus documents (`data/acmecorp_internal_docs/`)
* `.env`, `.env.example`
* `tests/node/`, `tests/graph/`, `tests/chains/`, `tests/conftest.py`
* `pyproject.toml`, `.pre-commit-config.yaml`

## 7. Safety constraints

Default constraints:

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

Feature-specific constraints (from the spec):

* Do not edit existing rows in `evals/questions.jsonl`.
* Do not change `normalize_for_contains` or `summarize_state`.
* Do not change existing check names or `passed` aggregation semantics.
* Keep all checks deterministic and pure (unit-testable without API keys).

## 8. Validation plan

This section defines what the implementing agent should run after
implementation. The plan creation step must not run these commands.

```powershell
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest tests/evals/ -q
uv run pytest tests/node/ tests/graph/ tests/evals/ -q
uv run python evals/run_eval.py --validate-only
```

Full eval is **not required** for this change (no rows are edited) and is
explicitly deferred; run it only if the user separately approves:

```powershell
uv run python evals/run_eval.py --output evals/results.md
```

## 9. Acceptance criteria

* `uv run python evals/run_eval.py --validate-only` passes on the unchanged
  `evals/questions.jsonl`.
* All pre-existing `tests/evals/` tests pass without expectation edits.
* New tests cover every case listed in step 4 and pass.
* A flat-string `expected_contains` list produces identical check results to
  the current implementation (regression tests prove it).
* Metrics include `expected_not_contains_matches` and the rendered report
  includes the matching table row.
* `evals/README.md` documents the new syntax with an example.
* `ruff check`, `ruff format --check`, and `mypy` pass.
* Only the three files in Section 5 are changed; no prompt/model/corpus/.env
  changes; no graph behavior changes; full eval explicitly deferred.

## 10. Risks and calibration notes

* **Eval row calibration risk:** enriching existing rows with the new syntax
  needs a full eval recalibration run and is out of scope; the dataset uses
  only flat lists until a separate, approved calibration pass.
* **Semantics ambiguity:** nested-list-means-any-of could be misread as an
  AND-group by future row authors; the README example and strict validation
  errors are the mitigation — write both carefully.
* **Validation strictness:** the heterogeneous `expected_contains` list must
  reject deeper nesting and empty values so typos fail at `--validate-only`
  rather than silently weakening a check.
* **mypy:** the item type becomes `str | list[str]`; keep annotations
  consistent with the file's existing typing style so `uv run mypy` stays
  green.
* **Overengineering risk:** no regex, weights, thresholds, or scope options;
  only the two additions in the spec.
* **Documentation drift:** update `evals/README.md` in the same change;
  retrieval/web/LLM variability does not affect these pure checks.

## 11. Recommended implementation prompt

> Read `CLAUDE.md`, then read
> `docs/roadmap/plan/richer-eval-expected-contains-checks-plan.md` and follow
> it exactly. Read the source spec
> (`docs/roadmap/spec/richer-eval-expected-contains-checks.md`) only if the
> plan is insufficient on its own. Implement only the planned scope: any-of
> groups in `expected_contains` and the new `expected_not_contains` check in
> `evals/run_eval.py`, new mocked tests in
> `tests/evals/test_eval_harness.py`, and documentation in
> `evals/README.md`. Do not edit `evals/questions.jsonl`, any `graph/` code,
> prompts, model names, corpus documents, or `.env`/`.env.example`. Run only
> the safe validation commands in the plan's Section 8 (no full eval, no
> `tests/chains/`, no API-key-requiring commands), do not commit, and report
> final status using the plan's Section 12 format.

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
