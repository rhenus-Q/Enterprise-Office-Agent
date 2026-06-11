# ADR 001: Explicit stop_reason values for every non-clean run ending

Status: Accepted

Date: 2026-06-11

## Context

The graph has many ways to end without a fully verified answer: privacy mode
blocks a needed web search, the retry limit is reached while a quality gate
still fails, a per-run budget is spent, or an external dependency fails. Early
versions simply returned whatever `generation` held, which made a failed
answer indistinguishable from a successful one — the worst possible behavior
for an assistant whose core promise is "never present an unvetted answer as a
success."

We needed a mechanism that (a) tells the *caller* exactly why a run ended,
(b) lets the CLI attach an honest user-facing caveat, and (c) is testable
without parsing prose.

## Decision

`GraphState` carries a `stop_reason: str` field (`""` = clean finish). All
non-clean endings record a machine-readable value defined in
`graph/consts.py`: `web_search_disabled`, `max_retries_not_grounded`,
`max_retries_not_useful`, `budget_exhausted`, `retrieval_error`,
`web_search_error`, `generation_error`, and `tool_error`.

Because conditional edges in this design are pure (read-only), terminal
outcomes that need a state write go through small **notice nodes**
(`web_search_disabled_notice`, `max_retries_*_notice`,
`budget_exhausted_notice`, `tool_error_notice`) whose only job is one
`stop_reason` write. Mid-run degradations (e.g. a failed Tavily call) are
written directly by the node that caught the failure. Presentation is fully
separated: `main.py` maps each reason to a caveat string
(`STOP_REASON_NOTES`) appended after the answer; the graph never formats
user-facing text.

Nodes only write `stop_reason` on failure, so a successful step never
clobbers a reason recorded earlier in the run.

## Consequences

- Every failure mode has exactly one observable, asserted-on value; the
  mocked graph tests check `result["stop_reason"]` instead of matching answer
  text.
- The CLI can warn users precisely ("did not pass the anti-hallucination
  check" vs. "web search is disabled") rather than generically.
- New failure modes follow a known recipe: add a constant, record it at the
  failure site (node or notice node), add one caveat string in `main.py`.
- The eval harness (`evals/run_eval.py`) reuses the same field for
  deterministic behavioral checks.

## Trade-offs

- `stop_reason` is a **single final value**, not a warning list. If retrieval
  fails and the run later exhausts retries, the terminal notice node
  overwrites `retrieval_error` — last writer wins, and the earlier
  degradation is no longer visible in the final state. We accepted this
  because the reason that actually ended the run is the most actionable one,
  and a multi-warning list would touch every node and every caveat test for
  marginal benefit at the current scale.
- A string field is weaker than an enum; typos are caught only by tests that
  import the shared constants.
- The notice nodes add graph vertices that do nothing but write one field —
  topology noise accepted to keep routing functions pure.

## Alternatives considered

- **Silent termination** (return whatever the last generation was): rejected
  — it presents failed answers as successes.
- **Encoding warnings in the answer text** inside the graph: rejected — it
  mixes presentation into orchestration, breaks "judge the generation, not
  the boilerplate" for the graders, and is untestable except by string
  matching.
- **Raising exceptions to the caller**: rejected — exhausted retries and
  privacy stops are expected outcomes, not errors, and the run still has a
  best-effort answer worth delivering with a caveat.
- **A list of accumulated warnings**: deferred, not rejected — it is the
  natural evolution if multiple simultaneous degradations need surfacing, but
  it was not worth the schema and test churn yet.
