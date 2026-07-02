# Office Agent v1.6 — Release Notes

## Summary

Office Agent v1.6 completes Phase 7 by adding the **Workflow / Approval Agent**
capability to the Enterprise Office Agent. With this release the Office Agent
covers **seven capabilities** through a single deterministic, LLM-free entry
point (`office_agent.engine.answer_office_request()`). This release is
engineering hardening and release readiness: it adds no runtime capabilities
beyond the already-merged Phase 7 tool, and it consolidates documentation,
module boundaries, and validation so the repository reads as a professional
engineering project.

## Version map

| Release | Phase | Capabilities added |
|---|---|---|
| **v1** | Phases 1–5 | Knowledge Q&A, Email Summary, Calendar Lookup, Task / Ticket Assistant, Daily Briefing |
| **v1.5** | Phase 6 | Meeting Agent / Meeting Prep |
| **v1.6** | Phase 7 | Workflow / Approval Agent |

## Included capabilities

| # | Capability | Intent | Backing |
|---|---|---|---|
| 1 | Knowledge Q&A | `knowledge_qa` | Adapter over the real `enterprise_rag` engine |
| 2 | Email Summary | `email_summary` | Local mock `mock_data/emails.json` |
| 3 | Calendar Lookup | `calendar_lookup` | Local mock `mock_data/calendar_events.json` |
| 4 | Task / Ticket Assistant | `ticket_assistant` | Local mock `mock_data/tickets.json` + `tasks.json` |
| 5 | Daily Briefing | `daily_briefing` | Aggregates the mock email/calendar/ticket data |
| 6 | Meeting Agent / Meeting Prep | `meeting_agent` | Composes the mock calendar/email/ticket data |
| 7 | Workflow / Approval Agent | `workflow_approval` | Local mock `mock_data/approvals.json` + `audit_log.json` |

## What is new in v1.6

- **Workflow / Approval Agent (`workflow_approval`, Phase 7)** — a deterministic
  mock approval assistant over a local approval queue and audit log:
  - **List / filter views** — all, pending, assigned-to-me, high-priority /
    urgent, approved, rejected, and topic filters (e.g. "expense approvals",
    "VPN approvals").
  - **Per-id status** — status, priority, requester, approver/owner, due date,
    amount, linked ticket/task, and policy area for any `APR-<n>`.
  - **Simulated approve/reject decisions** — computed in the response only.
  - **Simulated follow-up task creation** — computed in the response only.
  - **Audit-log output** — a specific approval's events, sorted by timestamp.
- **Routing precedence** places workflow/approval matching before ticket/task, so
  "create a follow-up task for APR-001" is an approval action rather than a plain
  task.

## Architecture notes

- The Office Agent is a **thin keyword router + tool dispatch**, not a LangGraph
  graph. Intent classification is pure keyword matching — **no LLM routing**.
- **`enterprise_rag` is not duplicated inside `office_agent`.** Knowledge Q&A is
  a thin adapter that calls `enterprise_rag.graph.engine.answer_question()` and
  reuses its formatting (caveats + `Sources:` section). It is the only Office
  Agent tool that reaches an LLM / external services.
- Every tool returns a uniform `ToolResult`; the engine builds an
  `OfficeAgentResponse` with the routed intent attached for observability/testing.
- **Simulated actions never mutate the repo mock data.**
  `handle_approval_request` writes nothing; `build_simulated_decision` and
  `build_simulated_followup_task` are pure (no system clock — timestamps mirror
  the source approval). An optional `record_decision(..., persist_path=...)` seam
  writes only to a caller-provided path (tests use `tmp_path`), never to
  `mock_data/`.
- Both modules follow the repo discipline: **side-effect-free imports** and lazy
  `@lru_cache` external clients / data loaders.

## Validation results

Local validation of the v1.6 baseline:

- Office Agent demo: **passed** (local-only, no API keys)
- `tests/office_agent/`: **137 passed**
- Full suite (`uv run pytest`): **592 passed**
- `ruff check`: **passed**
- `ruff format --check`: **passed**
- `mypy`: **passed**

CI ([`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)) runs the fully
mocked suites and lint on every push/PR with no API keys.

## Mocked surfaces

All Office Agent capabilities except Knowledge Q&A are backed by static,
fictional AcmeCorp JSON in [`office_agent/mock_data/`](../../office_agent/mock_data/):
`emails.json`, `calendar_events.json`, `tickets.json`, `tasks.json`,
`approvals.json`, `audit_log.json`. The data is read-only and anchored to the
data (not the system clock). No external service is contacted (no Gmail, Outlook,
Google Calendar, Slack, Jira, Linear, Asana, or Trello). Only Knowledge Q&A
reaches an LLM / external services, and only through the `enterprise_rag` engine.

## Non-goals

- No real integrations with mail, calendar, ticketing, or approval systems.
- No LLM routing for the Office Agent.
- No conversation memory (both modules are single-turn).
- No frontend, deployment tooling, or external service connectors.
- No changes to `enterprise_rag` behavior, prompts, graph logic, model names,
  eval semantics, or the corpus.

## Known limitations

- Office Agent tools are deterministic demonstrations of the routing + tool
  contract over mock data, not production integrations.
- Keyword routing is intentionally simple; it does not do semantic intent
  resolution.
- The `enterprise_rag` engine's own limitations (single-turn CLI, `print`-based
  logging, sequential grading, prompt-level-only injection defense) are detailed
  in [`structure.md`](../../structure.md) §15.

## Suggested future production integrations

These are explicitly out of scope for this repository, listed only as the natural
next steps if the Office Agent were taken toward production:

- Replace the mock loaders with real read paths behind the same tool contract
  (Gmail / Outlook for email, Google / Outlook Calendar for calendar, Jira /
  Linear / Asana for tickets, a real approval system for `workflow_approval`).
- Promote simulated actions to real writes behind an explicit, audited
  persistence layer (the `record_decision(..., persist_path=...)` seam models the
  shape of such a boundary).
- Add authentication/authorization, structured logging, and metrics for any real
  integration.

## Detailed usage

See [`docs/office-agent-v1-demo.md`](../office-agent-v1-demo.md) for the full
capability list, routing precedence, the programmatic API, and example requests.
