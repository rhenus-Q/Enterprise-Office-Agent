"""
office_agent.llm_assist — the Office Agent's optional, default-off LLM assist.

This package hosts two opt-in LLM assists, both gated by the single
`OFFICE_LLM_ENABLED` switch (default false):

- Phase 1 — an LLM-assisted email digest layered on the deterministic Email Summary
  tool (`email_digest.py` + `office_agent/tools/email.py`), validated `EmailDigest`
  boundary in `models.py`.
- Phase 2 — an LLM-assisted Daily Briefing narrative layered on the deterministic
  Daily Briefing tool (`briefing_narrative.py` + `office_agent/tools/briefing.py`),
  validated `BriefingNarrative` boundary in `briefing_models.py`.

The two share the flag/timeout/stop_reason in `config.py` but keep independent
schemas, prompts, validators, and renderers. With the flag off, nothing in this
package constructs a client and the deterministic Office Agent behavior is preserved
byte-for-byte for both tools.

Import is side-effect-free: reading config constructs nothing, and each ChatOpenAI
client is built lazily only on the first `get_*_chain()` call. This package imports
nothing from `enterprise_rag` — the Office Agent gains its optional LLM features
without depending on the RAG subsystem's internals.
"""
