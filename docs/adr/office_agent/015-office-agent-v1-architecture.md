# ADR 015: Office Agent v1 architecture

Status: Accepted

Date: 2026-07-01

Builds on: [ADR 014](../enterprise_rag/014-enterprise-rag-package-and-office-agent-placeholder.md)
(the `enterprise_rag` package + reserved `office_agent` placeholder). ADR 014
reserved the module path; this ADR records the architecture of the Office Agent
v1 that now fills it.

> **Historical note.** This ADR records the **original five-capability v1
> architecture** and is preserved as history — it is deliberately not rewritten as
> though later capabilities existed when it was accepted. The subsequent Meeting
> Agent / Meeting Prep and Workflow / Approval Agent extensions (and the current
> seven-capability inventory and router precedence) are documented in
> [ADR 016](016-office-agent-capability-extensions.md), which extends this record.

## Context

`enterprise_rag` is the completed Enterprise Document Q&A engine, exposed through
a stable public API (`enterprise_rag.graph.engine.answer_question()` and
`enterprise_rag.graph.formatting.format_answer()`). ADR 014 established a second
capability module, `office_agent/`, as an intentionally empty placeholder and
committed to two rules for it: side-effect-free imports and no regression to
`enterprise_rag` behavior or its tests.

Office Agent v1 was built incrementally (Phases 1–5) into a shell around five
**local, mock, deterministic** office capabilities:

1. **Knowledge Q&A** — enterprise document questions, answered by adapting the
   `enterprise_rag` engine.
2. **Email Summary** — summaries over a fictional mock inbox.
3. **Calendar Lookup** — today/tomorrow/next-meeting/conflicts over a fictional
   mock calendar.
4. **Task / Ticket Assistant** — ticket/task views and a *simulated* task
   creation over fictional mock tickets/tasks.
5. **Daily Briefing** — a thin aggregation of the email/calendar/ticket data.

The explicit goal of v1 was to prove **multi-tool office-agent orchestration**
— routing a free-text request to the right capability and returning a useful,
structured result — **without** external integrations, OAuth, or LLM-based
routing. Those carry real cost, secret-management, privacy, and
nondeterminism concerns that would have dominated the effort and made the whole
surface hard to test. v1 deliberately defers them.

## Decision

Keep Office Agent v1 **deterministic, local-only, and mock-data-backed**, with a
small, uniform module architecture:

### Routing — a deterministic keyword router (no LLM)

`office_agent.router.route_request(text) -> RoutedIntent` classifies a request by
case-insensitive substring matching against ordered keyword groups. The first
matching group wins; no group matches → `unknown`. The precedence is:

```
email -> calendar -> ticket/task -> daily_briefing -> knowledge -> unknown
```

Rationale for this order:

- **Channel-specific requests win first.** If a request explicitly names a
  channel (`email`/`inbox`, `calendar`/`meeting`/`schedule`, `ticket`/`task`),
  it routes to that specific tool even if it also mentions a policy topic
  (e.g. "summarize my emails about the VPN policy" is an email request, not a
  knowledge lookup).
- **Whole-day requests route to Daily Briefing.** Broad "brief me / what should I
  focus on today / summarize my day" requests are holistic, so they route to the
  aggregator — placed after the specific tools but before the broad knowledge
  keywords.
- **Knowledge/policy/document questions** fall to `knowledge_qa`.
- **Everything else** returns a safe, explicit unsupported-intent message
  (`formatting.UNSUPPORTED_INTENT_NOTE`) — the agent never guesses or fabricates
  a capability it does not have.

### Typed schemas and a single entry point

- Intents are **string constants** in `office_agent.schemas`
  (`INTENT_KNOWLEDGE_QA`, `INTENT_EMAIL_SUMMARY`, `INTENT_CALENDAR_LOOKUP`,
  `INTENT_TICKET_ASSISTANT`, `INTENT_DAILY_BRIEFING`, `INTENT_UNKNOWN`), kept in
  lockstep with the router and the engine dispatch.
- Lightweight dataclasses carry data: `OfficeRequest`, `RoutedIntent`,
  `ToolResult`, `OfficeAgentResponse`.
- `office_agent.engine.answer_office_request(user_input) -> OfficeAgentResponse`
  is the **single entry point**: it routes once, dispatches to exactly one tool,
  and builds the response uniformly with the routed `intent` attached for
  observability and testing. It is the office-agent analogue of
  `enterprise_rag.graph.engine` — thin dispatch, no orchestration graph.

### `ToolResult` — the common tool output contract

Every tool returns a `ToolResult(tool, content, stop_reason, sources, run_id)`.
`content` is the user-facing text; `tool` records which capability produced it;
the remaining fields carry through Knowledge Q&A's `enterprise_rag` metadata
(caveats/sources/run_id) and default to empty for the mock tools. The engine maps
any `ToolResult` to an `OfficeAgentResponse` the same way, so adding a capability
is: one intent constant + one router rule + one tool returning `ToolResult` + one
dispatch branch.

### Capability tools — small modules, one pattern

- `tools/knowledge.py` **adapts** `enterprise_rag` (`answer_question` +
  `format_answer`) — it never reimplements retrieval/generation/grading/
  formatting, so RAG behavior and provenance are preserved exactly.
- `tools/email.py`, `tools/calendar.py`, `tools/tickets.py` are deterministic
  summaries over static fictional JSON in `office_agent/mock_data/`.
- `tools/briefing.py` is a **thin aggregator** that reuses the other tools' pure
  loaders/helpers (e.g. `email.load_emails`, `calendar.resolve_days/next_meeting/
  find_conflicts`, `tickets.load_tickets/load_tasks`) — it never parses another
  tool's formatted output and is **not** a new agent graph.

### Cross-cutting rules (consistent with ADR 014 and CLAUDE.md)

- **Side-effect-free imports**: mock JSON is read lazily (cached) on first use,
  never at import time; no external client is constructed.
- **Read-only mock data by default**: task "creation" is *simulated* and pure;
  the only write path is an explicit, opt-in `persist_path` seam used solely by
  tests against `tmp_path`, never the repo's `mock_data/` files.
- **Deterministic, mock-data-anchored dates**: "today"/"tomorrow"/the briefing
  day are resolved from the data, never the system clock, so output is identical
  on every run.
- **No LLM** anywhere in the office-agent path (routing or summarization).
- **Mocked, CI-safe tests**: every office-agent test runs with no API keys and no
  network; engine tests mock each tool at its seam and assert the non-selected
  tools are never invoked.

### Deferred to future work

Real external integrations (mail/calendar/ticketing), OAuth/secret management,
task persistence, permissions/privacy/audit logging, and LLM-based routing or
briefing generation are explicitly **out of scope for v1**.

## Consequences

Positive:

- **Deterministic and CI-safe.** No secrets, OAuth, or external-service setup;
  the whole office-agent suite is fully mocked and fast.
- **Clear module boundaries.** Router, schemas, engine, and one file per tool —
  each capability is added by the same four-step pattern.
- **`enterprise_rag` stays stable and reused through its public API.** The
  Knowledge Q&A adapter depends only on `answer_question`/`format_answer`, so RAG
  routing, prompts, model, state schema, and tests are untouched (ADR 014's
  no-regression rule holds).
- **Easy future replacement.** Each mock tool can be swapped for a real adapter
  behind the same `ToolResult` interface without touching the router or engine.
- **Honest failure mode.** Unsupported requests get an explicit, safe message
  rather than a hallucinated capability.

Trade-offs:

- **Keyword routing is limited** compared with an LLM router: it can misroute
  phrasings that use none of the known keywords, and precedence is a fixed order
  rather than a learned intent. Adequate for a bounded, well-known capability set;
  revisited if the capability space grows.
- **Mock data is not real user data**, so the tools demonstrate behavior and
  shape, not production correctness.
- **The Daily Briefing is deterministic** and may feel less flexible than an
  LLM-written narrative; it trades expressiveness for reproducibility and
  testability.
- **Real integrations, auth, persistence, permissions, privacy, and audit
  logging remain open** — v1 does none of them.

## Alternatives considered

- **An LLM router in v1** — rejected/deferred: adds cost and nondeterminism,
  makes routing hard to unit-test, and needs API keys in CI. A deterministic
  keyword router proves orchestration first; an LLM (or hybrid) router is a
  future decision once the capability set justifies it.
- **Direct Gmail / Google Calendar / Jira (etc.) integrations in v1** —
  rejected/deferred: OAuth, secret management, rate limits, and privacy/audit
  concerns are a large surface that would dominate v1 and make tests depend on
  live services. Mock tools behind a stable interface let the real adapters land
  later without reshaping the agent.
- **Making the Daily Briefing a new LangGraph graph** — rejected: v1's briefing
  is a straight-line aggregation of pure helpers; a graph would add orchestration
  machinery with no branching to justify it. Kept as a thin function.
- **Mutating the mock JSON files for task creation** — rejected: it would make
  tests order-dependent and risk corrupting committed fixtures. Task creation is
  simulated and pure, with persistence available only via an explicit test-only
  path.
- **Duplicating `enterprise_rag` logic inside `office_agent`** — rejected: it
  would fork retrieval/generation/grading and risk diverging from — or
  destabilizing — the completed engine. The adapter reuses the public API so RAG
  stays the single source of truth.

## Future decisions

Each of these is deliberately left open and will get its own ADR when tackled:

- **Router evolution** — LLM router vs. deterministic vs. hybrid.
- **Real mail adapter** — Gmail / Outlook.
- **Real calendar adapter** — Google / Outlook Calendar.
- **Real ticketing adapter** — Jira / Linear / Asana.
- **Task persistence model** — where and how created tasks are stored.
- **Auth / OAuth / security / privacy model** for real integrations.
- **Audit logging and user permissioning.**
- **Daily Briefing evolution** — whether it becomes graph-based or LLM-assisted.
- **Surface** — whether Office Agent gets a CLI or an API server (today it is a
  library entry point; `main.py` remains the `enterprise_rag` CLI).
