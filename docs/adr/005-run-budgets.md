# ADR 005: Per-run cost and latency budgets

Status: Accepted

Date: 2026-06-11

## Context

The self-correction design multiplies LLM calls: routing, per-chunk grading,
generation, two post-generation graders, query rewrites, web searches, and
per-result web grading — looped up to `MAX_RETRIES = 5` times. The retry cap
bounds *iterations*, but nothing bounded *spend within an iteration's
machinery*, and a future change (or a pathological configuration) could make
a single question arbitrarily expensive or slow. For a portfolio/demo project
run against a paid API, an unbounded worst case is also a personal-cost
hazard: one bad loop is a real bill.

## Decision

Three counters live in `GraphState` and are incremented **only in nodes**
(the only legal state writers): `llm_call_count` (generations, query
rewrites, web-result grades), `web_search_count` (actual Tavily calls), and
`web_result_grading_count`. Three env-configurable budgets in
`graph/config.py` cap them — `MAX_LLM_CALLS_PER_RUN` (default 30),
`MAX_WEB_SEARCHES_PER_RUN` (5), `MAX_WEB_RESULTS_TO_GRADE` (15). Invalid or
non-positive env values fall back to defaults, so a budget can never be
accidentally disabled.

Checks are pure reads, placed where they prevent further spend:

- The **LLM-call budget is checked at the top of `grade_generation`, before
  the graders run** — a spent budget must not spend more, so the final
  answer goes out ungraded with a `budget_exhausted` caveat saying exactly
  that.
- The **web-search budget** is checked in the not-useful branch (looping
  toward a search that cannot run is pure waste → stop with the budget
  caveat) plus a defensive guard inside `websearch` itself (skip the search,
  documents unchanged).
- The **grading budget** is enforced inside `websearch`'s loop: remaining
  results are dropped ungraded and unused; the run continues.

Deliberate accounting tradeoff: hallucination/answer-grader calls run inside
a conditional edge (which cannot write state) and are bounded at two per
generation, so they are not individually counted — capping counted calls
transitively caps them. Failed external attempts (e.g. a Tavily timeout)
still increment their counters, so a persistently failing dependency cannot
drive an unbounded retry loop (ADR 006).

## Consequences

- Every run has a hard cost ceiling independent of routing, retries, or
  failures; defaults sit above the retry loop's worst case, so default
  behavior is unchanged and the budgets act purely as a backstop.
- Cost-sensitive deployments tighten three env vars without code changes.
- Counters double as observability: the eval harness reports average LLM
  calls and total web searches per run.

## Trade-offs

- **Budget exhaustion may stop a recoverable run.** The next retry might have
  passed; we deliberately prefer a bounded, caveated stop over open-ended
  spend, and the caveat tells the user the answer is unverified rather than
  wrong.
- The uncounted-grader accounting means `llm_call_count` understates true API
  calls by a bounded factor — fine for a backstop, inadequate for billing.
- Three knobs is more configuration surface; mitigated by safe defaults and
  fallback parsing.
- Counter increments thread through node return values, adding boilerplate
  to every counting node.

## Alternatives considered

- **Relying on `MAX_RETRIES` alone**: rejected — it bounds loop iterations,
  not the cost inside each iteration, and provides no web-specific or
  grading-specific control.
- **Wall-clock timeouts**: rejected — they cut runs mid-step with no clean
  state to caveat, and are flaky in tests; call counts are deterministic and
  mockable.
- **Token-based budgets**: rejected for now — accurate token accounting
  requires response metadata plumbing through every chain; call counts are a
  cruder but sufficient proxy at this scale.
- **Global (cross-run) quotas**: out of scope — the CLI is single-turn,
  per-question; a service wrapper would be the right place for tenant-level
  quotas.
