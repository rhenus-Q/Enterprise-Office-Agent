# ADR 016: Office Agent capability extensions (Meeting and Workflow / Approval)

Status: Accepted

Date: 2026-07-03

Extends: [ADR 015](015-office-agent-v1-architecture.md) (the original
five-capability, deterministic, local-only Office Agent v1). ADR 015 remains the
historical baseline; this ADR records the later capability extensions and does
not replace or rewrite that decision.

## Context

[ADR 015](015-office-agent-v1-architecture.md) established Office Agent v1
(Phases 1–5) as a **deterministic, local-only, mock-data-backed** agent over five
capabilities — Knowledge Q&A, Email Summary, Calendar Lookup, Task / Ticket
Assistant, and Daily Briefing — with a keyword router, a single
`answer_office_request()` entry point, and a `ToolResult` tool contract. That ADR
explicitly deferred richer capabilities and left "Daily Briefing evolution"
(graph-based or LLM-assisted) and "Router evolution" (LLM vs. deterministic vs.
hybrid) as open future decisions.

Two capabilities were added after v1:

- **Meeting Agent / Meeting Prep** (v1.5 / Phase 6) — a composite capability that
  assembles a meeting-prep sheet by combining the existing local calendar, inbox,
  ticket, and task data.
- **Workflow / Approval Agent** (v1.6 / Phase 7) — an approval-queue capability
  that summarizes a fictional approval queue and audit log and *simulates*
  approve / reject / follow-up-task actions.

Both extensions kept the architecture **deterministic at the Office Agent layer**.
Knowledge Q&A remains the only capability that delegates to the LLM-based
`enterprise_rag` subsystem; neither new capability calls an LLM, the RAG engine,
or any external service. This ADR records that the deterministic decision from
ADR 015 was deliberately retained as the surface grew from five to seven
capabilities, and documents the current seven-capability architecture and router
precedence.

## Decision

Keep the Office Agent **deterministic, local-only, and mock-data-backed** while
extending it to **seven capabilities**, added through the same four-step pattern
ADR 015 defined (one intent constant + one router rule + one tool returning
`ToolResult` + one dispatch branch):

1. **Knowledge Q&A** — enterprise document questions, delegated to the LLM-based
   `enterprise_rag` engine through the adapter (`office_agent/tools/knowledge.py`).
2. **Email Summary** — deterministic summaries over a fictional mock inbox.
3. **Calendar Lookup** — today / tomorrow / next-meeting / conflicts over a
   fictional mock calendar.
4. **Task / Ticket Assistant** — ticket/task views and *simulated* task creation
   over fictional mock tickets/tasks.
5. **Daily Briefing** — a thin aggregation of the email/calendar/ticket data.
6. **Meeting Agent / Meeting Prep** — a deterministic composite prep sheet
   (`office_agent/tools/meeting.py`).
7. **Workflow / Approval Agent** — a deterministic approval-queue view with
   simulated decisions and audit-oriented views (`office_agent/tools/approvals.py`).

### Router precedence (verified against `office_agent/router.py`)

The keyword router evaluates ordered rules; the first matching group wins, and no
match returns `unknown`. The precedence is:

```
email → workflow/approval → ticket/task → meeting_prep → calendar → daily_briefing → knowledge → unknown
```

Notes on the order (as implemented):

- **Email wins first** so an explicit inbox request ("summarize my emails about
  the VPN policy") is an email request, not a policy lookup.
- **Workflow / Approval is matched before ticket/task**, so an approval request
  that mentions a task ("create a follow-up task for APR-001") routes to the
  workflow tool. An explicit approval id (`APR-\d+`) also routes here, evaluated
  at the workflow rule's precedence position (after the email keywords).
- **Meeting *prep* is matched before the broad calendar keywords**, so "prepare me
  for my next meeting" is prep, while a plain "what meetings do I have today?"
  lookup still falls through to Calendar Lookup.
- **Daily Briefing** follows the specific channel tools but precedes the broad
  knowledge keywords, so "what should I focus on today?" is a briefing.
- **Knowledge / policy / document** keywords are last before the `unknown`
  fallback.

### Module roles

- **`office_agent/router.py`** — the deterministic keyword router; owns the intent
  precedence above. No LLM.
- **`office_agent/engine.py`** — the single entry point
  `answer_office_request(user_input)`: routes once, dispatches to exactly one
  tool, and builds an `OfficeAgentResponse` uniformly with the routed intent
  attached for observability and testing.
- **`office_agent/schemas.py`** — the intent string constants (now including
  `INTENT_MEETING_AGENT` and `INTENT_WORKFLOW_APPROVAL`), the `OFFICE_INTENTS`
  tuple, and the plain dataclasses (`OfficeRequest`, `RoutedIntent`, `ToolResult`,
  `OfficeAgentResponse`). Kept in lockstep with the router and engine dispatch.
- **Meeting Agent tool (`office_agent/tools/meeting.py`)** — reuses the other
  tools' *pure* loaders/helpers (calendar/email/tickets) to compose a prep sheet;
  it never parses another tool's formatted output, never calls the RAG engine
  ("relevant knowledge areas" are inferred deterministically from labels), and
  reaches no external service.
- **Workflow / Approval tool (`office_agent/tools/approvals.py`)** — filters a
  fictional approval queue and audit log and returns simulated decisions /
  follow-up tasks. All actions are pure and simulated; the only write path is an
  explicit, test-only `persist_path` seam that never touches the repo's mock data.
- **`enterprise_rag` adapter boundary (`office_agent/tools/knowledge.py`)** — the
  sole seam between the Office Agent and the LLM-based RAG subsystem. It depends
  only on the public API (`answer_question` / `format_answer`) and never
  reimplements retrieval/generation/grading.

### What the extensions are — and are not

- **Meeting Agent is a deterministic composite workflow**, not an autonomous LLM
  agent: it selects a meeting and derives agenda/risks/follow-ups by fixed rules
  over local mock data.
- **Workflow / Approval Agent is a deterministic workflow** with **simulated
  decisions** and **audit-oriented views**, not an autonomous LLM agent.
- **Neither new capability is currently an autonomous LLM agent**, and neither
  calls an LLM.
- **External actions and persistence remain simulated or caller-controlled** —
  approve/reject/create-task are simulated, and mock data is read-only by default.
- **Knowledge Q&A is the only capability that calls the LLM-based RAG subsystem.**

## Rationale

The extensions kept deterministic orchestration for the same reasons ADR 015 chose
it — the growth from five to seven capabilities did not change the trade-off:

- **Predictable behavior.** Rule-based routing and rule-based tools produce the
  same output for the same input every time.
- **Keys-free tests and CI.** The whole Office Agent suite runs with no API keys
  and no network; the Meeting and Workflow tools are fully mockable at their loader
  seams.
- **Stable routing.** A fixed, test-protected precedence keeps existing phrasings
  routing where they did as new capabilities are added.
- **Low latency and cost.** No LLM calls on the office path means no per-request
  token cost or latency for capabilities that are fundamentally rule-based.
- **Easier failure handling.** Deterministic local tools have small, well-defined
  failure modes compared with LLM/network calls.
- **No unnecessary use of LLMs for rule-based business workflows.** Meeting prep
  and approval-queue views are structured data operations; an LLM would add
  nondeterminism and cost without a corresponding benefit.

## Consequences

- **The Office Agent now has seven capabilities** behind one deterministic,
  LLM-free entry point.
- **Router precedence and intent-surface consistency must remain test-protected.**
  The precedence order and the `schemas` ↔ router ↔ engine lockstep are behavior
  that tests must continue to pin so new capabilities cannot silently reorder or
  misroute existing ones.
- **Documentation should distinguish** plain tools, deterministic composite
  workflows (Meeting, Workflow / Approval), LLM-assisted features (Knowledge Q&A
  via `enterprise_rag`), and autonomous agents (none currently exist here).
- **Future selective LLM assistance requires a separate ADR.** Introducing an LLM
  into routing, meeting prep, briefing narrative, or any office-path capability is
  a new decision and must not silently change this one.
- **ADR 015 remains the historical baseline** for the original five-capability v1
  decision; this ADR extends it to record the seven-capability architecture.

## Status and relationships

- **Status: Accepted** — consistent with the repository's ADR convention (a later
  reversal would be marked `Superseded by ADR-XXX` rather than editing this
  record).
- This ADR **extends** [ADR 015](015-office-agent-v1-architecture.md); it does not
  supersede or rewrite ADR 015's historical decision.
- It also inherits the cross-cutting rules from
  [ADR 014](../enterprise_rag/014-enterprise-rag-package-and-office-agent-placeholder.md) and
  CLAUDE.md (side-effect-free imports, lazy data/client access, no regression to
  `enterprise_rag`).
