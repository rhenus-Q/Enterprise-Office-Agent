# Architecture Decision Records

Architecture Decision Records (ADRs) capture the significant design decisions
in this project: the context that forced a choice, the decision made, its
consequences, the trade-offs accepted, and the alternatives deliberately not
chosen. They document *why* the code is the way it is — the part git history
and code comments don't preserve.

Each ADR is focused, uses a fixed template (Status / Date /
Context / Decision / Consequences / Trade-offs / Alternatives considered),
and describes behavior that is actually implemented — no aspirational
architecture.

## Index

ADRs are grouped by the module they primarily concern; a decision that spans
the whole repository is classified as repository-wide and lives directly in
`docs/adr/`.
[ADR 014](enterprise_rag/014-enterprise-rag-package-and-office-agent-placeholder.md)
is listed under Enterprise RAG because its primary decision is packaging the
completed RAG implementation into `enterprise_rag/`; the `office_agent/` portion
was only a reserved empty placeholder at that time.

### Enterprise RAG ADRs (001–014)

| ADR | Title | Decision in one line |
|---|---|---|
| [001](enterprise_rag/001-stop-reason.md) | Explicit `stop_reason` values | Every non-clean run ending records a machine-readable reason; the CLI maps it to an honest user-facing caveat. |
| [002](enterprise_rag/002-web-search-privacy-mode.md) | `WEB_SEARCH_ENABLED` privacy mode | One toggle guarantees user questions never reach an external search API; quality gates stay active. |
| [003](enterprise_rag/003-meaningful-retries.md) | Meaningful retries | At `temperature=0`, retries must change the input: grounding feedback for not-grounded, query rewriting for not-useful. |
| [004](enterprise_rag/004-web-result-relevance-gate.md) | Web-result relevance gate | Every web result is individually relevance-graded against the original question before it can reach generation. |
| [005](enterprise_rag/005-run-budgets.md) | Per-run cost/latency budgets | Counted LLM calls, web searches, and web-result grades are capped per run; exhaustion stops the run with a caveat. |
| [006](enterprise_rag/006-graceful-degradation.md) | Graceful degradation | External dependency failures degrade or stop safely with a `stop_reason` instead of crashing; nothing ungraded or unverified is presented as normal. |
| [007](enterprise_rag/007-answer-provenance.md) | Deterministic answer provenance | The `Sources:` section is post-run formatting of document metadata — the LLM never generates citations. |
| [008](enterprise_rag/008-synthetic-enterprise-corpus.md) | Synthetic AcmeCorp corpus | A fictional internal-policy corpus replaces tutorial pages so the enterprise features operate on enterprise-shaped content. |
| [009](enterprise_rag/009-eval-harness.md) | Deterministic eval harness | Behavioral evals with deterministic checks (stop reasons, provenance, counters, substrings); not run in CI. |
| [010](enterprise_rag/010-prompt-injection-defense.md) | Prompt-injection defense | The generation prompt explicitly treats retrieved content as untrusted evidence, never as instructions — a first-line mitigation, not a complete solution. |
| [011](enterprise_rag/011-web-fallback-policy.md) | Configurable web-fallback policy | `WEB_FALLBACK_POLICY` (conservative/aggressive/disabled) controls when retrieval paths escalate to web; the default conservative policy is local-first, and disabled blocks local-path fallback with a caveat. |
| [012](enterprise_rag/012-prompt-injection-hardening.md) | Prompt-injection hardening | Extends ADR 010: Security rules on the control-plane chains (router/graders/rewriter), explicit `[BEGIN/END UNTRUSTED DOCUMENT n]` delimiters in the generation context, and deterministic graph-level containment tests. |
| [013](enterprise_rag/013-eval-harness-v2-expansion.md) | Eval harness v2 expansion | Extends ADR 009: 24-row/6-category dataset (adds `multi_document`, `policy_fallback`), richer deterministic checks (AND/OR contains, not-contains, source titles, min-local-sources, web-search-count, policy), and metadata-only history + delta tracking; still deterministic, still not in CI. |
| [014](enterprise_rag/014-enterprise-rag-package-and-office-agent-placeholder.md) | `enterprise_rag` package + `office_agent` placeholder | The completed RAG implementation moved under `enterprise_rag/`; `office_agent/` is a reserved empty placeholder; root docs stay repo-level; historical ADRs are preserved, not moved or rewritten. No runtime behavior change. |

### Office Agent ADRs (015–018)

| ADR | Title | Decision in one line |
|---|---|---|
| [015](office_agent/015-office-agent-v1-architecture.md) | Office Agent v1 architecture | The completed Office Agent v1: deterministic keyword intent routing (email → calendar → ticket → daily_briefing → knowledge → unknown), a single `answer_office_request()` entry point, a `ToolResult` tool contract, a Knowledge Q&A adapter over `enterprise_rag` plus local mock email/calendar/ticket tools and a thin Daily Briefing aggregator — all local, read-only, deterministic, and no-LLM/no-external-integration. |
| [016](office_agent/016-office-agent-capability-extensions.md) | Office Agent capability extensions | Extends ADR 015 with the later Meeting Agent / Meeting Prep (v1.5) and Workflow / Approval Agent (v1.6) capabilities: the seven-capability inventory and the current router precedence (email → workflow/approval → ticket → meeting_prep → calendar → daily_briefing → knowledge → unknown). Both extensions are deterministic composite workflows with simulated actions — no LLM (Knowledge Q&A stays the only capability calling `enterprise_rag`), no external integration. |
| [017](office_agent/017-office-agent-llm-assist-email-digest.md) | Optional LLM-assisted email digest | Partially supersedes ADR 015/016's "No LLM" office stance for the Email Summary tool only: an optional, **default-off** (`OFFICE_LLM_ENABLED`) single-pass structured-output digest in `office_agent/llm_assist/`, with a byte-for-byte flag-off guarantee, deterministic grounding validation, an honest `llm_assist_error` fallback, and injection controls (no action surface). All other tools stay deterministic; keys-free CI is unaffected (real-model test gated under `tests/office_agent/integration/`). |
| [018](office_agent/018-office-agent-llm-assist-daily-briefing.md) | Optional LLM-assisted Daily Briefing narrative | Extends ADR 017 with a **second** optional, **default-off** assist — for the Daily Briefing tool only. The same `OFFICE_LLM_ENABLED` switch gates a single-pass structured-output narrative (`BriefingNarrative`) that synthesizes emails, meetings, tickets, tasks, and approvals; a separate `collect_briefing_facts()` fact set is the single source of truth for both the LLM input and the grounding whitelist. Prepends narrative → validated references → the unchanged deterministic briefing; keeps the byte-for-byte flag-off guarantee, deterministic grounding (duplicates normalized, not rejected), and the `llm_assist_error` fallback. All other tools stay deterministic. |

### Repository-wide ADRs (019)

| ADR | Title | Decision in one line |
|---|---|---|
| [019](019-hierarchical-runtime-privacy-modes.md) | Hierarchical runtime privacy modes | Two default-off switches: `PRIVACY_MODE` disables Tavily, LangSmith tracing, and both Office LLM assists while preserving the OpenAI RAG path; `OFFLINE_MODE` additionally disables OpenAI and every external service, failing closed with the additive `offline_mode` stop reason. A mode can only restrict; the graph is untouched. Governs both `enterprise_rag` and `office_agent`, so it lives at `docs/adr/`. |

## Conventions

- Status is `Accepted` for all current ADRs; superseded decisions would be
  marked `Superseded by ADR-XXX` rather than edited or deleted.
- New ADRs take the next number and follow the same template.
- ADRs reference real files and constants (`enterprise_rag/graph/consts.py`,
  `MAX_RETRIES = 5`, budget defaults 30/5/15) so they can be checked against
  the code they describe. ADRs written before the [ADR 014](enterprise_rag/014-enterprise-rag-package-and-office-agent-placeholder.md)
  package refactor cite the former top-level paths (`graph/…`, `ingestion.py`)
  and are preserved as history.
