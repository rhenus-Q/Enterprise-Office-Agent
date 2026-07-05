# ADR 013: Eval harness v2 — expanded dataset, richer checks, history and delta

Status: Accepted

Date: 2026-06-30

Extends: [ADR 009](009-eval-harness.md) (lightweight deterministic eval
harness). ADR 009 records the original v1 harness and is preserved as-is; this
ADR documents the v2 expansion built on top of it.

## Context

ADR 009 established a deliberately small, deterministic behavioral harness: 15
rows across four categories (`local_corpus`, `web_fallback`,
`insufficient_context`, `privacy_mode`), a handful of optional expectations
(`expected_stop_reason`, `expected_source_type`, `expected_contains`), and a
Markdown report — explicitly a smoke test, not a statistical instrument, and
never run in CI. ADR 009 named several of its own limits as future work:
substring checks that cannot express provenance or multi-signal expectations,
category rules encoded in runner code, and no run-over-run tracking.

Two capabilities have since landed in the codebase and were not covered by an
ADR:

- **The configurable web-fallback policy (ADR 011)** added behavior the v1
  dataset could not exercise: conservative-stays-local, aggressive-escalates,
  conservative-web-when-empty, and disabled-declines. Proving the policy knob
  actually changes behavior requires paired rows that differ only in policy —
  a new category and per-row policy expectations.
- **Multi-document synthesis** (answers that must draw on two named corpus
  documents) had no representation, so nothing measured whether provenance
  spanned the right sources.

Layering these onto v1 required the dataset to carry richer, still-deterministic
expectations, and made run-over-run comparison worth the cost: with more rows
and more checks, "did anything regress since the last run?" is no longer
answerable by eyeballing two reports.

## Decision

Expand the harness in place — same `evals/` layout, same "deterministic checks
only, not in CI" posture as ADR 009 — along four axes.

### 1. Expanded dataset and categories

`evals/questions.jsonl` grows to **24 rows across six categories**. The four
original categories are retained and two are added:

- `local_corpus` — answerable from the AcmeCorp corpus.
- `web_fallback` — requires routing to web search.
- `insufficient_context` — fabrication baits that must decline or caveat.
- `privacy_mode` — web-disabled guarantees (zero web searches).
- **`multi_document`** — answers that must synthesize two named corpus
  documents, with provenance spanning both.
- **`policy_fallback`** — rows that pin the web-fallback policy (ADR 011)
  per row, including paired rows that share a question but differ only in
  `web_fallback_policy` to prove the knob changes behavior.

### 2. Richer deterministic expectations

Rows may now carry, in addition to the v1 fields:

- **`expected_contains` with AND/OR group semantics.** Each list item is either
  a string (required substring) or a list of strings (an OR group — at least one
  must match). All items must be satisfied, so the field expresses AND-of-ORs.
- **`expected_not_contains`** — substrings that must be absent (e.g. an answer
  must not surface a fabricated specific).
- **`expected_source_titles`** — local document titles that must appear in the
  run's provenance (drawn from `Document.metadata`, web sources excluded).
- **`expected_min_local_sources`** — minimum count of distinct local source
  titles, the deterministic signal that multi-document synthesis actually
  happened.
- **`expected_web_search_count`** — an exact integer, or an object with `min`
  / `max` bounds, checked against the tracked web-search counter.
- **`web_fallback_policy`** (per-row) — pins the effective policy for the run;
  a `policy_applied` check asserts the graph resolved that policy into state.

All string matching runs through a shared normalizer (NFKC, typographic
dash/hyphen variants folded to ASCII, whitespace collapsed, casefolded) so
typographic variation in model output does not fail an otherwise-correct answer.
The v1 category rules remain: web-disabled rows are hard-checked for zero web
searches, `web_fallback` rows must use a web source after ≥ 1 search, and
`insufficient_context` rows must decline or end with a stop-reason caveat. A row
passes only when every applicable check passes.

### 3. Metadata-only history and delta tracking

Each full run writes an append-only history record and renders a "Delta vs.
previous run" section in the report:

- **Metadata-only history records** (one JSON per full run) under
  `evals/history/`. A record holds the run id, timestamp, dataset fingerprint,
  aggregate metrics, and per-row `{id, category, passed, failed_checks,
  stop_reason, retries, llm_call_count, web_search_count}`. It **never** stores
  answer text, `page_content`, prompts, raw graph state, or API keys. The
  harness only ever *writes new* records — it never edits or deletes existing
  ones.
- **Dataset fingerprinting** — a `{row_count, ids, dataset_sha256}` fingerprint
  (SHA-256 over the raw file bytes) so a dataset edit that leaves ids unchanged
  still registers as a change.
- **Baseline comparison** — the latest prior record is auto-discovered as the
  baseline (newest-first by filename, which sorts chronologically), or an
  explicit `--baseline <path>` overrides it. The freshly written record is never
  its own baseline. When the two fingerprints differ, the delta section prints a
  warning that aggregate deltas mix dataset changes with behavior changes.
- **Row transitions** — the delta classifies rows into **newly passing**,
  **newly failing**, **still failing**, **added**, and **removed**, alongside
  per-category and per-check baseline/current/delta tables.

### 4. Reporting improvements

The Markdown report gains:

- **Per-category pass metrics** for all six categories.
- **Per-check match metrics** (`stop_reason`, `source_type`,
  `expected_contains`, `expected_not_contains`, `source_titles`,
  `min_local_sources`, `web_search_count`, `policy_applied`).
- **Average tracked LLM calls**, with an explicit report note that this is the
  graph's budgeted operational counter (generations, query rewrites,
  web-result grades) — router and grader calls are not individually tracked, so
  it is **not total LLM usage and not billing-accurate cost accounting**.
- The inserted delta section (above), placed after the metrics.

### CI boundary (unchanged from ADR 009)

- The **real end-to-end eval stays outside CI**: it drives the live
  router/graders/generation (OpenAI) and possibly Tavily, so it needs secrets,
  costs money, and is nondeterministic. Run it deliberately and only with
  explicit approval.
- **CI-safe surfaces remain CI-safe.** The harness's pure helpers — dataset
  loading/validation, per-row checks, metric aggregation, fingerprinting,
  history record building, delta computation, and Markdown/delta rendering — are
  unit-tested with no API-adjacent imports in `tests/evals/`
  (`test_eval_harness.py`, `test_eval_history.py`). `--validate-only` checks the
  dataset format (including all v2 fields) and exits without touching the graph
  or writing any history.

## Consequences

- The dataset now exercises the fallback-policy matrix (ADR 011) and
  multi-document provenance, so behavior those features introduced is
  measurable rather than assumed.
- Provenance and multi-signal expectations are expressible in data
  (`expected_source_titles`, `expected_min_local_sources`, AND/OR
  `expected_contains`, `expected_not_contains`), moving expectation-authoring out
  of runner code and into the rows.
- Regressions are diagnosable run-over-run: the delta section names exactly which
  rows and checks changed, and the fingerprint flags when a dataset edit — not a
  behavior change — explains a metric shift.
- The history trail stays privacy-safe by construction: metadata-only records
  mean a shared or committed baseline never leaks answer text, corpus content,
  prompts, or secrets (consistent with the observability rules in ADR 007 / ADR
  012).
- The harness continues to reuse the system's own signals (`stop_reason`, source
  metadata, budget counters), so it doubles as a check that those signals remain
  useful.

## Trade-offs

- **Still deterministic, still not LLM-as-judge.** The v1 trade-off stands: the
  normalizer reduces false failures on typographic variation but cannot judge a
  correct paraphrase, and a wrong answer that happens to contain a token can
  still pass. Judged metrics remain recorded future work layered on top, not a
  replacement.
- **End-to-end runs remain nondeterministic** (model judgments, live web
  results), so pass rates and deltas vary between runs even with frozen checks.
  The report is a snapshot and the delta is directional, not a CI gate.
- **24 rows is still smoke-test-sized** — enough to demonstrate each behavior
  category, including the policy matrix, not enough for statistical claims.
- **Tracked LLM calls are an operational counter, not a bill.** The report
  states this explicitly; it must not be read as cost accounting.
- **History accumulates files.** Records are append-only by design; pruning is a
  manual/operational concern. `evals/history/*.json` is gitignored by default
  (the dir is tracked via `.gitkeep`); a known-good baseline is shared only by
  deliberate `git add -f`.

## Alternatives considered

- **Keeping the v1 dataset and checks unchanged** — rejected: it could not
  express the fallback-policy matrix (ADR 011) or multi-document provenance, so
  those behaviors would stay untested.
- **Rewriting ADR 009 to describe v2 as if v1 never existed** — rejected: the
  v1 decision (why the harness started small, deterministic, and out of CI) is
  worth preserving as history. This ADR extends it; ADR 009 carries a pointer
  note instead of being edited away.
- **Storing full answers/traces in history for richer diffs** — rejected: it
  would leak answer text, corpus content, and prompts into a potentially shared
  file, violating the metadata-only observability posture (ADR 007 / ADR 012).
  Per-row check outcomes and counters are enough to compute the deltas that
  matter.
- **Running the expanded eval (or a judged eval) in CI** — rejected, same
  reasons as ADR 009: secrets in CI, per-push cost, and flaky nondeterministic
  failures. `--validate-only` plus the `tests/evals/` helper tests keep the
  harness itself under CI-safe coverage.
- **An external eval service, dashboard, or database for history** —
  rejected: over-engineering at this size. JSONL dataset + stdlib runner +
  append-only JSON records + a Markdown report keep the whole harness reviewable
  in one sitting.
