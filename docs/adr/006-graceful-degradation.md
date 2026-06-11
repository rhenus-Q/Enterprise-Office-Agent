# ADR 006: Graceful degradation on external dependency failures

Status: Accepted

Date: 2026-06-11

## Context

The graph depends on five external surfaces: the Chroma retriever, Tavily
search, the generation LLM, three LLM graders, and the query-rewriter LLM.
Originally any of them raising (timeout, API error, malformed response)
crashed the whole run with a stack trace — unacceptable for an assistant
whose other safeguards (privacy mode, budgets, retry caps) all promise
controlled endings. A crash is also the *least* informative failure: the user
learns nothing about what was attempted or what survived.

## Decision

Every external call is wrapped in `try/except Exception` at its existing call
site, with two failure classes:

**Degrade and continue** (the run keeps going with reduced capability, and
the node records a `stop_reason` so the final answer carries an honest
caveat even if it later passes every gate):

- *Retriever/Chroma failure* → empty documents + `web_search=True`, reusing
  the existing irrelevant-docs fallback path (`retrieval_error`); in privacy
  mode this degrades to the deterministic insufficient-context answer.
- *Tavily failure* → continue with local documents only
  (`web_search_error`); the failed attempt still counts against the
  web-search budget so a flaky API cannot loop forever.
- *Query-rewriter failure* → `search_query=""`, meaning the next search uses
  the original question (`tool_error`); the retry loop continues fully gated.
- *Relevance-grader failure* (local chunk or web result) → the **ungraded
  content is dropped** — unvetted content never reaches generation
  (`tool_error`); remaining items are still graded.

**Stop immediately** (continuing would present unverified output as normal):

- *Generation failure* → the node substitutes a deterministic safe placeholder
  answer and records `generation_error`; `grade_generation` checks this
  before anything else and routes straight to `END` — a failed generation is
  never graded, retried, or presented as a normal answer.
- *Hallucination/answer-grader failure* → these run inside the pure
  `grade_generation` edge, which cannot write state, so a `tool_error`
  outcome routes to the small `tool_error_notice` node and then `END`; the
  answer is delivered explicitly flagged as unverified.

Console banners log **only the exception type** (`---WEB SEARCH FAILED
(TimeoutError)...---`), never the message, which could carry keys, paths, or
URLs. Nodes write `stop_reason` only on failure, so a clean step never
clobbers an earlier recorded reason.

One refinement on persistence: the degrade-and-continue `tool_error` is
**transient** — the run is built to recover from it. When the final answer
subsequently passes both quality gates, the stale warning no longer describes
the terminal outcome, so the success path runs through a
`clear_transient_tool_error` pass-through that resets it to `""` (a fully
successful answer never ships with an error caveat). The asymmetry is
deliberate: `retrieval_error` / `web_search_error` persist even on success
because an entire evidence source was unavailable, and the stop-immediately
`tool_error` (verification failed) never reaches the cleanup node.

## Consequences

- The graph cannot crash on dependency failure; every path ends at `END`
  with an answer (possibly the safe placeholder) plus an accurate caveat.
- Conservative trust is preserved under failure: nothing ungraded is used,
  nothing unverified is presented as verified.
- All failure paths are deterministic and fully covered by mocked tests,
  including end-to-end runs proving a failed generation is never graded.

## Trade-offs

- **Degraded answers may be incomplete** — a retrieval failure answered from
  the web (or declined in privacy mode) is honest but worse than the healthy
  path. The caveat makes the degradation visible rather than silent.
- Broad `except Exception` can mask genuine bugs inside a seam as a polite
  caveat; mitigated by logging the exception type and by unit tests pinning
  the healthy paths.
- A single `stop_reason` reports the last failure, not all of them (ADR 001).
- No automatic retry/backoff of the failed call itself — one failure means
  degradation. Client-level retries could be added inside the lazy factories
  later without touching the graph.

## Alternatives considered

- **Letting exceptions propagate** to the CLI: rejected — crashes, no
  partial answer, raw stack traces to users.
- **A global try/except around `app.invoke`**: rejected — by the time the
  exception surfaces, the in-flight state is lost, so no degraded
  continuation or precise caveat is possible. (The eval harness wraps
  invocations defensively anyway, as a last resort.)
- **Retry-with-backoff at every call site**: rejected for now — it multiplies
  worst-case latency and interacts badly with the run budgets; the
  budget-counted single attempt keeps the math simple.
- **Routing grader failures as "not grounded"** (forcing a retry): rejected —
  it spends budget re-generating when the *verifier* is down, and the retry
  would face the same broken grader.
