# ADR 002: WEB_SEARCH_ENABLED privacy mode

Status: Accepted

Date: 2026-06-11

## Context

The assistant answers questions over internal enterprise documents — the
synthetic AcmeCorp corpus of policies and playbooks (VPN access, incident
response, data retention, …). Its CRAG design uses Tavily web search in three
places: entry routing, fallback when retrieved chunks are graded irrelevant,
and a supplement when a grounded answer is judged not useful.

In a compliance-sensitive deployment every one of those paths is a data-leak
risk: the user's question text (which may itself reveal internal incidents,
finances, or personnel matters — "who got paged for the Sev-1 last night?")
is transmitted to a third-party API. Some deployments must be able to
guarantee that questions never leave the local environment.

## Decision

A `WEB_SEARCH_ENABLED` environment variable (parsed in `graph/config.py`;
`false`/`0`/`no`/`off` disable, anything else — including unset — preserves
full behavior) is seeded into graph state by `main.py` as
`web_search_enabled`. When `False`:

- `route_question` returns `retrieve` **without calling the router LLM** —
  the question is not even sent to OpenAI for routing on this path, and
  every question goes retrieval-first.
- `decide_to_generate` never falls back to web search; generation proceeds
  with whatever relevant chunks remain, or returns the deterministic
  insufficient-context answer with none.
- `grade_generation` ends a grounded-but-not-useful run through the
  `web_search_disabled` notice (with a CLI caveat) instead of searching; the
  query rewriter is never invoked.
- The `websearch` node is unreachable — asserted by end-to-end mocked tests
  that drive worst-case scenarios and verify zero web-tool calls.

All grounding and usefulness quality gates remain active in privacy mode; the
mode reduces capability, never rigor. (One later, mode-independent exception:
the deterministic insufficient-context answer skips the graders — it contains
no claims to verify. In privacy mode it still ends through the
`web_search_disabled` notice, so the caveat is preserved.)

## Consequences

- A hard, testable guarantee: with the flag off, no code path constructs or
  invokes the Tavily tool, and the eval harness's privacy rows additionally
  assert `web_search_count == 0`.
- The toggle is per-process via env, and per-run via state — the eval harness
  exercises privacy rows in the same process as web-enabled rows without
  touching `.env`.
- Failure handling composes with it: a retriever failure in privacy mode
  degrades to the insufficient-context answer rather than the web fallback.

## Trade-offs

- **Answers may be incomplete.** Questions whose answers live outside the
  corpus get the honest "not enough information" response or a
  `web_search_disabled` caveat instead of a web-sourced answer. We chose
  honest refusal over silent capability loss — the caveat says exactly what
  was sacrificed and why.
- The flag gates the entire run; there is no per-question override in the
  CLI. Acceptable for the current single-toggle deployment story.
- Skipping the router LLM in privacy mode means out-of-scope questions waste
  one retrieval + grading round before being declined.

## Alternatives considered

- **Network-level blocking only** (firewall/egress rules): rejected as the
  *sole* mechanism — the graph would still attempt calls, fail, and surface
  confusing `web_search_error` caveats instead of a clear policy message.
  Defense in depth at the network layer remains compatible.
- **Removing web search entirely**: rejected — the fallback is genuinely
  valuable for deployments that allow it, and the CRAG correction loop is a
  core part of the design.
- **Routing to retrieval but still allowing the not-useful web supplement**:
  rejected — a half-privacy mode that leaks question text on exactly the
  hardest questions is worse than either extreme.
- **Per-question user prompt ("allow web for this question?")**: deferred —
  reasonable UX for an interactive product, but it complicates the CLI and
  the guarantee story ("never" is easier to verify than "only when
  approved").
