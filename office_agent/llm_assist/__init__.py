"""
office_agent.llm_assist — the Office Agent's optional, default-off LLM assist.

Phase 1 hosts exactly one capability: an opt-in LLM-assisted email digest layered
on top of the deterministic Email Summary tool (`office_agent/tools/email.py`).
Everything here is gated behind `OFFICE_LLM_ENABLED` (default false): with the
flag off, nothing in this package constructs a client and the deterministic Office
Agent behavior is preserved byte-for-byte.

Import is side-effect-free: reading config constructs nothing, and the ChatOpenAI
client is built lazily only on the first `email_digest.get_email_digest_chain()`
call. This package imports nothing from `enterprise_rag` — the Office Agent gains
one optional LLM feature without depending on the RAG subsystem's internals.
"""
