# ADR 004: Relevance-grade every web result before it reaches generation

Status: Accepted

Date: 2026-06-11

## Context

Locally retrieved chunks pass a per-chunk relevance gate (`retrieval_grader`)
before generation. Web search results originally did not: whatever Tavily
returned was concatenated into a `Document` and appended to the context. That
gave the *least* trusted input in the system — arbitrary public web content —
a free pass around the gate that curated internal chunks must clear. SEO
spam, off-topic pages, or tangentially related news could contaminate the
context, and the grounding gate would then happily verify an answer against
that contamination.

## Decision

Inside the `websearch` node, each Tavily result is graded **individually**
with the existing `retrieval_grader` against the **original question** (the
user's intent — even when the search itself used a rewritten retry query).
Only results graded relevant are merged into the single web-supplement
`Document` (tagged with the `web_search` source marker); irrelevant results
are dropped. Malformed responses (Tavily errors arriving as plain strings,
entries missing `content`) are skipped defensively, and a fully unusable
response leaves the documents unchanged — the workflow continues rather than
crashing.

The check lives *inside* the node, not as new graph edges: keeping it local
avoids creating a new, ungoverned loop in the topology. Grading volume is
capped by `MAX_WEB_RESULTS_TO_GRADE` (default 15, ADR 005); once spent,
remaining results are dropped **ungraded and unused** — the conservative
direction, since unvetted content must never reach generation.

## Consequences

- External content faces the same quality bar as internal content; the
  symmetry is easy to explain and to test.
- Reusing `retrieval_grader` meant zero new prompts or chains — one grader
  defines "relevant" for the whole system.
- The grounding gate downstream now verifies answers against vetted context
  only, which makes its verdict meaningful.
- Mocked node tests can drive every case (all relevant, mixed, none,
  malformed, budget-capped) deterministically.

## Trade-offs

- **One extra LLM call per web result** (up to 3 per search with
  `max_results=3`), adding latency and cost to every web round. Bounded by
  the grading budget and counted against the LLM-call budget.
- Sequential per-result grading; no batching. Acceptable at 3 results per
  search, and batched grading is a recorded future improvement.
- A grader false-negative throws away a genuinely useful result; with few
  results per search this can leave the supplement empty and push the run
  toward an honest insufficient-context outcome rather than a better answer.
  We prefer that failure direction over contamination.
- Grading against the original question (not the rewritten query) can drop
  results the rewrite deliberately sought; chosen because the answer is
  ultimately judged against the original question too.

## Alternatives considered

- **Trusting Tavily's own ranking**: rejected — relevance-to-query is not
  relevance-to-intent, and the project's trust model treats external content
  as the least trusted input, not pre-vetted.
- **A separate grading node with graph edges**: rejected — it would add a new
  conditional surface to the topology for what is conceptually an internal
  detail of "do a web search well."
- **Batching all results into one grading call**: deferred — cheaper, but a
  structured multi-verdict output is a new chain contract; per-result calls
  reuse the existing single-document grader unchanged.
- **Embedding-similarity pre-filtering instead of an LLM grader**: rejected
  for now — it would introduce a second relevance definition diverging from
  the one used for local chunks, for modest savings at k=3.
