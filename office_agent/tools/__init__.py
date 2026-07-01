"""
office_agent.tools — adapters that let the Office Agent invoke capabilities.

Phase 1 ships a single tool: `knowledge` (a thin adapter over the completed
enterprise_rag engine). Future tools (email summary, calendar lookup, tickets,
tasks) will be added here in their own phases, each behind the same
adapter-not-reimplementation rule.
"""
