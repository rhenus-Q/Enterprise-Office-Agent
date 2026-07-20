"""
api — the thin FastAPI adapter over the existing Python engines.

Exposes exactly two endpoints (`GET /api/health`, `POST /api/agent/run`) whose
only engine boundary is `office_agent.engine.answer_office_request()`. No
routing, intent detection, tool behavior, formatting, privacy, fallback, date,
or LLM-assist logic is implemented or duplicated here.

Importing this package (and `api.app`) is side-effect-free: the application is
built by the `create_app()` factory, which is where `.env` loading and tracing
privacy enforcement happen.
"""
