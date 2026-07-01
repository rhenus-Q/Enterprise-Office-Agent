"""
office_agent — the initial Enterprise Office Agent shell (Phase 1).

Phase 1 establishes the foundation only: a lightweight schema layer
(:mod:`office_agent.schemas`), a deterministic rule-based router
(:mod:`office_agent.router`), a single Knowledge Q&A tool that adapts the
completed enterprise document Q&A engine (:mod:`office_agent.tools.knowledge`
over :mod:`enterprise_rag`), and a thin dispatch entry point
(:func:`office_agent.engine.answer_office_request`).

Email summary, calendar lookup, tickets, tasks, and the daily briefing are
intentionally NOT implemented yet — they are reserved for later phases. Anything
added here must follow the same rules as the rest of the repo (side-effect-free
imports, lazy external clients) and must not change or regress `enterprise_rag`
behavior or its tests (see CLAUDE.md).
"""
