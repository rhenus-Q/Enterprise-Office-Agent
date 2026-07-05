# ADR 003: Meaningful retries — change the input, not just the attempt count

Status: Accepted

Date: 2026-06-11

## Context

The graph retries failed quality gates: a not-grounded answer triggers
regeneration, and a grounded-but-not-useful answer triggers another web
search round. All chains run at `temperature=0` for determinism — which means
a naive retry that replays identical inputs mostly reproduces the identical
failure. The original retry loop did exactly that: it burned up to
`MAX_RETRIES = 5` generations re-asking the same question over the same
context and reliably failing the same gate five times.

A retry is only worth its cost if something changes between attempts.

## Decision

Each retry path injects a concrete input change through a small pass-through
node spliced into the pre-existing cycle:

- **Not grounded → `add_grounding_feedback` → `generate`.** The node writes a
  fixed corrective instruction into `retry_feedback` ("use only facts
  explicitly supported by the documents; if they are insufficient, say so").
  `generate_answer` folds it into the question input — the prompt template
  and chain input variables are unchanged. Once set, the stricter instruction
  persists for the remainder of the run.
- **Not useful → `rewrite_query` → `websearch` → `generate`.** The
  `query_rewriter` chain produces a more specific search query informed by
  the previous (not useful) answer and writes it to `search_query`. The
  `websearch` node searches with it, and the fresh web supplement **replaces**
  the stale one rather than stacking near-duplicates, so the next grounding
  check judges genuinely new context. Relevance grading still uses the
  original question — the user's intent, not the rewritten query.

Both helper nodes are linear pass-throughs: no new decision points, so no new
uncontrolled loops. Every cycle still passes through `generate`, which
increments the single `retries` counter that `MAX_RETRIES` caps.

## Consequences

- Retries have a real chance of succeeding: the second generation sees a
  stricter instruction; the second search sees a sharper query and different
  results.
- Loop accounting stayed simple — one counter, one cap, checked after grading
  so even the final generation gets a full quality check.
- The seams are independently testable: mocked tests assert the feedback
  reaches the generation input and the rewritten query reaches the web tool.

## Trade-offs

- **More graph complexity**: two extra nodes, two extra state fields
  (`retry_feedback`, `search_query`), and more edge cases to test.
- **More LLM calls**: each not-useful retry adds a query-rewrite call (and
  the web-result grading calls that follow the new search). These are
  counted against the per-run LLM budget (ADR 005), which bounds the cost.
- The grounding feedback is a **fixed instruction** — the hallucination
  grader returns a boolean, not a rationale, so the retry cannot target the
  specific unsupported claim. Rationale-bearing feedback is a known future
  improvement, not current behavior.
- `retry_feedback` persisting for the whole run means later generations stay
  strict even after an unrelated web-search round; acceptable, since the
  stricter instruction is never harmful to groundedness.

## Alternatives considered

- **Raising temperature on retries**: rejected — it trades a hallucination
  failure for nondeterminism, makes tests flaky, and violates the project
  rule of keeping `temperature=0` and model behavior stable.
- **Rewriting the user's question itself**: rejected — all three graders
  judge against the original question; mutating it would corrupt the very
  standard the gates measure against. Only the *search query* is rewritten.
- **Changing the prompt templates per retry**: rejected — folding feedback
  into the existing question input achieves the same effect without altering
  prompts or chain signatures, which other tests and behavior depend on.
- **No retries (fail fast on first gate failure)**: rejected — single-shot
  failures are common and often recoverable; the bounded loop with honest
  exhaustion reporting (ADR 001) is strictly better for answer quality.
