"""
office_agent.tools — one tool per Office Agent capability.

Ships seven tools (Office Agent v1.6.0 / Phase 7):

- `knowledge` — a thin adapter over the completed enterprise_rag engine (the one
  tool that reaches an LLM); it never reimplements retrieval, generation, or graph
  logic.
- `email` — deterministic Email Summary over local mock inbox data.
- `calendar` — deterministic Calendar Lookup over local mock calendar data.
- `tickets` — deterministic Task / Ticket Assistant over local mock ticket/task data.
- `briefing` — deterministic Daily Briefing aggregating the email/calendar/ticket data.
- `meeting` — deterministic Meeting Agent / Meeting Prep composition.
- `approvals` — deterministic Workflow / Approval Agent over the local approval
  queue + audit log.

Every tool except `knowledge` runs on local, read-only mock data with no LLM by
default; Email Summary and Daily Briefing may add an optional, default-off LLM
assist (see `office_agent.llm_assist`). All follow the same
adapter-/local-not-reimplementation rule.
"""
