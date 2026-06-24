# Architecture Decision Records

Architecture Decision Records (ADRs) capture the significant design decisions
in this project: the context that forced a choice, the decision made, its
consequences, the trade-offs accepted, and the alternatives deliberately not
chosen. They document *why* the code is the way it is — the part git history
and code comments don't preserve.

Each ADR is short (roughly a page), uses a fixed template (Status / Date /
Context / Decision / Consequences / Trade-offs / Alternatives considered),
and describes behavior that is actually implemented — no aspirational
architecture.

## Index

| ADR | Title | Decision in one line |
|---|---|---|
| [001](001-stop-reason.md) | Explicit `stop_reason` values | Every non-clean run ending records a machine-readable reason; the CLI maps it to an honest user-facing caveat. |
| [002](002-web-search-privacy-mode.md) | `WEB_SEARCH_ENABLED` privacy mode | One toggle guarantees user questions never reach an external search API; quality gates stay active. |
| [003](003-meaningful-retries.md) | Meaningful retries | At `temperature=0`, retries must change the input: grounding feedback for not-grounded, query rewriting for not-useful. |
| [004](004-web-result-relevance-gate.md) | Web-result relevance gate | Every web result is individually relevance-graded against the original question before it can reach generation. |
| [005](005-run-budgets.md) | Per-run cost/latency budgets | Counted LLM calls, web searches, and web-result grades are capped per run; exhaustion stops the run with a caveat. |
| [006](006-graceful-degradation.md) | Graceful degradation | External dependency failures degrade or stop safely with a `stop_reason` instead of crashing; nothing ungraded or unverified is presented as normal. |
| [007](007-answer-provenance.md) | Deterministic answer provenance | The `Sources:` section is post-run formatting of document metadata — the LLM never generates citations. |
| [008](008-synthetic-enterprise-corpus.md) | Synthetic AcmeCorp corpus | A fictional internal-policy corpus replaces tutorial pages so the enterprise features operate on enterprise-shaped content. |
| [009](009-eval-harness.md) | Deterministic eval harness | Behavioral evals with deterministic checks (stop reasons, provenance, counters, substrings); not run in CI. |
| [010](010-prompt-injection-defense.md) | Prompt-injection defense | The generation prompt explicitly treats retrieved content as untrusted evidence, never as instructions — a first-line mitigation, not a complete solution. |
| [011](011-web-fallback-policy.md) | Configurable web-fallback policy | `WEB_FALLBACK_POLICY` (conservative/aggressive/disabled, default conservative): answer from remaining relevant local docs first; web fallback only when none remain. |
| [012](012-prompt-injection-hardening.md) | Prompt-injection hardening | Extends ADR 010: Security rules on the control-plane chains (router/graders/rewriter), explicit `[BEGIN/END UNTRUSTED DOCUMENT n]` delimiters in the generation context, and deterministic graph-level containment tests. |

## Conventions

- Status is `Accepted` for all current ADRs; superseded decisions would be
  marked `Superseded by ADR-XXX` rather than edited or deleted.
- New ADRs take the next number and follow the same template.
- ADRs reference real files and constants (`graph/consts.py`,
  `MAX_RETRIES = 5`, budget defaults 30/5/15) so they can be checked against
  the code they describe.
