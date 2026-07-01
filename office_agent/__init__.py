"""
office_agent — the Enterprise Office Agent (Phase 2).

The package provides a lightweight schema layer (:mod:`office_agent.schemas`), a
deterministic rule-based router (:mod:`office_agent.router`), a set of tools, and
a thin dispatch entry point (:func:`office_agent.engine.answer_office_request`).

Implemented capabilities:

- **Knowledge Q&A** (:mod:`office_agent.tools.knowledge`) — adapts the completed
  enterprise document Q&A engine (:mod:`enterprise_rag`).
- **Email Summary** (:mod:`office_agent.tools.email`) — a deterministic summary
  over local, fictional mock inbox data (:mod:`office_agent.mock_data`); no LLM
  and no mail service.

Calendar lookup, tickets, tasks, and the daily briefing are intentionally NOT
implemented yet — they are reserved for later phases. Anything added here must
follow the same rules as the rest of the repo (side-effect-free imports, lazy
external clients, local-only mock data) and must not change or regress
`enterprise_rag` behavior or its tests (see CLAUDE.md).
"""
