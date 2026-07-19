# ADR 017: Optional LLM-assisted email digest for the Office Agent

Status: Accepted

Date: 2026-07-03

Extends / partially supersedes: [ADR 015](015-office-agent-v1-architecture.md)
(the original "**No LLM** anywhere in the office-agent path" decision) and its
reaffirmation for the later capabilities in
[ADR 016](016-office-agent-capability-extensions.md). This ADR changes that stance
for **one tool only** (Email Summary); every other Office Agent capability remains
deterministic and LLM-free, and the Knowledge Q&A adapter over `enterprise_rag` is
unchanged.

## Context

ADR 015 established the Office Agent as deterministic, local-only, and LLM-free
except for the Knowledge Q&A adapter, and ADR 016 reaffirmed that as the surface
grew to seven capabilities. The deterministic Email Summary tool
(`office_agent/tools/email.py`) filters and sorts a fictional mock inbox but never
reads the emails' unstructured `body` text — so concrete asks ("reply with the
missing hotel receipt") and deadlines ("before Friday's security sync") that live
in the bodies are invisible in its output.

Phase 1 of the selective-LLM plan adds one optional capability: an LLM digest that
reads the filtered emails' bodies and extracts a summary, action items, and a
priority order. The goal is to prove a **safe, bounded, opt-in** LLM assist inside
the Office Agent without turning it into an LLM-routed or autonomous system, and
without any risk to the default keys-free, deterministic behavior.

## Decision

Add an **optional, default-off, single-pass** LLM digest layered on top of — never
replacing — the deterministic Email Summary, in a new self-contained package
`office_agent/llm_assist/`:

- **Default off.** `OFFICE_LLM_ENABLED` (Office-only, in
  `office_agent/llm_assist/config.py`) defaults to false and enables the digest
  only on an explicit truthy value — the deliberate inverse of `enterprise_rag`'s
  default-on `WEB_SEARCH_ENABLED`. With the flag off, no LLM client is constructed
  and `summarize_emails` output is **byte-for-byte identical** to before.
- **One structured-output call, no orchestration.** A single LCEL chain
  (`get_email_digest_chain`) using `ChatOpenAI(model="gpt-5-mini", temperature=0,
  timeout=...)` with `with_structured_output(EmailDigest)`. No LangGraph, no
  retries, no tools bound, no self-correction loop.
- **Validated model is the only boundary.** LLM output crosses into the Office
  Agent solely as a validated `EmailDigest` (`summary`, `action_items[{email_id,
  ask, deadline?}]`, `priority_order`) and is rendered deterministically; subjects
  in the priority section are looked up from the filtered emails by id, never taken
  from the model.
- **Deterministic grounding validation.** `validate_digest` requires every
  `action_items[].email_id` and every `priority_order` id to be one of the
  *filtered* email ids, and `priority_order` ids to be unique. Any violation is a
  failure.
- **Honest fallback.** Any failure (timeout, API error, structured-output parse
  failure, Pydantic validation error, grounding failure) returns the deterministic
  summary plus one caveat line and `stop_reason="llm_assist_error"` (defined in the
  assist package, so `office_agent/schemas.py` is unchanged). The assist never
  re-raises and never crashes the Office Agent. Console logging is exception-type
  only.
- **Prompt-injection controls.** The system prompt declares subjects and bodies
  untrusted data, instructs the model to ignore instructions inside them and to
  reference only provided ids / never invent deadlines, and the model has no action
  surface (nothing to send, reply, delete, archive, move, or persist).
- **Scope containment.** Email only. The router, engine dispatch, `ToolResult` /
  `OfficeAgentResponse` schema shape, mock data (read-only), and the other six
  capabilities are unchanged. The engine already copies `stop_reason` from
  `ToolResult`, so the assist outcome flows through with no schema change.

Tests: mocked, keys-free unit tests in `tests/office_agent/`; exactly one
`requires_openai`-gated real-model test in a new `tests/office_chains/` directory
(gated like `tests/chains/`). A small separate Office-assist eval lives under
`evals/office_assist/` with an offline `--validate-only` mode; full runs are
approval-gated like the RAG eval.

## Rationale

- **Zero-risk default.** Default-off with a byte-for-byte guarantee means the
  feature cannot regress the deterministic Office Agent or its keys-free CI.
- **Bounded surface.** One tool, one call, a validated schema, and deterministic
  rendering keep the blast radius and failure modes small.
- **No unnecessary machinery.** The task is single-pass extraction; LangGraph,
  retries, or a shared "LLM service layer" would be overengineering at Phase 1.
- **Containment over trust.** The real injection defense is architectural (no
  action surface, validated schema, id cross-checks, deterministic rendering), with
  prompt hardening as a first line — mirroring the `enterprise_rag` posture.
- **Independent of `enterprise_rag`.** The assist package imports nothing from the
  RAG subsystem, so RAG behavior, prompts, model, budgets, and tests are untouched.

## Consequences

- The Office Agent now has **one** optional LLM-assisted capability (email digest);
  everything else stays deterministic and LLM-free.
- The default-off byte-for-byte contract and the grounding/fallback behavior are
  test-protected and must remain so.
- Documentation must keep distinguishing deterministic tools, this optional
  LLM-assisted feature, and (still none) autonomous agents.
- A real-model test directory (`tests/office_chains/`) and an Office-assist eval
  (`evals/office_assist/`) now exist and are approval-gated; keys-free CI is
  unaffected.
- Future selective-LLM phases (e.g. a Daily Briefing narrative) are **out of
  scope** here and each require their own ADR rather than silently widening this
  decision.

## Status and relationships

- **Status: Accepted**, per the repository convention.
- This ADR **extends and partially supersedes** the no-LLM stance recorded in
  [ADR 015](015-office-agent-v1-architecture.md) and reaffirmed in
  [ADR 016](016-office-agent-capability-extensions.md) — for the Email Summary tool
  only. It inherits the cross-cutting rules from
  [ADR 014](../enterprise_rag/014-enterprise-rag-package-and-office-agent-placeholder.md) and
  CLAUDE.md (side-effect-free imports, lazy `@lru_cache` clients, no regression to
  `enterprise_rag`).
