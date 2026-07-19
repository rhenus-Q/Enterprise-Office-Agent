# ADR 018: Optional LLM-assisted Daily Briefing narrative for the Office Agent

Status: Accepted

Date: 2026-07-03

Extends: [ADR 017](017-office-agent-llm-assist-email-digest.md) (the first optional,
default-off Office LLM assist — the Email Digest). This ADR adds a **second** such
assist for **one more tool only** (Daily Briefing); every other Office Agent
capability remains deterministic and LLM-free, and the Knowledge Q&A adapter over
`enterprise_rag` is unchanged. ADR 017 explicitly left "a Daily Briefing narrative"
as out of scope and requiring its own ADR — this is that ADR.

## Context

ADR 017 established a safe, bounded, opt-in LLM pattern inside the Office Agent
(`office_agent/llm_assist/`): default-off `OFFICE_LLM_ENABLED`, a single
structured-output `gpt-5-mini` call, a validated Pydantic boundary, deterministic
grounding validation and rendering, and an honest `llm_assist_error` fallback with
no action surface.

The deterministic Daily Briefing (`office_agent/tools/briefing.py`) aggregates the
local mock data into one morning briefing, but it surfaces mostly **counts** and a
couple of email/meeting bullets — there is no cross-source *synthesis* of the day,
and workflow approvals are not represented at all. A narrative that ties emails,
meetings, tickets/tasks, and approvals together would be useful, but it must not
weaken the deterministic, keys-free guarantees.

## Decision

Add an **optional, default-off, single-pass** LLM narrative layered on top of — never
replacing — the deterministic Daily Briefing, reusing the ADR 017 infrastructure and
adding a **separate, narrowly scoped** schema/prompt/chain/validator/renderer:

- **Shared switch, shared config.** The same `OFFICE_LLM_ENABLED` flag (and the same
  `OFFICE_LLM_REQUEST_TIMEOUT_SECONDS` and `STOP_REASON_LLM_ASSIST_ERROR` from
  `office_agent/llm_assist/config.py`) now gates **two** assists. With the flag off,
  no LLM client is constructed and `generate_daily_briefing` output is **byte-for-byte
  identical** to before.
- **One structured-output call, no orchestration.** A new lazy LCEL chain
  (`get_briefing_narrative_chain`) using `ChatOpenAI(model="gpt-5-mini",
  temperature=0, timeout=...)` with `with_structured_output(BriefingNarrative)`. No
  LangGraph, no retries, no tools bound.
- **A separate collected fact set is the single source of truth.** A pure
  `collect_briefing_facts()` gathers a bounded, item-level set (`{source_type, id,
  title}`) across emails, meetings, tickets, tasks, and approvals — read-only, dates
  anchored to the data, a documented per-source cap, deterministic sorts. It is used
  **both** as the LLM input **and** as the grounding whitelist. The rendered
  deterministic sections are unchanged; approvals are added to the facts because the
  narrative synthesizes them.
- **Validated model is the only boundary.** LLM output crosses in solely as a
  validated `BriefingNarrative` (`narrative`, `references[{source_type, id}]`) and is
  rendered deterministically; reference titles are looked up from the facts, never
  taken from the model.
- **Deterministic grounding validation.** `validate_narrative` requires every
  reference's `(source_type, id)` pair to be present in the collected facts — one
  check that rejects unknown, global-but-absent, source-type-mismatched, and
  malformed ids. Duplicate references are **normalized (deduplicated), not rejected**
  — a deliberate, documented divergence from the digest's reject-on-duplicate rule,
  because references are a citation surface, not an ordering.
- **Success ordering.** On success the output is: narrative → validated reference
  list → a `"Deterministic briefing (facts):"` label → the complete, unchanged
  deterministic briefing, in that order (the narrative is **prepended**, whereas the
  email digest is appended).
- **Honest fallback.** Any failure (timeout, API error, structured-output parse
  failure, Pydantic validation error, grounding failure) returns the unchanged
  deterministic briefing plus one briefing-specific caveat line
  (`BRIEFING_ASSIST_ERROR_NOTE`) and `stop_reason="llm_assist_error"`. The assist
  never re-raises; console logging is exception-type only.
- **Prompt-injection controls.** The (new, briefing-specific) system prompt declares
  all source text untrusted data, instructs the model to reference only provided ids
  and never invent ids/facts/deadlines, forbids claiming any operation was performed,
  and the model has no action surface.
- **Scope containment.** Daily Briefing only. The router, engine dispatch, `ToolResult`
  / `OfficeAgentResponse` schema shape, mock data (read-only), the Phase 1 Email
  Digest, and the other capabilities are unchanged. The engine already copies
  `stop_reason` from `ToolResult`, so the outcome flows through with no schema change.

Tests: mocked, keys-free unit tests in `tests/office_agent/`; exactly one
`requires_openai`-gated real-model test in `tests/office_chains/`. A separate
offline-validatable eval lives at `evals/office_assist/briefing_cases.jsonl` +
`run_briefing_assist_eval.py`; full runs are approval-gated like the RAG eval.

## Rationale

- **Zero-risk default.** Default-off with a byte-for-byte guarantee means the feature
  cannot regress the deterministic Office Agent or its keys-free CI.
- **Reuse, don't over-generalize.** Reusing the ADR 017 flag/timeout/stop_reason
  avoids a second Office LLM config system, while a separate schema/prompt/validator/
  renderer avoids collapsing two different tasks into a premature "LLM service layer."
- **Containment over trust.** The injection defense is architectural (no action
  surface, validated schema, id cross-checks against a collected whitelist,
  deterministic rendering), with prompt hardening as a first line.
- **Independent of `enterprise_rag`.** The assist imports nothing from the RAG
  subsystem, so RAG behavior, prompts, model, budgets, and tests are untouched.

## Consequences

- The Office Agent now has **two** optional LLM-assisted capabilities (email digest,
  briefing narrative); everything else stays deterministic and LLM-free.
- `OFFICE_LLM_ENABLED` now enables both assists at once; operators should know one
  switch turns on both. Each keeps an independent byte-for-byte flag-off guarantee.
- Reusing `stop_reason="llm_assist_error"` means observability distinguishes the
  failed capability only via `ToolResult.tool` (`daily_briefing` vs `email_summary`);
  accepted and documented.
- Source-content prompt injection is covered by a mocked unit test, not the eval
  (mock data is read-only), stated honestly in the eval design.
- Future selective-LLM assists remain per-tool decisions and each require their own
  ADR rather than silently widening this one.

## Status and relationships

- **Status: Accepted**, per the repository convention.
- This ADR **extends** [ADR 017](017-office-agent-llm-assist-email-digest.md) for the
  Daily Briefing tool only, and inherits the cross-cutting rules from
  [ADR 014](../enterprise_rag/014-enterprise-rag-package-and-office-agent-placeholder.md) and CLAUDE.md
  (side-effect-free imports, lazy `@lru_cache` clients, no regression to
  `enterprise_rag`). The deterministic Office Agent architecture in
  [ADR 015](015-office-agent-v1-architecture.md) / [ADR 016](016-office-agent-capability-extensions.md)
  is otherwise unchanged.

## Implementation note (current state, 2026-07-04)

The decision above stands as accepted; this note records the **as-implemented**
behavior and the one refinement made after the original decision. It does not
change the decision — it documents where the shipped feature landed.

As implemented (`office_agent/llm_assist/briefing_narrative.py`,
`briefing_models.py`, and `office_agent/tools/briefing.py`), the Daily Briefing
Narrative provides:

- **Deterministic fact collection** — `collect_briefing_facts()` gathers a bounded,
  item-level fact set across emails, meetings, tickets, tasks, and approvals; it is
  the single source of truth for both the LLM input and the grounding whitelist.
- **Optional, default-off LLM narration**, gated by the shared `OFFICE_LLM_ENABLED`
  switch; flag-off output is byte-for-byte the deterministic briefing.
- **A single-pass LCEL structured-output call** (`gpt-5-mini`, `temperature=0`,
  bounded timeout) returning a validated `BriefingNarrative` — no LangGraph, no
  retries, no tools bound.
- **Grounding against the supplied `(source_type, id)` pairs**, with deterministic
  rendering (titles looked up from the facts, duplicates deduplicated not rejected).
- **Deterministic fallback** — any failure returns the unchanged deterministic
  briefing plus `BRIEFING_ASSIST_ERROR_NOTE` and `stop_reason="llm_assist_error"`.

**Refinement (critical-item coverage).** The originally-collected fact set was
`{source_type, id, title}` only. It now also carries, for relevant meeting/ticket
facts, **deterministic critical metadata** (e.g. `importance`, `priority`,
`status`, `conflicts_with`, `critical_reasons`) so that time-sensitive items are
not lost to brevity. The narrative-chain contract accordingly requires that:

- every fact carrying one or more `critical_reasons` **must be covered** in the
  narrative and included in its references (critical facts are never dropped for
  brevity);
- for every supplied schedule conflict, **both sides must be referenced** — a
  meeting whose `conflicts_with` lists another id, and that other meeting;
- **conflict counterparts may be retained beyond the ordinary per-source soft cap**
  in `collect_briefing_facts()`, so a conflict is never structurally omitted from
  the fact set.

The critical metadata is deterministically derived and remains **advisory content**
for the narrator: the model still has **no action, approval, mutation, send, or
execution authority**, and grounding/validation and the deterministic fallback are
unchanged. This remains a **bounded narrative-assistance feature**, not an
autonomous agent and not a LangGraph workflow.
