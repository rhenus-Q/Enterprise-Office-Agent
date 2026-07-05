# ADR 009: Lightweight deterministic eval harness

Status: Accepted

Date: 2026-06-11

> **Note:** This ADR records the **v1** eval harness. The later **v2**
> expansion — a larger dataset, richer deterministic expectations, and
> metadata-only history/delta tracking — is documented in
> [ADR 013](013-eval-harness-v2-expansion.md). This ADR is preserved as the
> original decision and is intentionally not rewritten.

## Context

The project has 170+ mocked unit and graph tests proving that *code paths*
work: routing branches, retry loops, budget stops, failure degradation. None
of them say whether the *system behaves well on realistic questions* — does a
VPN question actually answer from the corpus, does an out-of-corpus question
actually reach the web, does fabrication bait actually get declined, does
privacy mode actually hold under real model judgments? Tests and evals answer
different questions, and a repository claiming enterprise-assistant behavior
should demonstrate both.

The first version needed to be cheap, reproducible in its scoring, and honest
about what it can and cannot measure.

## Decision

A small harness under `evals/`:

- **`questions.jsonl`** — 15 rows across four behavioral categories: 5
  answerable from the AcmeCorp corpus (with checkable facts like "18
  months"), 5 requiring web fallback, 3 insufficient-context fabrication
  baits, 2 privacy-mode guarantees. Rows carry optional expectations:
  `expected_stop_reason`, `expected_source_type`, `expected_contains`.
- **`run_eval.py`** — runs each row through the real compiled graph (seeding
  `web_search_enabled` per row through graph state, exactly as `main.py`
  does — `.env` is never modified), then applies **deterministic checks
  only**: stop-reason match, source-type match from document metadata,
  case-insensitive expected substrings against the formatted answer, an
  automatic `web_search_count == 0` assertion for every web-disabled row, and
  two category rules (web-fallback rows must actually use a web source after
  ≥ 1 search; insufficient-context rows must decline or end with a caveat).
  No LLM-as-judge in this version.
- Output: per-category pass counts, check match rates, average retries and
  tracked LLM calls (labeled "tracked" because the counter omits router and
  grader calls — an operational counter, not billing), total web searches —
  printed to stdout and written to `evals/results.md` as Markdown.
- The insufficient-context rows run with web search disabled **on purpose**:
  with web enabled the graph would correctly answer them via fallback, which
  would test routing rather than fabrication resistance.
- **Not in CI.** The full run drives the real router, graders, and generation
  (OpenAI) and possibly Tavily: it needs secrets, costs money, and is
  nondeterministic. CI runs only mocked suites. The harness's pure helpers
  (loading, validation, checks, metrics, rendering) are unit-tested without
  API calls in `tests/evals/`, and `--validate-only` checks the dataset
  format with zero API-adjacent imports.

## Consequences

- Behavioral regressions (a prompt or corpus change breaking routing or
  refusal) become measurable with one command instead of anecdotes.
- Scoring is reproducible: given the same run outputs, the checks always
  produce the same verdicts — failures are diagnosable from the report's
  per-row failed-check column.
- The harness reuses the system's own observability (`stop_reason`, source
  metadata, budget counters), so it doubles as a check that those signals are
  actually useful.

## Trade-offs

- **Deterministic checks are less nuanced than LLM-as-judge.** Substring
  checks can fail on a correct paraphrase ("a year and a half" vs "18
  months") and pass on a wrong answer that happens to contain the token.
  Accepted for v1: cheap, explainable, zero judge-model variance; judged
  metrics are a recorded future improvement layered on top, not a
  replacement.
- The end-to-end runs themselves are still nondeterministic (model judgments,
  live web results), so pass rates can vary between runs even with frozen
  checks — the report is a snapshot, not a CI gate.
- 15 questions is a smoke-test-sized dataset: enough to demonstrate each
  behavior category, not enough for statistical claims.
- Category rules encode expectations in runner code rather than purely in
  data; acceptable at this size, worth revisiting if the dataset grows.

## Alternatives considered

- **LLM-as-judge scoring**: deferred — adds cost, a second model dependency,
  and judge variance before the basics existed; the deterministic layer is
  the foundation it would sit on.
- **Asserting behavior only in mocked tests**: rejected — mocks pin the
  graders' answers, so they cannot measure whether the real graders make good
  judgments.
- **Running evals in CI**: rejected — secrets in CI, per-push cost, and flaky
  failures from nondeterminism; `--validate-only` and the `tests/evals/`
  helper tests give CI-safe coverage of the harness itself.
- **An external eval service or dashboard**: rejected — over-engineering for
  a 15-question dataset; JSONL + a stdlib runner + a Markdown report keep the
  whole harness reviewable in one sitting.
