"""
office_agent — the Enterprise Office Agent (implemented through v1.6 / Phase 7).

The package provides a lightweight schema layer (:mod:`office_agent.schemas`), a
deterministic rule-based router (:mod:`office_agent.router`), a set of tools, and
a thin dispatch entry point (:func:`office_agent.engine.answer_office_request`).

Implemented capabilities (seven, across the version map below):

Office Agent v1 / Phases 1-5:

- **Knowledge Q&A** (:mod:`office_agent.tools.knowledge`) — adapts the completed
  enterprise document Q&A engine (:mod:`enterprise_rag`).
- **Email Summary** (:mod:`office_agent.tools.email`) — a deterministic summary
  over local, fictional mock inbox data (:mod:`office_agent.mock_data`); no LLM
  and no mail service.
- **Calendar Lookup** (:mod:`office_agent.tools.calendar`) — a deterministic
  view over local, fictional mock calendar data (today/tomorrow/next
  meeting/conflicts/important); no LLM and no calendar service.
- **Task / Ticket Assistant** (:mod:`office_agent.tools.tickets`) — deterministic
  ticket/task views and a *simulated* task-creation over local, fictional mock
  data; no LLM and no ticketing service, and it never mutates the mock files.
- **Daily Briefing** (:mod:`office_agent.tools.briefing`) — a deterministic
  aggregation of the email/calendar/ticket mock data into one morning briefing;
  no LLM, no external service, anchored to the mock-data day (not the clock).

Office Agent v1.5 / Phase 6:

- **Meeting Agent / Meeting Prep** (:mod:`office_agent.tools.meeting`) — a
  deterministic *composition* tool that assembles a per-meeting prep sheet from
  the local calendar/email/ticket mock data; no LLM and no external service, and
  it never calls the Enterprise RAG pipeline.

Office Agent v1.6 / Phase 7:

- **Workflow / Approval Agent** (:mod:`office_agent.tools.approvals`) — a
  deterministic mock approval assistant over a local approval queue + audit log,
  with *simulated* approve/reject decisions and follow-up tasks (the mock data is
  never mutated); no LLM and no external service.

Everything except Knowledge Q&A uses local deterministic base workflows by default.
Email Summary and Daily Briefing may optionally add default-off bounded LLM assists.
Anything added here must follow the same rules as the rest of the repo
(side-effect-free imports, lazy external clients, local-only mock data) and must
not change or regress `enterprise_rag` behavior or its tests (see CLAUDE.md).
"""
